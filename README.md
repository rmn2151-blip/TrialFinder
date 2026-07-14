# TrialFinder

Finding the right clinical trial is genuinely hard. clinicaltrials.gov has 500k+ studies and the eligibility criteria read like legal documents. Most people spend hours searching and still end up with a list of trials they don't understand and can't tell if they qualify for.

TrialFinder fixes that. You describe your condition, your treatment history, your location, and your current meds in plain English and it gives you back a ranked shortlist of open trials that actually fit you, with a plain-English explanation of why each one is a match.

Built for the Pfizer Hackathon.

---

## Running TrialFinder on your own computer (beginner-friendly guide)

This guide assumes you have never used a terminal or run code before. Follow it top to bottom and you'll have TrialFinder running on your own machine. It takes about 20-30 minutes the first time.

TrialFinder has two parts that both need to be running at the same time:

- the **backend** (the brain that does the searching and matching)
- the **frontend** (the website you actually see and click on)

You'll open two separate terminal windows, one for each. Keep both open while you use the app.

### Step 1 — Install the tools you'll need (one-time setup)

Before anything else, install these three free programs. Just download and run each installer like any normal app.

1. **Python** (version 3.10 or newer) — runs the backend. Get it from <https://www.python.org/downloads/>. On the first screen of the Windows installer, tick the box that says "Add Python to PATH" before clicking Install.
2. **Node.js** (the "LTS" version) — runs the frontend. Get it from <https://nodejs.org/> and click the big button labelled LTS.
3. **Git** — downloads the project onto your computer. Get it from <https://git-scm.com/downloads> and accept all the default options during install.

Now open your terminal:

- **Mac:** press Cmd+Space, type "Terminal", press Enter.
- **Windows:** press the Start button, type "PowerShell", press Enter.

Type each line below and press Enter after it. If each one prints a version number, you're ready:

```
python --version
node --version
git --version
```

(On some Macs you may need to type `python3 --version` instead of `python`.)

### Step 2 — Download the project

In the same terminal window, copy and paste the lines below one at a time, pressing Enter after each. This downloads TrialFinder into a folder and moves you into it.

```
git clone https://github.com/rmn2151-blip/TrialFinder.git
cd TrialFinder
```

### Step 3 — Start the backend (first terminal window)

Copy and paste these lines one at a time, pressing Enter after each.

```
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

**Windows note:** replace `source venv/bin/activate` with `venv\Scripts\activate`, and replace `cp .env.example .env` with `copy .env.example .env`.

Before you start the backend you need to add two secret keys to the `.env` file you just created (see **Step 5** below). Once that's done, start the backend with:

```
uvicorn main:app --reload
```

Leave this window open. When you see a line mentioning `http://127.0.0.1:8000`, the backend is running.

### Step 4 — Start the frontend (second terminal window)

Open a **new** terminal window (don't close the first one). Then go into the project's frontend folder and start it:

```
cd TrialFinder/frontend
npm install
npm run dev
```

When it finishes, it will show a web address like `http://localhost:5173`. Open that address in your web browser and TrialFinder is now running. The frontend automatically talks to the backend in your first window.

### Step 5 — Add your API keys

TrialFinder needs a couple of keys to work fully. Paste them into the `backend/.env` file you created in Step 3 (open it with any text editor like Notepad or TextEdit):

- `LINKUP_API_KEY` — get one from <https://www.linkup.so/>. This powers the trial search.
- `ANTHROPIC_API_KEY` — get one from <https://console.anthropic.com/>. This powers the AI ranking.
- `JWT_SECRET` — set this to any long random string (it keeps logins secure).
- `RESEND_API_KEY` — optional; only needed if you want email alerts.

> **Just want to try it without paying for API credits?** In `backend/.env`, set `MOCK_LINKUP=true`. The app will use built-in sample data instead of live searches, so you don't need the Linkup or Anthropic keys to click around.

### Step 6 — Use the app

With both windows running, go to `http://localhost:5173` in your browser, fill out the short intake form, and TrialFinder returns your ranked shortlist of trials in about 15-30 seconds.

**To stop the app:** click each terminal window and press Ctrl+C. **To start it again later:** repeat the `uvicorn main:app --reload` command in the backend folder and `npm run dev` in the frontend folder (you don't need to reinstall anything).

### If something goes wrong

- **"command not found"** — the tool from Step 1 isn't installed correctly, or you need to close and reopen the terminal after installing it.
- **The website won't load** — make sure BOTH terminal windows are still running without errors.
- **"port already in use"** — an old copy is still running. Close all terminal windows and start again.
- **Nothing happens after a search** — check your API keys in `backend/.env`, or set `MOCK_LINKUP=true` to test with sample data.

---

## How it works

1. You fill out a short intake form covering your condition, biomarkers, treatments you've tried, where you are, and what medications you're on.
2. The app fires three parallel searches using the Linkup API to pull open trials from clinicaltrials.gov, recent results from related trials, and journal coverage explaining what each trial is actually testing.
3. Claude reads all of that against your profile and ranks the top trials by fit, writing a personalized "why this fits you" explanation for each one.
4. You get a clean list with fit scores, plain-English summaries, eligibility at a glance, and flags for anything that might be a problem.

The whole thing takes about 15-30 seconds.

## Features

**Matching**

- AI ranking with a 0-100 fit score per trial
- biomarker matching (KRAS G12C, HER2+, BRCA1, etc.) weighted as the strongest fit signal
- washout calculator that figures out your earliest possible enrollment date based on your last treatment
- personalized "why this fits you" reasoning that references your specific history
- trust score breakdown showing confidence across eligibility criteria, location, and line of therapy
- excluded trials panel so you can see what got ruled out and why
- falls back to the free ClinicalTrials.gov API automatically when search results are thin

**Your account**

- save trials to a watchlist and get email alerts when a trial status changes
- multi-profile support so caregivers can search for family members (just switch profiles in the header)
- full auth with email and password

**Understanding trials**

- site and PI reputation lookup for each trial card
- plain-English drug briefings for the intervention each trial is testing
- educational pages on what clinical trial phases actually mean and what to expect if you enroll

## Tech stack

- **frontend:** React with Vite
- **backend:** FastAPI (Python)
- **search:** Linkup API (3 parallel queries per patient search)
- **AI ranking:** Anthropic Claude (claude-sonnet-4-6)
- **database:** SQLAlchemy with SQLite (swappable to PostgreSQL via DATABASE_URL)
- **email alerts:** Resend
- **trial data fallback:** ClinicalTrials.gov v2 API (free, no key needed)

## Running tests

```
cd backend
MOCK_LINKUP=true pytest tests/ -v
```

## Project structure

```
TrialFinder/
├── backend/
│   ├── main.py
│   ├── models/
│   ├── services/
│   │   ├── linkup_service.py
│   │   ├── matching_service.py
│   │   ├── llm_service.py
│   │   ├── cache.py
│   │   ├── watchlist_service.py
│   │   └── email_service.py
│   ├── routers/
│   ├── prompts/ranker.txt
│   ├── db/
│   └── tests/
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   ├── components/
│   │   └── api/client.js
│   └── vite.config.js
└── PLAN.md
```

## Deploying

- **backend** to Railway or Render. Set your env vars in the dashboard and point it at `uvicorn main:app --host 0.0.0.0 --port $PORT`.
- **frontend** to Vercel. Set `VITE_API_BASE_URL` to your Railway backend URL.

## A note on API costs

Each patient search costs roughly $0.06-0.12 in Linkup credits (3 queries at standard depth). The caching layer means repeat searches on the same condition and location are free. Use `LINKUP_DEPTH=standard` while testing and switch to `deep` for demos.

---

Built by Ruhani Nagda & Devnah Trivedi
