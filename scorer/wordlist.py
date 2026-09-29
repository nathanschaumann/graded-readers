"""Shared helpers for the Guiraud-index scoring scripts.

The canonical word set lives in `wordlist.txt` (one stem per line) and the
stemming rules live in `stemming_rules.json` (`irregulars` map + ordered
`suffixes` list). Both sit next to this file and are the source of truth —
edit them directly.
"""
import json
import os
import re


_HERE = os.path.dirname(os.path.abspath(__file__))
_WORDLIST_PATH = os.path.join(_HERE, "wordlist.txt")
_RULES_PATH    = os.path.join(_HERE, "stemming_rules.json")


def load_wordlist():
    """Return a set of every canonical word, lowercased."""
    with open(_WORDLIST_PATH, encoding="utf-8") as f:
        return {line.strip().lower() for line in f if line.strip()}


def load_stemming_rules():
    """Return (irreg_map, suffix_cascade).

      irreg_map        dict mapping inflected form -> base form
      suffix_cascade   list of (suffix, replacement) tuples in priority order
    """
    with open(_RULES_PATH, encoding="utf-8") as f:
        data = json.load(f)
    irreg = {k.lower(): v.lower() for k, v in data["irregulars"].items()}
    suffixes = [(s.lower(), r.lower()) for s, r in data["suffixes"]]
    return irreg, suffixes


def split_tokens_and_numerals(text):
    """Single source of truth for "how do we count words in a sentence?".

    Strips straight + curly apostrophes (so `don't` and `don't` both become
    the letter run `dont` — a one-word contraction per the project's
    rule-1 word counting). Then returns two lists:

      (letter_runs, digit_runs)

    `letter_runs` is the lowercased contractions-collapsed tokenizer
    output used by the wordlist + stemmer. `digit_runs` is needed for the
    Word-Count rule (`12` counts as one word, like a numeral). Hyphenated
    compounds split naturally because the hyphen is a non-letter and ends
    a letter-run — `gold-trimmed` becomes [`gold`, `trimmed`] which is
    what the rule wants (count = 2).

    Replaces the historical pair of nearly-identical helpers
    (`tokenize` in this file and `count_words_rule1` in score.py).
    """
    cleaned = text.replace("'", "").replace("’", "")  # straight & curly
    letters = re.findall(r"[A-Za-z]+", cleaned.lower())
    digits  = re.findall(r"\d+", cleaned)
    return letters, digits


def tokenize(text):
    """Lowercased contractions-collapsed letter-run list — the input to
    the stemmer / wordlist matcher. Thin wrapper over
    `split_tokens_and_numerals` that drops the numeric run."""
    letters, _ = split_tokens_and_numerals(text)
    return letters


def stem(word, irreg, suffixes, wordlist):
    """Stem one word against the project's stemmer, in order:
      1. Irregulars: if word is in IRREG and its mapped base form
         is in the wordlist, return the base form.
      2. Direct match: if the word itself is in the wordlist, return it.
      3. Suffix cascade: try each suffix rule in order; return the
         first transformed candidate that is in the wordlist.
      4. Otherwise return the original word (unmatched).

    Note the irregulars step takes priority over direct match — that's why
    e.g. `told` stems to `tell` even though `told` is itself in the wordlist."""
    w = word.lower()
    if w in irreg:
        mapped = irreg[w]
        if mapped in wordlist:
            return mapped
    if w in wordlist:
        return w
    for suf, rep in suffixes:
        if w.endswith(suf):
            cand = w[: -len(suf)] + rep
            if cand in wordlist:
                return cand
    return w
