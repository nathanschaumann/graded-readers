"""Score a graded-reader story file by the Guiraud index and check it against its level.

Guiraud index = unique word stems / sqrt(total word tokens). Higher means more varied
vocabulary. Each story is one plain-text file: a title, then titled chapters of numbered
sentences (each chapter is followed by a `Paragraphs:` block of summaries, which the
scorer ignores). A chapter starts wherever the sentence number resets to 1.

Usage (run from the repository root):

    python3 scorer/score.py stories/cinderella_englishE.txt              # last chapter
    python3 scorer/score.py stories/cinderella_englishE.txt --chapter 5  # chapter 5
    python3 scorer/score.py stories/cinderella_englishE.txt --all        # every chapter

Scoring chapter k uses chapters 1..k for the cumulative line.

Proper nouns (character and place names) are left out of the Guiraud count, though the
word count still includes them. Names are looked up per story, by file name, in
scorer/proper_nouns.json and scorer/proper_nouns/*.json; pass --proper a,b,c to override.

The level comes from the file-name suffix (VE, E, M, H, VH, or _oneoff), and the bounds
come from scorer/difficulty_constraints.csv. The scorer flags:

  - a chapter under 300 or over 600 words;
  - a sentence over the level's word cap;
  - a chapter or cumulative Guiraud above the level's ceiling.

There are no Guiraud floors: a low value is never a flag. Stories written before the
300-600 word chapter rule (2026-09-06) were held to older, shorter-chapter limits, so
they can legitimately show chapter-length flags. See METHOD.md.

The word list (scorer/wordlist.txt) is the stemmer's dictionary, not a list of allowed
words. Stemming rules are in scorer/stemming_rules.json. Pure Python 3 standard library.
"""
import argparse
import csv
import json
import math
import os
import sys
from collections import Counter
from pathlib import Path

from chapter_io import parse_story_full
from wordlist import (
    load_wordlist, load_stemming_rules, tokenize, stem,
    split_tokens_and_numerals,
)

_CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "difficulty_constraints.csv")

# filename suffix -> difficulty_constraints.csv column header
_LEVEL_CSV_COLUMN = [
    ("_englishVE.txt", "Very Easy"),
    ("_englishE.txt", "Easy"),
    ("_englishM.txt", "Medium"),
    ("_englishH.txt", "Hard"),
    ("_englishVH.txt", "Very Hard"),
    ("_english_oneoff.txt", "Jack (one-off)"),
]


def level_for_file(path: str):
    """Return the difficulty_constraints.csv column header for `path`'s
    filename suffix, or None if it doesn't match a known level."""
    name = os.path.basename(path)
    for suffix, column in _LEVEL_CSV_COLUMN:
        if name.endswith(suffix):
            return column
    return None


def _parse_chapter_words(cell: str):
    """'300/400/600' -> (300, 400, 600); '—' (Jack, no chapter word cap) ->
    (None, None, None)."""
    cell = cell.strip()
    if cell in ("—", "-", ""):
        return None, None, None
    floor_s, target_s, ceiling_s = cell.split("/")
    return int(floor_s), int(target_s), int(ceiling_s)


def load_constraints() -> dict:
    """Return {csv column header: bounds dict} from difficulty_constraints.csv,
    read fresh every call (this is a small, rarely-changed file; no caching
    benefit is worth the staleness risk)."""
    with open(_CSV_PATH, encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f))
    header = rows[0][1:]  # column headers, e.g. Very Easy/Easy/Medium/Hard/Very Hard/Jack (one-off)
    by_row = {row[0]: row[1:] for row in rows[1:]}
    out = {}
    for i, column in enumerate(header):
        cf, ct, cc = _parse_chapter_words(by_row["Words per chapter (floor/target/ceiling)"][i])
        out[column] = {
            "max_sentence_words": int(by_row["Words per sentence (max)"][i]),
            "chapter_floor": cf,
            "chapter_target": ct,
            "chapter_ceiling": cc,
            "guiraud_ceiling": float(by_row["Per-chapter Guiraud ceiling"][i]),
            "cum_ceiling": float(by_row["Cumulative Guiraud ceiling"][i]),
        }
    return out


def chapter_flags(sentences, word_count, guiraud_val, cum_val, bounds):
    """Return a list of short flag strings for one chapter against `bounds`
    (one entry from `load_constraints()`, or None if the file's level is
    unrecognized — in which case nothing is flagged)."""
    if bounds is None:
        return []
    flags = []
    if bounds["chapter_floor"] is not None and word_count < bounds["chapter_floor"]:
        flags.append(f"UNDER {bounds['chapter_floor']}w ({word_count}w)")
    if bounds["chapter_ceiling"] is not None and word_count > bounds["chapter_ceiling"]:
        flags.append(f"OVER {bounds['chapter_ceiling']}w ({word_count}w)")
    cap = bounds["max_sentence_words"]
    for i, s in enumerate(sentences, 1):
        n = count_words_rule1(s)
        if n > cap:
            flags.append(f"S{i} {n}w > {cap}w cap")
    # Ceilings only, at every level: a low Guiraud is never a flag.
    gc = bounds["guiraud_ceiling"]
    if guiraud_val > gc:
        flags.append(f"Guiraud {guiraud_val:.2f} > ceiling {gc}")
    if cum_val is not None and cum_val > bounds["cum_ceiling"]:
        flags.append(f"cumGuiraud {cum_val:.2f} > ceiling {bounds['cum_ceiling']}")
    return flags

_PROPER_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "proper_nouns.json")
_PROPER_SIDECAR_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "proper_nouns")


def count_words_rule1(text: str) -> int:
    """Count words per the sentence-length rule (Sentence length).

    Contractions count as 1 (`don't` -> 1), hyphenated compounds as their
    parts (`gold-trimmed` -> 2), numerals as 1 (`12` or `twelve` -> 1).
    Delegates to `wordlist.split_tokens_and_numerals` so this and the stemmer
    tokenizer can't drift apart.
    """
    letters, digits = split_tokens_and_numerals(text)
    return len(letters) + len(digits)


def _name_set(raw: str) -> set:
    """Split a 'name,name' string into a lowercased, stripped, non-empty set."""
    return {p.strip().lower() for p in raw.split(",") if p.strip()}


def load_proper_registry() -> dict:
    """Return the {story-file-name: 'name,name'} map from proper_nouns.json,
    unioned with any per-story sidecar files in proper_nouns/ (keys starting
    with '_' are comments and are skipped, in both the main file and every
    sidecar).

    A sidecar has the same shape as proper_nouns.json (typically one entry)
    and lets a parallel story-writing agent register names for its own story
    without editing the shared proper_nouns.json. Per story key, sidecar
    names are UNIONED into the main registry's names — a sidecar can only
    ADD names, never remove or override ones already in proper_nouns.json.
    A sidecar file that isn't valid JSON, or whose top level isn't a JSON
    object, is skipped with a one-line warning on stderr; scoring continues
    with whatever loaded successfully.
    """
    try:
        with open(_PROPER_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        data = {}
    merged = {k: _name_set(v) for k, v in data.items() if not k.startswith("_")}

    try:
        sidecar_files = sorted(
            name for name in os.listdir(_PROPER_SIDECAR_DIR)
            if name.endswith(".json")
        )
    except FileNotFoundError:
        sidecar_files = []

    for name in sidecar_files:
        path = os.path.join(_PROPER_SIDECAR_DIR, name)
        try:
            with open(path, encoding="utf-8") as f:
                side_data = json.load(f)
            if not isinstance(side_data, dict):
                raise ValueError("top-level JSON must be an object")
            for k, v in side_data.items():
                if k.startswith("_"):
                    continue
                merged[k] = merged.get(k, set()) | _name_set(v)
        except Exception as exc:
            print(f"warning: skipping malformed proper-noun sidecar {path}: {exc}",
                  file=sys.stderr)

    return {k: ",".join(sorted(v)) for k, v in merged.items()}


def resolve_proper(story_path: str, override) -> set:
    """Proper-noun set for a story: the explicit `--proper` override if given,
    else the registry entry keyed by file name, else empty."""
    if override is not None:
        raw = override
    else:
        raw = load_proper_registry().get(os.path.basename(story_path), "")
    return {p.strip().lower() for p in raw.split(",") if p.strip()}


def make_is_proper(proper: set):
    def is_proper(token: str) -> bool:
        if not proper:
            return False
        if token in proper:
            return True
        # single-trailing-s form: "auroras" (from "Aurora's") -> "aurora"
        return len(token) > 1 and token.endswith("s") and token[:-1] in proper
    return is_proper


def stem_sentences(sentences, is_proper, irreg, suffixes, wl):
    """Return (stems_per_sentence, missed_per_sentence) for a chapter."""
    stems_per_s, missed_per_s = [], []
    for sent in sentences:
        here, missed = [], []
        for w in tokenize(sent):
            if is_proper(w):
                continue
            s = stem(w, irreg, suffixes, wl)
            here.append(s)
            if s not in wl:
                missed.append(w)
        stems_per_s.append(here)
        missed_per_s.append(missed)
    return stems_per_s, missed_per_s


def guiraud(stems) -> float:
    return len(set(stems)) / math.sqrt(len(stems)) if stems else 0.0


def top3_str(stems) -> str:
    ranked = sorted(Counter(stems).items(), key=lambda kv: (-kv[1], kv[0]))[:3]
    return ", ".join(f"{s} ({c})" for s, c in ranked)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("story", help="bundled one-file-per-story draft (stories/<story>_english<level>.txt)")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--chapter", type=int, default=None,
                   help="1-based chapter to score (default: the last chapter in the file)")
    g.add_argument("--all", action="store_true",
                   help="print a per-chapter table for the whole story instead of one chapter")
    ap.add_argument("--proper", default=None,
                    help="comma-separated character names (lowercase) to exclude from Guiraud. "
                         "If omitted, looked up in scorer/proper_nouns.json by file name.")
    args = ap.parse_args()

    wl = load_wordlist()
    irreg, suffixes = load_stemming_rules()
    proper = resolve_proper(args.story, args.proper)
    is_proper = make_is_proper(proper)

    story_title, chapters = parse_story_full(Path(args.story))
    if not chapters:
        print("No numbered chapters found — is this a bundled story file?")
        return
    titles = [t for t, _ in chapters]
    bodies = [s for _, s in chapters]

    level = level_for_file(args.story)
    bounds = load_constraints().get(level) if level else None
    if level is None:
        print("(unrecognized level suffix — not flagging against difficulty_constraints.csv)")

    if args.all:
        pname = ",".join(sorted(proper)) or "(none)"
        print(f"{story_title or args.story}  —  {len(chapters)} chapters  (proper: {pname})")
        print(f"{'ch':>3}  {'sents':>5}  {'words':>5}  {'long':>4}  {'Guiraud':>7}  {'cumG':>5}  most-repeated stems")
        cum = []
        all_flags = []
        for i, sents in enumerate(bodies, 1):
            sp, _ = stem_sentences(sents, is_proper, irreg, suffixes, wl)
            flat = [s for row in sp for s in row]
            cum += flat
            words = sum(count_words_rule1(s) for s in sents)
            longest = max((count_words_rule1(s) for s in sents), default=0)
            g = guiraud(flat)
            cg_val = None if i == 1 else guiraud(cum)
            cg = "—" if cg_val is None else f"{cg_val:.2f}"
            print(f"{i:>3}  {len(sents):>5}  {words:>5}  {longest:>4}  {g:>7.2f}  {cg:>5}  {top3_str(flat)}")
            flags = chapter_flags(sents, words, g, cg_val, bounds)
            if flags:
                all_flags.append((i, flags))
        print(f"\nWhole-story cumulative Guiraud: {guiraud(cum):.2f}")
        if bounds is not None:
            if all_flags:
                print(f"\nFlags against the {level} bounds (see difficulty_constraints.csv):")
                for i, flags in all_flags:
                    for f in flags:
                        print(f"  ch.{i}: {f}")
                print("  (a story written before 2026-09-06 was held to older, retired bounds, so "
                      "chapter-length flags on it are expected; see METHOD.md)")
            else:
                print(f"\nNo flags against the {level} bounds.")
        return

    # Single-chapter mode.
    k = args.chapter if args.chapter is not None else len(chapters)
    if not (1 <= k <= len(chapters)):
        ap.error(f"--chapter {k} out of range (story has {len(chapters)} chapters)")

    # Cumulative stems across chapters 1..k; keep the current chapter's
    # per-sentence stems for the Block-2 sentence locations.
    cum_stems = []
    cur_sp = cur_missed = None
    for i in range(k):
        sp, missed = stem_sentences(bodies[i], is_proper, irreg, suffixes, wl)
        flat = [s for row in sp for s in row]
        cum_stems += flat
        if i == k - 1:
            cur_sp, cur_missed = sp, missed

    sentences = bodies[k - 1]
    cur_stems = [s for row in cur_sp for s in row]
    all_missed = [w for row in cur_missed for w in row]
    if not cur_stems:
        print("no tokens in this chapter")
        return

    sent_lens = [count_words_rule1(s) for s in sentences]
    word_count = sum(sent_lens)

    # --- Block 1: the metadata values ------------------------------------
    label = titles[k - 1] or f"chapter {k}"
    print(f"# {story_title or ''} — ch.{k}: {label}".rstrip(" —"))
    print(f"Guiraud: {guiraud(cur_stems):.2f}")
    if k > 1:
        print(f"Cumulative Guiraud: {guiraud(cum_stems):.2f}")
    print(f"Word Count: {word_count}")
    print(f"Longest Sentence: {max(sent_lens, default=0)} words")
    print(f"Sentence Count: {len(sentences)} sentences")
    print(f"Most-Repeated Stems: {top3_str(cur_stems)}")

    if bounds is not None:
        cum_val = None if k == 1 else guiraud(cum_stems)
        flags = chapter_flags(sentences, word_count, guiraud(cur_stems), cum_val, bounds)
        if flags:
            print(f"\nFlags against the {level} bounds (see difficulty_constraints.csv):")
            for f in flags:
                print(f"  {f}")
            print("  (a story written before 2026-09-06 was held to older, retired bounds, so "
                  "chapter-length flags on it are expected; see METHOD.md)")
        else:
            print(f"\nNo flags against the {level} bounds.")

    # --- Block 2: iteration aids -----------------------------------------
    print()
    print("Top 10 most-repeated stems and their sentences:")
    ranked = sorted(Counter(cur_stems).items(), key=lambda kv: (-kv[1], kv[0]))
    for s, c in ranked[:10]:
        locs = [idx for idx, row in enumerate(cur_sp, 1) if s in row]
        loc = ", ".join(f"S{i}" for i in locs) or "—"
        print(f"  {s} ({c}) — {loc}")
    if all_missed:
        print()
        print(f"Unmatched ({len(all_missed)}): {sorted(set(all_missed))}")


if __name__ == "__main__":
    main()
