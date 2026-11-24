# Step 3 Grammar: results (2026-11-19)

## What was done while you were away
1. **3d Fine-tuning**: `python -m training.train_grammar --hours 5.5`
   - Started from vennify/t5-base-grammar-correction and trained on 61,029 W&I + FCE sentence pairs
     (the "speech" version: punctuation/capitals/spelling fixes removed).
   - 1 full epoch = 3,815 steps, **4.3 hours on CPU**. Model saved in `models/grammar-speech-v1/`.
   - Dev loss (lower = better): 0.463 → 0.323 (0.5 h) → 0.297 (1.5 h) → 0.291 (2 h) → 0.284 (3.6 h) → **0.285** (end).
     It improved fast at first and then flattened, so more epochs on CPU won't add much.
2. **3e Comparison** on the benchmark (300 W&I dev sentences the model never saw, same seed for both).
3. **Real recordings test** on your 3 samples (`logs/compare_recordings.log`).
4. `coach/grammar.py` now loads **our model** (it falls back to vennify if `models/` is missing).

## Benchmark (300 sentences)
| | TP | FP (false alarms) | FN (missed) | Precision | Recall | F0.5 |
|---|---|---|---|---|---|---|
| speech: baseline | 64 | 76 | 268 | 0.457 | 0.193 | 0.359 |
| **speech: ours** | **85** | **59** | 247 | **0.590** | **0.256** | **0.468** |
| official: baseline | 130 | 121 | 348 | 0.518 | 0.272 | 0.439 |
| official: ours | 94 | 62 | 384 | 0.603 | 0.197 | 0.426 |

- **Speech** is the score that matters for our app: **+30% F0.5**, with 22% fewer false alarms and 33% more real mistakes caught.
- The official score is a little lower **on purpose**: our model no longer "fixes" commas and capitals
  (in our app those come from Whisper, not the speaker).

## Your recordings
| Sample | Baseline | Ours |
|---|---|---|
| 1 (30 s test) | "a speaking coach" ✓, **"so" ✗ false flag** (cut-off sentence) | "a speaking coach" ✓ |
| 2 (deliberate mistakes) | studying→study ✓, in→at ✓, parts→part ✓ | same 3 ✓ |
| 3 (natural speech) | native→natively ✓, **"-acured" ✗ false flag** (Whisper mis-hearing) | native→natively ✓, "for a speaking coach" ✓, "The second/fourth one is" (correct, but strict for speech) |

Result: **both false flags are gone, and every real mistake is still caught.**

## Still not caught (honest limits)
- "test of recording", "stop myself to generate", "New character all designed": these are harder,
  meaning-level errors. Recall is 0.26, so the model still misses about 3 out of 4 mistakes in essays.
  It is careful rather than complete, which is the safer choice for learners (few false flags).

## How to try it
```
python -m coach.grammar samples/audio_2026-11-19_13-29-20.ogg
python -m evaluate.grammar_eval 300 models/grammar-speech-v1
```

## Options to improve later (optional)
- Train 2–3 epochs on Colab GPU (`training/train_grammar_colab.ipynb`, about 20 min there).
- Try a bigger base model (t5-large / flan-t5-large) on Colab: usually the biggest jump in recall.

## Update 2026-11-20: speech test set (`evaluate/speech_test.tsv`)
216 spoken-style sentences: 133 with typical learner mistakes (145+ mistakes) and 83 correct sentences.
Run: `python -m evaluate.speech_eval [model] [--passes 2] [--show]`

| | mistakes fixed | right place found | correct sentences left alone | false alarms |
|---|---|---|---|---|
| original (vennify) | 65.5% | 66.2% | 98.8% | 3 |
| **ours (grammar-speech-v1)** | **84.4%** | **87.1%** | **98.8%** | 8 |

- Two passes (correcting the model's own output again) changed **nothing** for either model, so that idea is dropped.
- Some of the "misses" are valid alternatives ("I studied at" instead of "I study at", "said to me", "used to getting up").
- What ours still misses: word choice (lent/borrowed, tiring/tired, lately/late), comparatives
  (more tall, most cheap), word order (always is, very like), "The life is", stative verbs (am wanting).
- Caveat: Claude wrote this test set with 1–2 mistakes per sentence, so it's easier than real speech.
  It's still the right tool to compare models. Real recorded speech with teacher corrections would be better
  (Cambridge's Speak & Improve corpus is free but needs a sign-up request).

## Update 2026-11-20: v2
Started from v1 and trained 1 more epoch on `data/grammar/train_mix.tsv` (61k real + 120k synthetic
learner-style mistakes made from Tatoeba by `training/make_synthetic.py`). 11,315 steps, **12.7 h on CPU**.

| | speech test: fixed | found | false alarms | clean ok | perfect | BEA speech F0.5 | BEA official F0.5 |
|---|---|---|---|---|---|---|---|
| original (vennify) | 65.5% | 66.2% | 3 | 98.8% | 66.9% | 0.359 | 0.439 |
| v1 | 84.4% | 87.1% | 8 | 98.8% | 85.7% | 0.468 | 0.426 |
| **v2** | **95.2%** | **95.9%** | **4** | **98.8%** | **95.5%** | **0.502** | **0.454** |

- BEA (real essays, never seen, not made by us) also improved: recall 0.256 -> 0.301 with the same precision (0.60).
  This is the independent check, because the speech test and the synthetic data were both written by Claude.
- Dev loss on FCE essays rose a little (0.285 -> 0.293): expected, the new data is spoken-style.
- Recordings (`logs/compare_recordings_v2.log`, all 7 samples): same real catches as v1, plus it now catches
  "stop myself to generate" -> "from generating" and drops the false "your own" flag. Still strict on
  "The sixth/ninth one is"; one apostrophe-only fix ("countries'") slipped through.
- Still missed on the speech test (7 sentences): borrow/lend, who/that for things, what/who, "it rains" -> "is raining",
  "explained me", "most hardworking" (v2 made it worse: "hardestworking").

## Update 2026-11-22: v3 (now used by `coach/grammar.py`)
Started from v2 and trained 1 epoch on `data/grammar/train_mix_v3.tsv`: 20k new synthetic pairs aimed at v2's misses
(who/which/that, present progressive, "explained me", borrow/lend, teach/learn, long adjectives; cleaned by
`training/filter_v3.py`) + 50k old synthetic + 50k real. 7,497 steps, **8.6 h on CPU**. Dev loss 0.293 -> 0.288.

| | speech test: fixed | found | false alarms | clean ok | perfect | BEA speech F0.5 | BEA official F0.5 |
|---|---|---|---|---|---|---|---|
| v2 | 95.2% | 95.9% | 4 | 98.8% | 95.5% | **0.502** | **0.454** |
| **v3** | **99.3%** | **99.3%** | 4 | 97.6% | **99.2%** | 0.487 | 0.436 |

- The speech test gain is partly expected: the new synthetic data targets exactly the mistake types v2 missed there.
- BEA (independent, written essays) dropped a little (recall 0.301 -> 0.286, precision 0.60 -> 0.59; 300 sentences,
  so this is within noise but not a gain).
- New false alarm on the speech test: "I've been learning English" -> "teaching" (side effect of the teach/learn data).
  Still wrong: "most hardworking" -> "hardestworking".
- Real recordings (`logs/compare_recordings_v3.log`, 104 sentences, 10 differ from v2): v3 better on 5
  ("reply to them", "language abilities", "the chapter", no false tense change on "if you study", "economics grows"),
  worse on 2 ("now I am deliberately", "it's becoming"), 3 are style ("The first/third/ninth one").
- Chosen because the app rates speech and real recordings improved; revert by setting v2 in `coach/grammar.py`.
