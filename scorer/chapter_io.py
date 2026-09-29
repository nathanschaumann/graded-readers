"""Parsers for the story draft files that `score.py` reads.

The project writes **one file per story** (bundled). A bundled draft looks like:

    <Story Title>

    <Chapter Title>
    1. <sentence>
    2. <sentence>
    ...
    N. <sentence>

    Paragraphs:
    <a>-<b>: <summary>
    ...

    <next Chapter Title>
    1. <sentence>
    ...

Chapters are delimited by the numbered sentence index resetting to 1. The
story title (line 1), the chapter titles, the `Paragraphs:` headers, and the
`<a>-<b>: …` range lines are all ignored by the scorer — only the numbered
sentences are scored. A numbered sentence may open with a play-script speaker
label (`Cat: I can help you.`); that leading `Name: ` is stripped by
`strip_speaker_label` so the speaker name never counts toward the word cap or
the Guiraud score (a retired play-script format that four stories still use).

`parse_story` returns one list of sentences per chapter; `parse_story_full`
also returns the story title and each chapter's title. `parse_chapter` is the
legacy single-chapter parser (one block of numbered sentences), kept for any
caller that hands in a lone chapter's text.
"""

import re
from pathlib import Path


_NUMBERED_LINE_RE = re.compile(r"^\s*(\d+)\.\s+(.*\S)\s*$")
_DIVIDER_RE = re.compile(r"^---\s*$", re.MULTILINE)
# A Paragraphs: summary line — "1-5: …" or "7: …". Used to keep these out of
# the chapter-title detection in the bundled-story parser.
_PARA_RANGE_RE = re.compile(r"^\s*\d+\s*(?:-\s*\d+)?\s*:")

# A leading play-script speaker label on a spoken line — one to four Capitalized
# words, then a colon and a space: "Cat: I can help you." / "White Rabbit: I am
# late." Every consumer (scorer, word counter, longest-sentence, stats) sees the
# sentence with this label removed, so the speaker name is invisible to the word
# cap and to the Guiraud calculation — the dialogue-forward format's whole premise
# (four stories use this retired script format). Requiring every label word to be Capitalized keeps ordinary narration
# untouched — a plain sentence never opens with capitalized-word(s)+colon+space —
# and it is a no-op on ordinary prose.
_SPEAKER_LABEL_RE = re.compile(
    r"^(?:[A-Z][A-Za-z']*(?: [A-Z][A-Za-z']*){0,3}):[ \t]+(.*)$"
)


def strip_speaker_label(sentence: str) -> str:
    """Return `sentence` with a leading `Name: ` play-script speaker label removed.

    A no-op on any sentence that doesn't open with a capitalized-word(s) label
    followed by a colon and a space, which is every line in the pre-dialogue
    stories. The label is dropped before counting/scoring so it never costs a
    word against the sentence cap or a token/type against Guiraud.
    """
    m = _SPEAKER_LABEL_RE.match(sentence)
    return m.group(1) if m else sentence


def _read(text_or_path):
    if isinstance(text_or_path, Path):
        return text_or_path.read_text(encoding="utf-8")
    return text_or_path


def parse_story_full(text_or_path):
    """Split a bundled one-file-per-story draft into chapters.

    Returns ``(story_title, [(chapter_title, [sentence, ...]), ...])``.

    A new chapter starts whenever a numbered line resets to ``1.``. The first
    non-empty, non-numbered line is taken as the story title; each later
    non-empty, non-numbered line that is not the ``Paragraphs:`` header or a
    ``<a>-<b>:`` range line is remembered as the pending chapter title and
    attached to the next chapter that opens. Titles may be ``None`` for a
    malformed draft missing them.
    """
    text = _read(text_or_path)
    story_title = None
    pending_title = None
    chapters = []
    cur = None
    for raw in text.splitlines():
        m = _NUMBERED_LINE_RE.match(raw)
        if m:
            if int(m.group(1)) == 1:
                cur = []
                chapters.append((pending_title, cur))
                pending_title = None
            if cur is None:  # numbered lines before any "1." — start a chapter
                cur = []
                chapters.append((pending_title, cur))
                pending_title = None
            cur.append(strip_speaker_label(m.group(2)))
            continue
        line = raw.strip()
        if not line or line == "Paragraphs:" or _PARA_RANGE_RE.match(line):
            continue
        if story_title is None:
            story_title = line
        else:
            pending_title = line
    return story_title, chapters


def parse_story(text_or_path):
    """Return ``[[sentence, ...], ...]`` — one list of sentences per chapter
    from a bundled story draft. Thin wrapper over `parse_story_full`."""
    return [sents for _title, sents in parse_story_full(text_or_path)[1]]


def parse_chapter(text_or_path):
    """Return the numbered sentences from one englishE/englishVE draft file as a
    list[str] (the `"N. "` prefix is stripped).

    Falls back to whole-file non-blank lines when nothing is numbered
    (a work-in-progress draft with no `---` dividers or no numbering
    yet). The fallback drops the first chunk if there are multiple,
    on the assumption it's a metadata header.

    Pass either a `pathlib.Path` (read with utf-8) or already-loaded text.
    """
    if isinstance(text_or_path, Path):
        text = text_or_path.read_text(encoding="utf-8")
    else:
        text = text_or_path

    for section in _DIVIDER_RE.split(text):
        sentences = []
        for line in section.splitlines():
            m = _NUMBERED_LINE_RE.match(line)
            if m:
                sentences.append(strip_speaker_label(m.group(2)))
        if sentences:
            return sentences

    # Fallback: no numbered sentences anywhere. Drop the first chunk if
    # there are multiple (assume it's a header), then take non-blank lines.
    raw = _DIVIDER_RE.split(text)
    body = raw[-1] if len(raw) > 1 else raw[0]
    return [ln.strip() for ln in body.splitlines() if ln.strip()]
