# Speakoff

**Speak for one minute in English and get your scores, your level and a personal coach.**

Speakoff rates an English speaking recording (audio or video, at least 1 minute) and gives:

- **Scores out of 100**: fluency, grammar, vocabulary, pronunciation and overall
- **Level**: CEFR (A1–C2), IELTS Speaking band and TOEFL Speaking score
- **Feedback**: what went well and what to work on, with examples from your own answer, read aloud by an AI voice
- **On camera** score for videos (eye contact, expression, head movement; not part of the level)

All models are free and run on our own server (CPU, or a GPU when there is one).

## Features

- Record in the app or upload a file; videos are turned into small audio files after analysis
- **Ranked 1v1 matches**: two players get the same question, 5 seconds to read it and 30–60 seconds to speak;
  higher score wins. 7 ranks (Copper → Master), monthly seasons, national and global leaderboards
- **Friends**: requests, online status, friendly matches
- **Profile**: photo, frames, skills (one per 20 ranked matches, stacking x1 / x5 / x15), tiered achievements,
  game-style statistics
- **Daily rewards** calendar with Speakoff credits
- **Plans**: Free, Plus and Pro (payments not connected yet)
- **10 languages** for the app, the feedback and the AI voice: English, Korean, Russian, German, Indonesian,
  Uzbek, Chinese, Vietnamese, Hindi, Japanese
- Sign up with email (code), Google or Apple; dark and light themes

## How it works

| Part | Model / tool |
|---|---|
| Speech to text | faster-whisper (`small.en`) |
| Grammar | T5 fine-tuned on learner English (W&I+LOCNESS, FCE) and speech-style data, ERRANT |
| Pronunciation and fluency | wav2vec2 phonemes + a GOPT-style model trained on speechocean762 |
| Vocabulary and level | CEFR word lists, grammar range, repetition checks |
| On camera (video) | MediaPipe face landmarks |
| AI voice | edge-tts |

## Project structure

```
coach/       scoring: transcribe, fluency, grammar, pronunciation, level, feedback, video
server/      Flask API: accounts, recordings, ranked, friends, rewards, credits (see server/README.md)
front_end/   the app's pages: index.html, style.css, script.js, icon.svg
i18n/        all texts in 10 languages
training/    scripts used to train the grammar and pronunciation models
evaluate/    evaluation scripts and results
```

## Run it

Python 3.12.

```
python -m venv .venv
.venv\Scripts\activate          (Windows)   |   source .venv/bin/activate   (macOS / Linux)
pip install -r requirements.txt
python server/app.py
```

Then open **http://localhost:5000**. Email codes, Google / Apple sign-in and other settings: see `server/README.md`.

## Models

The trained models (`models/`, about 3.4 GB) and the training data (`data/`) are **not** in this repository
because of their size. They are needed to run the scoring: `models/grammar-speech-v3` (grammar) and
`models/pron-gopt` (pronunciation / fluency). Whisper and the other public models download by themselves on first run.

## Status

Website version working on a local server. Next: put the server online, then the App Store and Google Play apps.

## Third-party models

The anti-cheat voice check uses [microsoft/wavlm-base-plus-sv](https://huggingface.co/microsoft/wavlm-base-plus-sv)
(Microsoft UniSpeech, CC BY-SA 3.0), run only on our server.

Korean: grammar corrections by [Qwen/Qwen3-1.7B](https://huggingface.co/Qwen/Qwen3-1.7B) (Apache-2.0), morphemes by
[Kiwi](https://github.com/bab2min/kiwipiepy) (LGPL-2.1), word levels from the NIKL / TOPIK vocabulary lists collected in
[combined_korean_vocabulary_list](https://github.com/julienshim/combined_korean_vocabulary_list).
