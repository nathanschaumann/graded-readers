#!/usr/bin/env python3
"""Build the static site data from the story files.

Reads   stories/*.txt            the graded readers (plain text, one file per story)
        french/*.fr.json         French versions, where they exist
        scorer/                  the Guiraud scorer, used here to compute each story's numbers
        METHOD.md                rendered to method.html

Writes  data/stories.json        the library index (one small record per story)
        data/stories/<slug>.json the text of one story, chapter by chapter
        method.html

Run from the repository root:   python3 scripts/build.py
Pure Python 3 standard library.
"""
import html
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scorer"))

import score as sc  # noqa: E402
from chapter_io import strip_speaker_label  # noqa: E402
from wordlist import load_wordlist, load_stemming_rules  # noqa: E402

LEVELS = [
    ("VE", "Very Easy", "Very Easy"),
    ("E", "Easy", "Easy"),
    ("M", "Medium", "Medium"),
    ("H", "Hard", "Hard"),
    ("VH", "Very Hard", "Very Hard"),
    ("oneoff", "One-off", "Jack (one-off)"),
]
SUFFIX = [("_englishVE", "VE"), ("_englishE", "E"), ("_englishM", "M"), ("_englishH", "H"),
          ("_englishVH", "VH"), ("_english_oneoff", "oneoff")]
LEVEL_LABEL = {code: label for code, label, _ in LEVELS}
LEVEL_CSV = {code: col for code, _, col in LEVELS}

NUM_RE = re.compile(r"^\s*(\d+)\.\s+(.*\S)\s*$")
PARA_RE = re.compile(r"^\s*(\d+)\s*(?:-\s*(\d+))?\s*:\s*(.*\S)\s*$")
LABEL_RE = re.compile(r"^([A-Z][A-Za-z']*(?: [A-Z][A-Za-z']*){0,3}):[ \t]+(.*)$")


def split_file_name(name):
    for suf, code in SUFFIX:
        if name.endswith(suf):
            return name[: -len(suf)], code
    raise ValueError(f"unknown level suffix: {name}")


def parse_raw(path):
    """Return (title, chapters). A chapter is {title, sents:[str], paras:[(a,b,summary)]}."""
    title = None
    pending = None
    chapters = []
    cur = None
    in_paras = False
    for raw in path.read_text(encoding="utf-8").splitlines():
        m = NUM_RE.match(raw)
        if m and not in_paras:
            if int(m.group(1)) == 1 or cur is None:
                cur = {"title": pending, "sents": [], "paras": []}
                chapters.append(cur)
                pending = None
            cur["sents"].append(m.group(2))
            continue
        line = raw.strip()
        if not line:
            in_paras = False
            continue
        if line == "Paragraphs:":
            in_paras = True
            continue
        pm = PARA_RE.match(line)
        if in_paras and pm and cur is not None:
            a = int(pm.group(1))
            b = int(pm.group(2) or pm.group(1))
            cur["paras"].append((a, b, pm.group(3)))
            continue
        in_paras = False
        if title is None:
            title = line
        else:
            pending = line
    return title, chapters


NO_SPACE_BEFORE = {",", ".", ")", "]", "CQ"}
NBSP_BEFORE = {";", ":", "!", "?", "»"}


def detok_french(tgt):
    """Turn the tagged 'word:pos word:pos' French into plain typeset text."""
    out = ""
    prev = None
    for tok in tgt.split(" "):
        w = tok.rsplit(":", 1)[0]
        if w == "OQ":
            w = "‘"
        elif w == "CQ":
            w = "’"
        if prev is None:
            sep = ""
        elif w.startswith("-") or w in (",", ".", ")", "]") or w == "’":
            sep = ""
        elif w in (";", ":", "!", "?", "»"):
            sep = " "
        elif prev in ("«",):
            sep = " "
        elif prev in ("(", "[", "‘") or prev.endswith("'") or prev.endswith("’") and len(prev) > 1:
            sep = ""
        else:
            sep = " "
        out += sep + w
        prev = w
    return out.replace("'", "’")


def main():
    wl = load_wordlist()
    irreg, suffixes = load_stemming_rules()
    constraints = sc.load_constraints()
    (ROOT / "data" / "stories").mkdir(parents=True, exist_ok=True)
    index = []
    for path in sorted((ROOT / "stories").glob("*.txt")):
        slug, code = split_file_name(path.stem)
        title, chapters = parse_raw(path)
        fr_path = ROOT / "french" / f"{slug}.fr.json"
        fr_sents = None
        if fr_path.exists():
            fr_sents = json.load(open(fr_path, encoding="utf-8"))["sentences"]
        flat_en = [s for ch in chapters for s in ch["sents"]]
        if fr_sents is not None:
            if len(fr_sents) != len(flat_en) or any(a != b["en"] for a, b in zip(flat_en, fr_sents)):
                raise SystemExit(f"French does not line up with English for {slug}")

        # --- numbers from the scorer -------------------------------------------------
        proper = sc.resolve_proper(str(path), None)
        is_proper = sc.make_is_proper(proper)
        bounds = constraints[LEVEL_CSV[code]]
        cum = []
        words_total = 0
        longest = 0
        over_cap = 0
        ch_over_g = 0
        ch_len_flags = 0
        ch_stats = []
        for ch in chapters:
            bodies = [strip_speaker_label(s) for s in ch["sents"]]
            sp, _ = sc.stem_sentences(bodies, is_proper, irreg, suffixes, wl)
            flat = [x for row in sp for x in row]
            cum += flat
            lens = [sc.count_words_rule1(s) for s in bodies]
            w = sum(lens)
            g = sc.guiraud(flat)
            words_total += w
            longest = max(longest, max(lens, default=0))
            over_cap += sum(1 for n in lens if n > bounds["max_sentence_words"])
            ch_over_g += 1 if g > bounds["guiraud_ceiling"] else 0
            fl, ce = bounds["chapter_floor"], bounds["chapter_ceiling"]
            if fl is not None and (w < fl or w > ce):
                ch_len_flags += 1
            ch_stats.append({"words": w, "guiraud": round(g, 2)})
        cum_g = sc.guiraud(cum)

        # --- story text --------------------------------------------------------------
        gi = 0
        out_chapters = []
        for ci, ch in enumerate(chapters):
            sents = []
            for i, raw in enumerate(ch["sents"]):
                item = {}
                m = LABEL_RE.match(raw)
                if m:
                    item["sp"], item["t"] = m.group(1), m.group(2)
                else:
                    item["t"] = raw
                if fr_sents is not None:
                    item["fr"] = detok_french(fr_sents[gi]["tgt"])
                gi += 1
                sents.append(item)
            paras = []
            ranges = ch["paras"] or [(1, len(sents), "")]
            covered = 0
            for a, b, summary in ranges:
                chunk = sents[a - 1:b]
                if chunk:
                    paras.append({"s": chunk, "summary": summary})
                    covered += len(chunk)
            if covered != len(sents):  # ranges did not cover the chapter: fall back to one block
                paras = [{"s": sents, "summary": ""}]
            names = [t.strip() for t in (ch["title"] or f"Chapter {ci + 1}").split(" / ")]
            out_chapters.append({"title": names[0], "also": names[1:], "paras": paras,
                                 "words": ch_stats[ci]["words"], "guiraud": ch_stats[ci]["guiraud"]})

        record = {
            "slug": slug,
            "file": path.name,
            "title": title,
            "level": code,
            "levelLabel": LEVEL_LABEL[code],
            "words": words_total,
            "chapters": len(chapters),
            "sentences": len(flat_en),
            "longest": longest,
            "sentenceCap": bounds["max_sentence_words"],
            "guiraud": round(cum_g, 2),
            "guiraudCeiling": bounds["cum_ceiling"],
            "chapterCeiling": bounds["guiraud_ceiling"],
            "chaptersOverCeiling": ch_over_g,
            "sentencesOverCap": over_cap,
            "chapterLengthFlags": ch_len_flags,
            "french": fr_sents is not None,
            "script": any("sp" in s for c in out_chapters for p in c["paras"] for s in p["s"]),
        }
        story = dict(record)
        story["chapterList"] = out_chapters
        (ROOT / "data" / "stories" / f"{slug}.json").write_text(
            json.dumps(story, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        index.append(record)

    order = {code: i for i, (code, _, _) in enumerate(LEVELS)}
    index.sort(key=lambda r: (order[r["level"]], r["title"].lower()))
    levels = []
    for code, label, col in LEVELS:
        b = constraints[col]
        levels.append({"code": code, "label": label, "maxSentence": b["max_sentence_words"],
                       "chapterCeiling": b["guiraud_ceiling"], "cumCeiling": b["cum_ceiling"],
                       "count": sum(1 for r in index if r["level"] == code)})
    (ROOT / "data" / "stories.json").write_text(
        json.dumps({"levels": levels, "stories": index}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(index)} stories, {sum(1 for r in index if r['french'])} with French")
    render_method()


def inline(s):
    s = html.escape(s, quote=False)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s)
    return s


def render_method():
    """Tiny Markdown renderer for METHOD.md: headings, paragraphs, bullets, one table style."""
    src = (ROOT / "METHOD.md").read_text(encoding="utf-8").splitlines()
    body = []
    i = 0
    while i < len(src):
        line = src[i]
        if line.startswith("# "):
            body.append(f"<h1>{inline(line[2:])}</h1>")
        elif line.startswith("## "):
            body.append(f"<h2>{inline(line[3:])}</h2>")
        elif line.startswith("|"):
            rows = []
            while i < len(src) and src[i].startswith("|"):
                rows.append([c.strip() for c in src[i].strip().strip("|").split("|")])
                i += 1
            rows = [r for r in rows if not all(set(c) <= set("-: ") for c in r)]
            t = "<div class='tablewrap'><table><thead><tr>" + "".join(f"<th>{inline(c)}</th>" for c in rows[0]) + "</tr></thead><tbody>"
            for r in rows[1:]:
                t += "<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>"
            body.append(t + "</tbody></table></div>")
            continue
        elif line.startswith("- "):
            items = []
            while i < len(src) and src[i].startswith("- "):
                items.append(f"<li>{inline(src[i][2:])}</li>")
                i += 1
            body.append("<ul>" + "".join(items) + "</ul>")
            continue
        elif line.strip():
            para = [line.strip()]
            while i + 1 < len(src) and src[i + 1].strip() and not re.match(r"^(#|\||- )", src[i + 1]):
                i += 1
                para.append(src[i].strip())
            body.append(f"<p>{inline(' '.join(para))}</p>")
        i += 1
    page = (ROOT / "scripts" / "method_template.html").read_text(encoding="utf-8")
    (ROOT / "method.html").write_text(page.replace("{{BODY}}", "\n".join(body)), encoding="utf-8")


if __name__ == "__main__":
    main()
