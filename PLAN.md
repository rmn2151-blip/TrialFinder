# TrialFinder — Build Plan
**Hackathon: Linkup | Deadline: ~6 days | Stack: React + FastAPI + Python**

---

## What We're Building

A web app where a patient describes their condition, treatment history, location, and current medications — and gets back a ranked shortlist of open clinical trials with plain-English "why this fits you" reasoning. Powered by Linkup's search API to pull live trial data, recent results, and journal coverage.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                  React Frontend                      │
│  PatientIntakeForm → LoadingState → ResultsPage      │
└───────────────────────┬─────────────────────────────┘
                        │ POST /api/match
┌───────────────────────▼─────────────────────────────┐
│                FastAPI Backend                       │
│                                                      │
│  /api/match  →  MatchingService                      │
│                     │                               │
│            ┌────────▼────────┐                      │
│            │  Linkup Search  │  ← pulls open trials │
│            │  (3 queries)    │    results, journals  │
│            └────────┬────────┘                      │
│                     │                               │
│            ┌────────▼────────┐                      │
│            │  LLM Ranker     │  ← Claude/GPT-4o     │
│            │  (structured    │    structured output  │
│            │   output)       │                      │
│            └────────┬────────┘                      │
│                     │                               │
│            ┌────────▼────────┐                      │
│            │  Response       │  → ranked trials     │
│            │  Formatter      │    with reasoning    │
│            └─────────────────┘                      │
└─────────────────────────────────────────────────────┘
```

### Key API Calls Per User Request

1. **Linkup query 1** — open trials: `"open clinical trials [condition] [year]"`
2. **Linkup query 2** — recent results: `"clinical trial results [condition] 2024 2025"`
3. **Linkup query 3** — journal coverage: `"[condition] trial mechanism plain english"`
4. **LLM call** — rank + generate "why this fits you" reasoning from aggregated results

**Estimated Linkup cost per request:** ~$0.06–0.12 → your $20 budget covers ~170–330 searches. Plenty for a hackathon demo.

---

## Folder Structure

```
trial-finder/
├── backend/
│   ├── main.py                  # FastAPI app entry point
│   ├── routers/
│   │   └── match.py             # /api/match endpoint
│   ├── services/
│   │   ├── linkup_service.py    # Linkup API wrapper
│   │   ├── matching_service.py  # Orchestration logic
│   │   └── llm_service.py       # LLM ranking + reasoning
│   ├── models/
│   │   ├── patient.py           # PatientProfile pydantic model
│   │   └── trial.py             # Trial + RankedTrial models
│   ├── prompts/
│   │   └── ranker.txt           # LLM ranking prompt template
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── IntakeForm.jsx
│   │   │   ├── ResultsPage.jsx
│   │   │   ├── TrialCard.jsx
│   │   │   ├── LoadingState.jsx
│   │   │   └── Header.jsx
│   │   ├── pages/
│   │   │   ├── Home.jsx
│   │   │   └── Results.jsx
│   │   ├── api/
│   │   │   └── client.js        # axios wrapper
│   │   ├── App.jsx
│   │   └── main.jsx
│   ├── index.html
│   ├── vite.config.js
│   └── package.json
├── docker-compose.yml           # optional, for deployment
└── README.md
```

---

## Builder Split

### Builder A — Backend & AI (Python/FastAPI)
### Builder B — Frontend & UX (React)

These tracks run **mostly in parallel** after Day 1 setup. They converge on Day 4 for integration.

---

## Day-by-Day Timeline

### Day 1 (Thursday) — Setup & Contracts
**Both builders together (~2 hrs)**

- [ ] Create GitHub repo, set up monorepo structure above
- [ ] Builder A: `cd backend && python -m venv venv && pip install fastapi uvicorn httpx python-dotenv anthropic pydantic`
- [ ] Builder B: `cd frontend && npm create vite@latest . -- --template react && npm install axios react-router-dom`
- [ ] Define and agree on the **API contract** (the JSON shape that backend sends to frontend) — paste it in a shared `CONTRACT.md` so both can work independently
- [ ] Both get Linkup API keys + LLM API keys in `.env`

**API Contract to agree on:**
```json
POST /api/match
Request:
{
  "condition": "stage 3 non-small cell lung cancer",
  "treatment_history": "carboplatin + paclitaxel, 6 cycles",
  "location": "New York, NY",
  "medications": ["metformin", "lisinopril"],
  "age": 58,
  "additional_context": "..."
}

Response:
{
  "trials": [
    {
      "rank": 1,
      "title": "Phase II Trial of...",
      "nct_id": "NCT12345678",
      "phase": "Phase II",
      "sponsor": "Memorial Sloan Kettering",
      "location": "New York, NY — 2.1 miles away",
      "status": "Recruiting",
      "fit_score": 92,
      "why_this_fits": "This trial targets KRAS G12C mutations, which are common in your cancer subtype. Your prior platinum-based therapy matches the 'previously treated' eligibility requirement. The trial site is near you.",
      "plain_english": "This trial is testing a new pill that blocks a specific protein that helps your cancer grow. Unlike chemo, it's targeted — meaning fewer side effects for most patients.",
      "source_url": "https://clinicaltrials.gov/...",
      "eligibility_summary": "Must have received prior platinum therapy. ECOG 0-1. No active brain mets.",
      "warning_flags": []
    }
  ],
  "search_context": "Found 12 open trials, ranked top 5",
  "disclaimer": "This is not medical advice..."
}
```

---

### Day 2 (Friday) — Core Backend

**Builder A tasks:**

#### Task A1 — Linkup Service (`linkup_service.py`)
Build the wrapper around Linkup's search API. For each patient query, fire 3 targeted searches:

```python
async def search_trials(condition: str, location: str) -> list[dict]:
    # Query 1: open recruiting trials
    q1 = f'site:clinicaltrials.gov "{condition}" "recruiting" open trial 2024 2025'
    
    # Query 2: recent trial results/news
    q2 = f'"{condition}" clinical trial results efficacy 2024 2025'
    
    # Query 3: mechanism explained
    q3 = f'"{condition}" clinical trial how it works mechanism treatment'
    
    results = await asyncio.gather(
        linkup_search(q1), linkup_search(q2), linkup_search(q3)
    )
    return aggregate(results)
```

Use `httpx.AsyncClient` for async HTTP. Linkup's API endpoint: `https://api.linkup.so/v1/search` with `Authorization: Bearer {key}` and body `{"q": "...", "depth": "deep", "outputType": "sourcedAnswer"}`.

**Deliverable:** `linkup_service.py` with unit test using mocked responses.

---

#### Task A2 — LLM Ranking Service (`llm_service.py`)
Take the raw Linkup search output + patient profile → return structured ranked trials.

Prompt strategy (in `prompts/ranker.txt`):
```
You are a clinical trial matching assistant. Given a patient profile and raw search results about clinical trials, extract and rank the top 5 most relevant trials.

Patient Profile:
{patient_json}

Raw Search Results:
{linkup_results}

For each trial, output a JSON array with fields: title, nct_id, phase, sponsor, location, status, fit_score (0-100), why_this_fits (2-3 sentences personalized to this patient), plain_english (1-2 sentences explaining what the trial is actually testing), eligibility_summary, warning_flags.

Rank by fit_score descending. Only include trials with status "Recruiting" or "Enrolling by Invitation".
```

Use Claude's `response_format` structured output or JSON mode. Fall back to GPT-4o-mini if over budget.

**Deliverable:** `llm_service.py`, tested with a sample patient + sample Linkup response.

---

#### Task A3 — FastAPI Endpoint (`routers/match.py` + `main.py`)
Wire services together. Add CORS for localhost:5173 (Vite dev port).

```python
@router.post("/api/match", response_model=MatchResponse)
async def match_trials(patient: PatientProfile):
    raw_results = await linkup_service.search_trials(patient.condition, patient.location)
    ranked = await llm_service.rank_and_reason(patient, raw_results)
    return MatchResponse(trials=ranked, disclaimer=DISCLAIMER_TEXT)
```

Add a `/api/health` endpoint for frontend to ping. Add basic rate limiting (slowapi) to protect your $20 budget.

**Deliverable:** `uvicorn main:app --reload` runs cleanly, curl test returns valid JSON.

---

### Day 2 (Friday) — Core Frontend

**Builder B tasks (runs in parallel with A):**

#### Task B1 — Patient Intake Form (`IntakeForm.jsx`)
Multi-step form with 4 sections. Use React state (no library needed at this scale):

- **Step 1:** Condition — free text + optional "common conditions" quick-pick chips (Lung Cancer, Breast Cancer, Leukemia, Crohn's, etc.)
- **Step 2:** Treatment history — free text area ("What treatments have you tried?")
- **Step 3:** Location + Age — zip code or city, age input
- **Step 4:** Current medications — tag input (type med name, press Enter to add)

Add a "Tell us more" optional textarea at the end.

Progress bar at top. "Find Trials" CTA button.

**Deliverable:** Form renders cleanly, captures all fields, calls `onSubmit(patientData)` prop with the right shape.

---

#### Task B2 — Results Page (`ResultsPage.jsx` + `TrialCard.jsx`)
Use the mock API contract from Day 1 to build this before the real backend exists.

`TrialCard.jsx` should show:
- Rank badge + fit score (colored: green 80+, yellow 60-79, gray <60)
- Trial title + NCT ID (linked to clinicaltrials.gov)
- Phase pill + Status pill (Recruiting = green)
- **"Why this fits you"** — highlighted box, this is the hero feature
- **"What they're testing"** — plain English summary
- Location + distance
- Eligibility summary (collapsible)
- Warning flags (if any, shown in amber)

`ResultsPage.jsx`:
- Header with patient's condition + "X trials found"
- Sort controls (by fit score, by distance, by phase)
- List of TrialCards
- Sticky disclaimer footer

**Deliverable:** ResultsPage renders correctly with hardcoded mock data matching the API contract.

---

#### Task B3 — Loading State + Error Handling (`LoadingState.jsx`)
The gap between form submit and results returning (~5-15 seconds for 3 Linkup calls + LLM) needs a good UX.

Build an animated loading state that cycles through status messages:
- "Searching 500,000+ clinical trials..."
- "Reading recent trial results..."
- "Analyzing eligibility criteria..."
- "Generating personalized matches..."

Use a simple CSS animation or Tailwind animate-pulse. This makes the wait feel productive.

Also handle: network error state, empty results state ("No trials found — try broadening your condition description").

**Deliverable:** LoadingState renders, cycles messages, ErrorState shows a friendly message.

---

### Day 3 (Saturday) — Polish & Depth

**Builder A:**

#### Task A4 — Smarter Search Queries
Improve Linkup query construction to be more targeted:
- Extract condition synonyms (e.g., "NSCLC" for lung cancer) using the LLM before searching
- Add location-aware queries ("New York clinical trial [condition]")
- Filter Linkup results to prioritize clinicaltrials.gov URLs
- Parse NCT IDs from results to deduplicate trials

#### Task A5 — Caching Layer
Add simple in-memory caching (or Redis if time allows) so identical condition+location queries don't burn Linkup credits. Use a hash of the patient profile as cache key. Cache for 1 hour.

```python
from functools import lru_cache
# or use a simple dict + timestamp
_cache: dict[str, tuple[float, Any]] = {}
```

---

**Builder B:**

#### Task B4 — Home Page Design (`Home.jsx`)
The landing page before the form. Should convey trust and purpose quickly:
- Headline: **"Find clinical trials that actually fit you"**
- Subheadline: "Describe your condition in plain English. We'll match you to recruiting trials and explain why each one might be right for you."
- Stats: "500,000+ trials searched • Updated daily • Free to use"
- Prominent "Get Started" button → scrolls to / routes to form
- Small trust badges: "Powered by real-time trial data"

#### Task B5 — Responsive + Accessibility
- Mobile-responsive layout (trials stack on mobile)
- Keyboard navigation for form
- ARIA labels on interactive elements
- Color contrast check on fit score badges

---

### Day 4 (Sunday) — Integration Day

**Both builders together:**

- [ ] Replace mock data in frontend with real API calls (`src/api/client.js`)
- [ ] Test the full flow end-to-end with 3-4 real patient profiles
- [ ] Debug CORS, timeout issues (set 30s timeout on frontend for LLM calls)
- [ ] Tune LLM prompt based on real output quality
- [ ] Add `.env.example`, update README with setup instructions

**Test patient profiles to use:**
1. Stage 3 NSCLC, prior chemo, New York
2. Metastatic breast cancer (HER2+), no prior targeted therapy, San Francisco
3. Crohn's disease, failed biologics, Chicago
4. Rare disease: amyloidosis, Boston

---

### Day 5 (Monday) — Deployment & Demo Prep

#### Deployment (Builder A)
- **Backend:** Deploy to Railway.app or Render.com (free tier, FastAPI works out of the box)
  ```
  # Procfile or railway.json
  web: uvicorn main:app --host 0.0.0.0 --port $PORT
  ```
- **Frontend:** Deploy to Vercel (`vercel --prod` from frontend dir)
- Set environment variables in both platforms
- Test deployed version with real patient profiles

#### Demo Prep (Builder B)
- Record a Loom walkthrough (2-3 min) showing a real search
- Write a compelling README with screenshots
- Prepare 2-3 "wow" demo cases (cancer patients where the matching is clearly useful)
- Add the disclaimer / "not medical advice" language prominently

---

### Day 6 (Tuesday) — Buffer + Submission

- Fix any last-minute bugs from user testing
- Submit to Linkup Hackathon with README, demo link, Loom
- Share on LinkedIn/Twitter for bonus visibility

---

## API Budget Plan ($20 Linkup)

| Usage | Cost estimate |
|-------|---------------|
| Development & testing (50 searches) | ~$3–5 |
| Integration testing (20 searches) | ~$1–2 |
| Demo day / judges testing (30 searches) | ~$2–4 |
| Buffer | ~$9–14 |

**Tips to stretch the budget:**
- Cache by condition+location hash (saves 80% of repeat queries)
- In dev, mock Linkup with saved responses (`MOCK_LINKUP=true` env flag)
- Use `depth: "standard"` instead of `"deep"` during development; switch to `"deep"` for demos

---

## Risk Register

| Risk | Mitigation |
|------|------------|
| Linkup doesn't return enough trial-specific results | Supplement with direct ClinicalTrials.gov API (free, no key needed): `https://clinicaltrials.gov/api/v2/studies?query.cond=...` |
| LLM produces hallucinated trial data | Always include source URLs; show "sourced from" on each card; add disclaimer |
| Too slow for live demo (15s+) | Show animated loading state; pre-generate 3-4 demo results and cache them |
| LLM budget runs out | Use GPT-4o-mini (~10x cheaper) for ranking; reserve better model for "why this fits" copy |
| Not enough time for full UI | Ship the form + results as a single-page app; skip Home page polish if needed |

---

## Nice-to-Haves (if time permits)

- **Email results** — let user enter email and send the shortlist as a PDF
- **Save & compare** — bookmark trials across sessions (localStorage)
- **Filter sidebar** — filter by phase, distance, intervention type
- **"Ask a follow-up"** — chatbot to answer "what does ECOG status mean?" inline
- **ClinicalTrials.gov deep link** — auto-populate the official CT.gov search with their criteria

---

## Quick Reference

| Thing | Where |
|-------|-------|
| Linkup API docs | https://docs.linkup.so |
| ClinicalTrials.gov API | https://clinicaltrials.gov/data-api/api |
| FastAPI docs | https://fastapi.tiangolo.com |
| Vite + React setup | https://vitejs.dev/guide |
| Deploy backend | https://railway.app |
| Deploy frontend | https://vercel.com |
