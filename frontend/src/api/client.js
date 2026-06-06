import axios from "axios";
import { MOCK_MATCH_RESPONSE } from "./mockData.js";

// Base URL: in dev, Vite proxies /api -> localhost:8000 (see vite.config.js).
// In production set VITE_API_BASE_URL to the deployed backend origin.
const baseURL = import.meta.env.VITE_API_BASE_URL || "";

// Set VITE_USE_MOCK=true to develop the results UI without a running backend.
// (Auth/profiles/watchlist still require the real backend.)
const USE_MOCK = import.meta.env.VITE_USE_MOCK === "true";

const TOKEN_KEY = "trialfinder_token";

const api = axios.create({
  baseURL,
  timeout: 45000,
  headers: { "Content-Type": "application/json" },
});

// Attach the JWT (if present) to every request.
api.interceptors.request.use((config) => {
  const token = getToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// ---------------------------------------------------------------------------
// Token storage
// ---------------------------------------------------------------------------

export function getToken() {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* ignore storage errors */
  }
}

// ---------------------------------------------------------------------------
// Matching
// ---------------------------------------------------------------------------

export async function matchTrials(patient) {
  if (USE_MOCK) {
    await new Promise((r) => setTimeout(r, 2500));
    return MOCK_MATCH_RESPONSE;
  }
  try {
    const { data } = await api.post("/api/match", patient);
    return data;
  } catch (err) {
    throw normalizeError(err);
  }
}

export async function checkHealth() {
  const { data } = await api.get("/api/health");
  return data;
}

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

export async function register(email, password) {
  try {
    const { data } = await api.post("/api/auth/register", { email, password });
    return data; // { access_token, token_type, account }
  } catch (err) {
    throw normalizeError(err);
  }
}

export async function login(email, password) {
  try {
    const { data } = await api.post("/api/auth/login", { email, password });
    return data;
  } catch (err) {
    throw normalizeError(err);
  }
}

export async function fetchMe() {
  const { data } = await api.get("/api/auth/me");
  return data; // { id, email, created_at }
}

// ---------------------------------------------------------------------------
// Profiles
// ---------------------------------------------------------------------------

export async function listProfiles() {
  const { data } = await api.get("/api/profiles");
  return data; // [ProfileOut]
}

export async function createProfile(profile) {
  try {
    const { data } = await api.post("/api/profiles", profile);
    return data;
  } catch (err) {
    throw normalizeError(err);
  }
}

export async function deleteProfile(profileId) {
  await api.delete(`/api/profiles/${profileId}`);
}

// ---------------------------------------------------------------------------
// Watchlist
// ---------------------------------------------------------------------------

export async function addToWatchlist({ profile_id, nct_id, title, source_url }) {
  try {
    const { data } = await api.post("/api/watchlist", {
      profile_id,
      nct_id,
      title,
      source_url,
    });
    return data;
  } catch (err) {
    throw normalizeError(err);
  }
}

export async function getWatchlist(profileId) {
  const { data } = await api.get("/api/watchlist", {
    params: { profile_id: profileId },
  });
  return data; // { profile_id, trials: [...] }
}

export async function removeFromWatchlist(watchId) {
  await api.delete(`/api/watchlist/${watchId}`);
}

export async function updateWatchlistStatus(watchId, status) {
  try {
    const { data } = await api.put(`/api/watchlist/${watchId}/status`, { status });
    return data;
  } catch (err) {
    throw normalizeError(err);
  }
}

export async function getTrialResults(nctId, title = "") {
  try {
    const { data } = await api.get(`/api/results/${nctId}`, { params: { title } });
    return data;
  } catch (err) {
    throw normalizeError(err);
  }
}

// ---------------------------------------------------------------------------
// Doctor briefing PDF
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Conversational intake
// ---------------------------------------------------------------------------

export async function startIntakeSession() {
  if (USE_MOCK) {
    return {
      session_id: "mock-" + Math.random().toString(36).slice(2, 10),
      question:
        "To help me find the right trials for you, I'll ask a few short questions. To start: what condition or diagnosis are you looking for trials for?",
    };
  }
  try {
    const { data } = await api.post("/api/intake/start");
    return data;
  } catch (err) {
    throw normalizeError(err);
  }
}

// Deterministic mock follow-up script for use without a backend.
const MOCK_INTAKE_SCRIPT = [
  "Where are you located (city, state, or ZIP)?",
  "What treatments have you already tried, if any?",
  "Any biomarker or genomic test results (e.g. KRAS G12C+, HER2+)? Type 'none' if not applicable.",
  "How old are you? Or type 'skip'.",
  "Any current medications? List them separated by commas, or 'none'.",
];

export async function submitIntakeAnswer(sessionId, answer, prior = []) {
  if (USE_MOCK) {
    const turn = prior.length;
    if (turn >= MOCK_INTAKE_SCRIPT.length) {
      const [condition, location, treatmentHistory, biomarkers, age, medications] = [
        prior[0] || "",
        prior[1] || "",
        prior[2] || "",
        prior[3] || "",
        prior[4] || "",
        answer || "",
      ];
      const profile = { condition, location };
      if (treatmentHistory && !/^none|skip$/i.test(treatmentHistory))
        profile.treatment_history = treatmentHistory;
      if (biomarkers && !/^none|skip$/i.test(biomarkers))
        profile.biomarkers = biomarkers.split(",").map((s) => s.trim()).filter(Boolean);
      const n = parseInt(age, 10);
      if (!isNaN(n)) profile.age = n;
      if (medications && !/^none|skip$/i.test(medications))
        profile.medications = medications.split(",").map((s) => s.trim()).filter(Boolean);
      return { session_id: sessionId, question: null, complete: true, profile, turns_so_far: turn + 1 };
    }
    return {
      session_id: sessionId,
      question: MOCK_INTAKE_SCRIPT[turn],
      complete: false,
      profile: null,
      turns_so_far: turn + 1,
    };
  }
  try {
    const { data } = await api.post("/api/intake/answer", {
      session_id: sessionId,
      answer,
    });
    return data;
  } catch (err) {
    throw normalizeError(err);
  }
}

// ---------------------------------------------------------------------------
// Ambiguity resolution (clarify)
// ---------------------------------------------------------------------------

const MOCK_CLARIFY_SCRIPT = [
  { question: "Are you currently taking any blood thinners or anticoagulants?" },
  { question: "Have you had any cancer treatment in the last 4 weeks?" },
  {
    verdict: "eligible",
    reason:
      "Based on your answers, you appear to meet the trial's washout and concomitant-medication criteria. Confirm with the study team.",
  },
];

export async function clarifyEligibility({ patient, trial, history }) {
  if (USE_MOCK) {
    await new Promise((r) => setTimeout(r, 600));
    const step = MOCK_CLARIFY_SCRIPT[history.length] || {
      verdict: "stop",
      reason: "Need confirmation from the study team.",
    };
    if (step.question) {
      return {
        verdict: "ask",
        question: step.question,
        remaining: MOCK_CLARIFY_SCRIPT.length - history.length - 1,
      };
    }
    return { verdict: step.verdict || "stop", reason: step.reason };
  }
  try {
    const { data } = await api.post("/api/clarify", { patient, trial, history });
    return data;
  } catch (err) {
    throw normalizeError(err);
  }
}

export async function downloadBriefingPdf(patient, match) {
  try {
    const response = await api.post(
      "/api/briefing/pdf",
      { patient, match },
      { responseType: "blob" }
    );
    const blob = new Blob([response.data], { type: "application/pdf" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "trialfinder-briefing.pdf";
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  } catch (err) {
    throw normalizeError(err);
  }
}

// ---------------------------------------------------------------------------
// Reputation (site / PI lookup)
// ---------------------------------------------------------------------------

const MOCK_REPUTATION = {
  sponsor: "Memorial Sloan Kettering Cancer Center",
  pi: null,
  summary: "Major academic cancer center with deep KRAS G12C trial experience.",
  hospital_reputation:
    "Memorial Sloan Kettering is one of the largest and oldest cancer centers in the United States and is consistently ranked among the top two cancer hospitals in U.S. News & World Report. It runs an active portfolio of early-phase oncology trials, including KRAS G12C-targeted studies.",
  publications: [
    {
      title: "Adagrasib in KRAS G12C–Mutated Non–Small-Cell Lung Cancer",
      url: "https://www.nejm.org/doi/full/10.1056/NEJMoa2204619",
      year: "2022",
    },
    {
      title: "KRAS G12C inhibition with sotorasib in advanced NSCLC",
      url: "https://www.nejm.org/doi/full/10.1056/NEJMoa2103695",
      year: "2021",
    },
  ],
  recent_press: [
    {
      title: "MSK opens new precision oncology unit for KRAS-targeted therapies",
      url: "https://www.mskcc.org/news/example",
      snippet:
        "The center announced a dedicated unit focused on KRAS G12C and other targeted therapies.",
      date: "2025-03",
    },
  ],
  sources: [
    { label: "MSKCC official", url: "https://www.mskcc.org/" },
    {
      label: "U.S. News Best Hospitals",
      url: "https://health.usnews.com/best-hospitals",
    },
  ],
  cached: false,
};

const MOCK_DRUG_INTEL = {
  drug: "sotorasib",
  summary:
    "Sotorasib is a covalent KRAS G12C inhibitor — a once-daily oral pill that locks the mutant KRAS protein in its inactive state. It's the first generation of targeted therapies for the ~13% of lung adenocarcinomas driven by KRAS G12C.",
  side_effect_signals:
    "Most-reported issues are liver enzyme elevations, fatigue, GI side effects, and occasional pneumonitis. Grade 3+ events in roughly 1 in 5 patients.",
  phase_results: [
    {
      phase: "Phase II",
      summary: "CodeBreaK 100: 37.1% ORR, median PFS 6.3 months in pretreated KRAS G12C NSCLC.",
      url: "https://www.nejm.org/doi/full/10.1056/NEJMoa2103695",
    },
    {
      phase: "Phase III",
      summary: "CodeBreaK 200: superior PFS vs docetaxel (5.6 vs 4.5 months).",
      url: "https://www.thelancet.com/example",
    },
  ],
  conference_signals: [
    {
      conference: "ASCO 2025",
      finding: "KRYSTAL-7: adagrasib + pembrolizumab in 1L NSCLC, ORR 63%.",
      url: "https://ascopubs.org/example",
    },
  ],
  fda_designations: [
    {
      label: "Breakthrough Therapy designation for KRAS G12C+ NSCLC",
      date: "2021",
      url: "https://www.fda.gov/example",
    },
  ],
  sources: [],
  cached: false,
};

export async function getDrugIntel(drug) {
  if (USE_MOCK) {
    await new Promise((r) => setTimeout(r, 600));
    return { ...MOCK_DRUG_INTEL, drug: drug || MOCK_DRUG_INTEL.drug };
  }
  try {
    const { data } = await api.get("/api/drug-intel", { params: { drug } });
    return data;
  } catch (err) {
    throw normalizeError(err);
  }
}

export async function getReputation(sponsor, pi = null) {
  if (USE_MOCK) {
    await new Promise((r) => setTimeout(r, 700));
    return { ...MOCK_REPUTATION, sponsor: sponsor || MOCK_REPUTATION.sponsor };
  }
  try {
    const { data } = await api.get("/api/reputation", {
      params: pi ? { sponsor, pi } : { sponsor },
    });
    return data;
  } catch (err) {
    throw normalizeError(err);
  }
}

// ---------------------------------------------------------------------------
// Errors
// ---------------------------------------------------------------------------

function normalizeError(err) {
  if (err.code === "ECONNABORTED") {
    return new Error(
      "The request took too long. The server may be busy — please try again."
    );
  }
  if (err.response) {
    const detail = err.response.data?.detail;
    if (err.response.status === 429) {
      return new Error(
        "You've made several requests in a short window. Please wait a minute and try again."
      );
    }
    if (err.response.status === 401) {
      return new Error(
        typeof detail === "string" ? detail : "Please log in to continue."
      );
    }
    return new Error(
      typeof detail === "string"
        ? detail
        : "Something went wrong. Please try again."
    );
  }
  if (err.request) {
    return new Error(
      "Couldn't reach the server. Check your connection and make sure the backend is running."
    );
  }
  return new Error("An unexpected error occurred. Please try again.");
}

export default api;
