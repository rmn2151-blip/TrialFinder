import axios from "axios";
import { MOCK_MATCH_RESPONSE } from "./mockData.js";

// Base URL: in dev, Vite proxies /api -> localhost:8000 (see vite.config.js).
// In production set VITE_API_BASE_URL to the deployed backend origin.
const baseURL = import.meta.env.VITE_API_BASE_URL || "";

// Set VITE_USE_MOCK=true to develop the UI without a running backend.
const USE_MOCK = import.meta.env.VITE_USE_MOCK === "true";

const api = axios.create({
  baseURL,
  // LLM + 3 Linkup calls can take a while; allow 45s before timing out.
  timeout: 45000,
  headers: { "Content-Type": "application/json" },
});

/**
 * POST /api/match
 * @param {Object} patient PatientProfile-shaped payload
 * @returns {Promise<Object>} MatchResponse: { trials, search_context, disclaimer, condition_searched }
 */
export async function matchTrials(patient) {
  if (USE_MOCK) {
    // Simulate network + processing latency so the loading state is visible.
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

/** GET /api/health — used to surface backend availability if needed. */
export async function checkHealth() {
  const { data } = await api.get("/api/health");
  return data;
}

function normalizeError(err) {
  if (err.code === "ECONNABORTED") {
    return new Error(
      "The search took too long. The trial database may be busy — please try again."
    );
  }
  if (err.response) {
    const detail = err.response.data?.detail;
    if (err.response.status === 429) {
      return new Error(
        "You've made several searches in a short window. Please wait a minute and try again."
      );
    }
    return new Error(
      typeof detail === "string"
        ? detail
        : "Something went wrong while searching for trials. Please try again."
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
