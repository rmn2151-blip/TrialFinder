# TrialFinder

finding the right clinical trial is genuinely hard. clinicaltrials.gov has 500k+ studies and the eligibility criteria read like legal documents. most people spend hours searching and still end up with a list of trials they don't understand and can't tell if they qualify for.

TrialFinder fixes that. you describe your condition, your treatment history, your location, and your current meds in plain english and it gives you back a ranked shortlist of open trials that actually fit you, with a plain english explanation of why each one is a match.

built for the Linkup Hackathon.

---

## how it works

1. you fill out a short intake form covering your condition, biomarkers, treatments you've tried, where you are, and what medications you're on
2. the app fires three parallel searches using the Linkup API to pull open trials from clinicaltrials.gov, recent results from related trials, and journal coverage explaining what each trial is actually testing
3. Claude reads all of that against your profile and ranks the top trials by fit, writing a personalized "why this fits you" explanation for each one
4. you get a clean list with fit scores, plain english summaries, eligibility at a glance, and flags for anything that might be a problem

the whole thing takes about 15-30 seconds.

---

## features

**matching**
- AI ranking with a 0-100 fit score per trial
- biomarker matching (KRAS G12C, HER2+, BRCA1, etc) weighted as the strongest fit signal
- washout calculator that figures out your earliest possible enrollment date based on your last treatment
- personalized "why this fits you" reasoning that references your specific history
- trust score breakdown showing confidence across eligibility criteria, location, and line of therapy
- excluded trials panel so you can see what got ruled out and why
- falls back to the free ClinicalTrials.gov API automatically when search results are thin

**your account**
- save trials to a watchlist and get email alerts when a trial status changes
- multi-profile support so caregivers can search for family members (just switch profiles in the header)
- full auth with email and password

**understanding trials**
- site and PI reputation lookup for each trial card
- plain english drug briefings for the intervention each trial is testing
- educational pages on what clinical trial phases actually mean and what to expect if you enroll

---

## tech stack

- frontend: React with Vite
- backend: FastAPI (Python)
- search: Linkup API (3 parallel queries per patient search)
- AI ranking: Anthropic Claude claude-sonnet-4-6
- database: SQLAlchemy with SQLite (swappable to PostgreSQL via DATABASE_URL)
- email alerts: Resend
- trial data fallback: ClinicalTrials.gov v2 API (free, no key needed)

---

## getting started

**backend**

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --reload
```

**frontend**

```bash
cd frontend
npm install
npm run dev
```

the frontend dev server runs on localhost:5173 and proxies API requests to localhost:8000.

**environment variables**

copy backend/.env.example and fill these in

```
LINKUP_API_KEY=your_linkup_key
ANTHROPIC_API_KEY=your_anthropic_key
MOCK_LINKUP=false
LINKUP_DEPTH=standard
JWT_SECRET=something_random
RESEND_API_KEY=optional_for_email_alerts
```

set MOCK_LINKUP=true during development to skip real Linkup calls and use fixture data. this saves your API credits while building.

**running tests**

```bash
cd backend
MOCK_LINKUP=true pytest tests/ -v
```

---

## project structure

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

---

## deploying

**backend** to Railway or Render. set your env vars in the dashboard and point it at

```
uvicorn main:app --host 0.0.0.0 --port $PORT
```

**frontend** to Vercel. set VITE_API_BASE_URL to your Railway backend URL.

---

## a note on API costs

each patient search costs roughly $0.06-0.12 in Linkup credits (3 queries at standard depth). the caching layer means repeat searches on the same condition and location are free. use LINKUP_DEPTH=standard while testing and switch to deep for demos.

---

built by Ruhani Nagda
