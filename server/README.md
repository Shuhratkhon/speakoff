# Speakoff website

The website lives in `front_end/` (`index.html`, `style.css`, `script.js`); this `server/` folder runs it.

## Run it on this PC

```
.venv\Scripts\python.exe server\app.py
```

Then open **http://localhost:5000** in Chrome or Edge. In PyCharm you can also open `server/app.py` and press Run.
The first start loads the models (about 1 minute, "models loaded" appears in the window).
The microphone and camera work on `localhost`; on a public server they need HTTPS.

## What is where

| | |
|---|---|
| `server/app.py` | the website's API: sign up / sign in, recordings, results, progress, profile, plans |
| `server/worker.py` | analyses one recording at a time; keeps the audio of each user's last 10 recordings (normal + ranked), results stay |
| `server/plans.py` | plan limits and prices |
| `server/media.py` | file length, video → small audio file |
| `server/mailer.py` | sends sign-up codes by email |
| `server/questions.py` | question of the day + short questions for ranked matches |
| `server/ranked.py` | Ranked 1v1: queue, matches, replay / bot opponents, RP, seasons |
| `server/ranks.py` | the 7 ranks (Copper → Master, 3 divisions each) and 1-month seasons |
| `server/friends.py` | friends: search, requests, online status, friendly challenges (no RP) |
| `server/rewards.py` | 20 skills, achievements, avatar frames, profile statistics |
| `server/data/` | database (`app.db`), recordings, AI-voice files, profile photos — **not** for GitHub |
| `i18n/*.json` | all texts in 10 languages (website + feedback); edit a file and it is used at once |

## Sign-up codes

Without an email account set up, the server is in **test mode**: the code is shown on the page and printed
in the server window. To send real emails (e.g. a Gmail account with an app password), set before starting:

```
$env:SMTP_HOST="smtp.gmail.com"; $env:SMTP_PORT="587"; $env:SMTP_USER="you@gmail.com"; $env:SMTP_PASSWORD="app password"
```

Phone codes stay in test mode until an SMS service (paid per message) is connected.

## Plans

Payments are not connected yet: the Plans page switches plans instantly (test mode).
Real payments (Visa, Mastercard, JCB, UnionPay, Amex) come with the business registration.

## Ranked (1v1)

- Matches a day: Free 3 · Plus 10 · Pro 20 (`server/plans.py`).
- Queue → a player near your rank (the allowed RP gap grows while waiting). Nobody after 20 s → a **replay** of a
  real player's earlier answer to the same question (does not change their RP) or, if there is none, the
  **Speakoff Bot** (half RP).
- Same question for both, 5 s to read, then 30–60 s of speaking. Both answers are scored by the normal models
  (ranked answers go first in the analysis queue). Higher overall wins; < 2 points apart = draw; no answer,
  < 30 s or < 25 English words = loss. RP: Elo-like (K = 40), never below 0.
- Seasons are numbered from launch: Season 1 = November 2026.
- Friendly matches (challenge a friend): same rules, no RP, not in statistics or skills, but they count toward the
  matches a day.
- Ranks: 300 RP each (Copper 0 … Diamond 1500, Master 1800+). Seasons last 1 month; at a new season Copper stays Copper, Bronze-Gold go to Bronze I, Platinum-Master to Gold I. RP per match: ranks.rp_change (higher ranks win and lose less, wins worth 20% more).
- Ranked answers are not kept as audio and do not change the level or the Progress charts.

## Sign in with Google / Apple

The buttons are on the welcome and sign-in screens. Until the IDs below are set, they show "not set up on this
server yet". New Google / Apple users only choose a username (no password; they can set one later in Settings).
A Google / Apple account whose verified e-mail matches an existing account signs into that account.

1. **Google** (free): Google Cloud Console → APIs & Services → Credentials → *Create OAuth client ID* →
   type *Web application*; add the site's address under *Authorised JavaScript origins*
   (e.g. `http://localhost:5000` for testing). Later add the Android and iOS client IDs for the apps.
2. **Apple** (needs the $99/year Apple developer account): Certificates, IDs & Profiles → *Services ID* →
   enable *Sign in with Apple*, register the HTTPS domain and return URL (Apple does not accept localhost).
3. Set before starting the server (PowerShell):

```
$env:GOOGLE_CLIENT_IDS="123-abc.apps.googleusercontent.com"
$env:APPLE_CLIENT_IDS="com.speakoff.signin"; $env:APPLE_REDIRECT_URI="https://your-server-address/"
```
