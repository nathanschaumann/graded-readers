# Graded Readers

Public-domain tales retold in plain, literal English at five levels, with an open scorer that checks each story against its level's limits. Some have a French version. It is a static site: no server, no accounts, no build step to view it.

## What is in it

52 stories: Very Easy 13, Easy 14, Medium 8, Hard 6, Very Hard 10, plus one one-off (Jack and the Beanstalk). The ten Very Hard stories have a French version. The library has a level filter, search and sort. Reader pages have light and dark themes, adjustable text size, a language toggle (English, French or side by side), optional summaries and a scorer report.

Each level caps sentence length (10, 12, 15, 20 and 24 words) and a Guiraud lexical-diversity ceiling per chapter and per story. Chapters run 300 to 600 words. Exact limits: [METHOD.md](METHOD.md).

## Use it

Open `index.html`, or serve the folder:

    python3 -m http.server 8000

It also works on GitHub Pages.

## Score a text

The scorer is pure Python 3, standard library only:

    python3 scorer/score.py stories/cinderella_englishE.txt --all
    python3 scorer/score.py stories/cinderella_englishE.txt --chapter 5

To score your own text, save it like the files in `stories/`: a title line, then chapters, each a title followed by numbered sentences that restart at 1. End the file name with `_englishVE`, `_englishE`, `_englishM`, `_englishH` or `_englishVH` to pick a level. Character names can be left out of the count with `--proper anna,mark`.

To rebuild the site data after editing a story: `python3 scripts/build.py`.

## How it was made

The stories were drafted with Claude (Anthropic) under written rules and checked with the scorer. They were not edited by a professional editor or publisher, and the levels have not been tested with learners. The French versions were also written with AI help and are not professionally checked. [METHOD.md](METHOD.md) lists the limits.

## Sources and licenses

The tales are retellings of public-domain works by Grimm, Andersen, Perrault, the Arabian Nights, Baum, Stevenson, Dickens, Stoker, Shelley, Wells, Doyle, London, Wilde, Carroll, Swift, Homer and others, or of traditional folk tales.

- **Code** (html, css, js, `scorer/*.py`, `scripts/`): MIT, see [LICENSE](LICENSE).
- **Stories and French versions** (`stories/`, `french/`, and the `data/` built from them): CC BY 4.0. Copyright (c) 2026 Nathan Schaumann. Reuse them with credit.
- **Scorer data** (`scorer/wordlist.txt`, `stemming_rules.json`, `proper_nouns*`): a base-word dictionary and rules the stemmer uses, not a list of allowed words.
