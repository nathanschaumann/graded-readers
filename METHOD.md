# Method

How the readers were written and checked, and what that does not prove.

## The five levels

Every story is a plain, literal retelling of a public-domain tale, written so a learner meets the same small core of words many times. Each level has hard limits. Chapters at every level are 300 to 600 words, aiming for about 400.

| Level | Longest sentence | Guiraud ceiling per chapter | Guiraud ceiling for the whole story |
| --- | --- | --- | --- |
| Very Easy | 10 words | 6.2 | 6.0 |
| Easy | 12 words | 6.4 | 6.1 |
| Medium | 15 words | 6.5 | 6.3 |
| Hard | 20 words | 6.6 | 6.5 |
| Very Hard | 24 words | 7.0 | 7.0 |

One story, Jack and the Beanstalk, is a one-off with its own limits: 10 words per sentence and ceilings of 5.5 (chapter) and 6.0 (whole story). The limits live in `scorer/difficulty_constraints.csv`. There are ceilings only, no floors: a low score is never a failure.

The writing rules on top of the numbers: every word in its most literal sense (no metaphors), character names preferred over pronouns, and a lean toward dialogue over reported speech.

## What Guiraud is

Guiraud lexical diversity is the number of different word stems divided by the square root of the number of words, so a text that keeps reusing its words scores low and a text that keeps bringing in new words scores high.

## How the scorer checks a story

`scorer/score.py` reads a story file and splits it into chapters. It sets aside character and place names, then reduces each remaining word to its base form (so "ran" and "runs" both count as "run"), using a word list, a table of irregular forms and a set of suffix rules. It then works out the Guiraud score for each chapter and for the story so far, and flags anything outside the level's limits: a chapter under 300 or over 600 words, a sentence over the level's cap, or a chapter or whole-story score above its ceiling. Nothing in it calls a network or a model.

## Limitations

- **AI-drafted, not professionally edited.** The stories were drafted with Claude (Anthropic) under these rules and checked by the automated scorer. No professional editor or publisher has reviewed them.
- **The level is a lexical measure, not a validated one.** Sentence length and word repetition are checked. Nobody has tested the levels against learners, or mapped them to CEFR or ACTFL. A low Guiraud score means words repeat, not that the words are common.
- **Guiraud shifts with text length,** so scores from very short and very long texts compare only roughly. That is why chapter length is fixed to one band.
- **Older stories break the chapter rule.** Stories written before the 300 to 600 word rule were held to shorter chapters, capped at 120 to 400 words depending on level, and were not rewritten. Of the 581 chapters in this collection, 247 are under 300 words, and 28 of the 52 stories have at least one. The scorer flags these.
- **A few scores are over their ceiling.** Two whole stories are just above theirs (The Pied Piper of Hamelin, 6.11 against 6.1, and The Steadfast Tin Soldier, 6.15 against 6.1), and 9 chapters sit above their per-chapter ceiling. Stories were later shortened by deleting filler sentences, and those chapters were left as they were.
- **These are adaptations.** They compress, simplify and sometimes reorder the source. They are not translations, and they end where the plot ends.
- **Four stories keep an older script format,** where spoken lines start with the speaker's name.
- **The French is machine-assisted.** The ten Very Hard stories have a French version written sentence by sentence with AI help. No professional translator has checked it.
