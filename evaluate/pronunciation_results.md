# Step 4d: our scores vs expert teachers (2026-11-21)

**Data:** speechocean762 (free, Apache 2.0, `data/speechocean762/`). 5,000 short English sentences read by
Mandarin-native learners (half children), each scored by 5 experts. We used 400 random **train** sentences
to tune and 400 random **test** sentences (never used for tuning) to judge.
Run: `python -m evaluate.speechocean_eval extract train 400`, `... extract test 400`, then `... report`
(about 10 s per sentence on CPU, 2.2 h in total). Full output: `logs/so762_run.log`.

PCC = correlation with the teachers (1 = exactly the same ranking, 0 = unrelated).

## Pronunciation
| | PCC with teachers (test) |
|---|---|
| first guess (share of sounds right, 60% -> 0, 97% -> 100) | 0.529 |
| **tuned (share right + average GOP + worst 20% of sounds)** | **0.557**, average error 0.93 of 10 |
| adults only | **0.659** |
| children only | 0.381 |
| published GOP methods (for comparison) | ~0.6-0.7 (best deep models trained on this data ~0.8) |

- For **adults (our users)** we are in the range of published GOP methods. Children are much harder
  (the phoneme model learned from adult voices).
- `coach/pronunciation.py` now uses the tuned formula and threshold (`WRONG_GOP = -5.25`).

## Single sounds ("you said /v/ instead of /w/")
| threshold | precision | recall | F1 |
|---|---|---|---|
| -2.0 (first guess) | 0.17 | 0.71 | 0.27 |
| **-5.25 (tuned)** | **0.28** | 0.34 | **0.31** |

- PCC of our per-sound GOP with the teachers' sound scores: 0.418.
- Honest limit: about 7 out of 10 sounds we flag were NOT marked wrong by the teachers
  (many are accent-level differences the teachers accepted, or alignment errors). The app should present
  sound feedback as "practise these sounds" (most frequent swaps), not as certain mistakes.

## Fluency
- Our formula (unchanged): PCC **0.485**. It rises steadily with the teachers' fluency score
  (our average 57 / 67 / 76 / 81 for teacher scores <6 / 6-7 / 8 / 9-10).
- Strongest signal: **speed** (syllables per second, PCC +0.51), then average pause (-0.41),
  pause % (-0.38), mid-phrase pauses (-0.38), fillers (-0.31).
- A linear fit on all numbers reached 0.70, but it was **not applied**: these are 3-second read sentences, and
  the fitted weights count events per clip, so they would not carry over to 1-minute free speech.

## Your recordings after tuning
| | Fluency | Grammar | Pronunciation (before -> after) | Overall |
|---|---|---|---|---|
| mumtozkhon_1 | 59 | 60 | 86 -> **81** | 67 |
| mumtozkhon_2 | 56 | 80 | 79 -> **78** | 71 |
| shuhratkhon_4 | 83 | 75 | 97 -> **83** | 80 |

The old formula gave almost-perfect scores too easily (97); the tuned one spreads speakers the way teachers do.

## Ways to improve later
1. Use all 2,500 train sentences and a small learned model on top of GOP features (GOPT-style) -> ~0.65-0.7.
2. Test on spontaneous adult speech (speechocean762 is read speech, Mandarin speakers).
3. Grammar score is still a guess: there is no free teacher-scored spoken grammar set yet.

## Update 2026-11-22: trained pronunciation model (now used by the app)
`training/train_pron.py`, GOPT-style transformer, trained on all 2,500 train sentences
(features: `python -m evaluate.speechocean_eval features train|test 2500`, ~4 h CPU; training ~15 min).
Saved in `models/pron-gopt/model.pt`. Test = 2,500 sentences from other speakers.

| PCC with teachers (test) | simple formula | **trained model** | published GOPT (2022) |
|---|---|---|---|
| single sounds | 0.42 | **0.64** | 0.61 |
| words | n/a | 0.50 | 0.53 |
| sentence accuracy | 0.56 | **0.75** | 0.71 |
| sentence fluency / prosody | n/a | 0.78 / 0.77 | 0.75 / 0.76 |
| total | n/a | **0.76** | 0.74 |

- Wrong-sound detection (threshold 1.1): precision 0.63 (old 0.28), recall 0.43.
- Shown score is stretched like the teachers' scale (average prediction per teacher score: 3-5 -> 5.3, 6 -> 6.5,
  7 -> 7.3, 8 -> 8.2, 9 -> 8.7, 10 -> 8.9). Native speakers (2 NASA videos) now score 94-95; learners 61-84.
- "Sounds to practise" = model-flagged sounds + any swap heard 3+ times (habits such as /th/ -> /z/),
  except swaps native speakers also make (American "on", weak vowels).
- Same speaker, two recordings: ravshanbek 83 / 84, mumtozkhon 80 / 71 (was 86 / 76 with the formula).
