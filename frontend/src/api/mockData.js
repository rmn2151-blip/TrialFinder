// Mock MatchResponse used for UI development without a live backend.
// Shape mirrors backend/models/trial.py:MatchResponse exactly.
export const MOCK_MATCH_RESPONSE = {
  condition_searched: "Stage 3 non-small cell lung cancer (KRAS G12C)",
  search_context: "Found 12 open trials, ranked top 5 by fit.",
  disclaimer:
    "This information is for educational purposes only and does not constitute medical advice. Always consult with a qualified healthcare provider before making any treatment decisions or enrolling in a clinical trial.",
  trials: [
    {
      rank: 1,
      title:
        "Phase II Study of Adagrasib (MRTX849) in Previously Treated KRAS G12C-Mutated NSCLC",
      nct_id: "NCT04685135",
      phase: "Phase II",
      sponsor: "Memorial Sloan Kettering Cancer Center",
      location: "New York, NY — 2.1 miles away",
      status: "Recruiting",
      fit_score: 92,
      why_this_fits:
        "This trial targets KRAS G12C mutations, which match your tumor's molecular profile. Your prior carboplatin + paclitaxel therapy satisfies the 'previously treated' eligibility requirement, and the primary site is within a few miles of your location.",
      plain_english:
        "This trial tests a once-daily pill that blocks the KRAS G12C protein driving your cancer's growth. Unlike chemotherapy, it's targeted, so most patients have fewer side effects.",
      eligibility_summary:
        "Must have received prior platinum-based chemotherapy. ECOG performance status 0–1. No active, untreated brain metastases.",
      warning_flags: [],
      source_url: "https://clinicaltrials.gov/study/NCT04685135",
      intervention_type: "Drug",
    },
    {
      rank: 2,
      title:
        "Sotorasib Plus Pembrolizumab in KRAS G12C-Mutant Stage III/IV NSCLC",
      nct_id: "NCT04613596",
      phase: "Phase I/II",
      sponsor: "Amgen",
      location: "New York, NY — 5.4 miles away",
      status: "Recruiting",
      fit_score: 84,
      why_this_fits:
        "Combines a KRAS G12C inhibitor with immunotherapy, relevant to your subtype. Your treatment history fits the second-line population this study enrolls. Located near you.",
      plain_english:
        "This study pairs a targeted pill with an immunotherapy drug to see whether the combination shrinks tumors more effectively than either alone.",
      eligibility_summary:
        "Confirmed KRAS G12C mutation. One prior line of systemic therapy allowed. Adequate organ function.",
      warning_flags: ["May require a fresh tumor biopsy before enrollment."],
      source_url: "https://clinicaltrials.gov/study/NCT04613596",
      intervention_type: "Drug",
    },
    {
      rank: 3,
      title:
        "Durvalumab Consolidation After Chemoradiation in Unresectable Stage III NSCLC",
      nct_id: "NCT03833154",
      phase: "Phase III",
      sponsor: "AstraZeneca",
      location: "Newark, NJ — 11.8 miles away",
      status: "Recruiting",
      fit_score: 71,
      why_this_fits:
        "Designed for stage III disease like yours. It does not require a specific mutation, so it's a fallback if molecular-targeted trials don't pan out. Slightly farther from your location.",
      plain_english:
        "This trial uses an immunotherapy infusion after standard chemoradiation to help the immune system keep the cancer from returning.",
      eligibility_summary:
        "Unresectable stage III NSCLC. Completed chemoradiation within the last 6 weeks. No prior immunotherapy.",
      warning_flags: [
        "Excludes patients who have already received PD-1/PD-L1 immunotherapy.",
      ],
      source_url: "https://clinicaltrials.gov/study/NCT03833154",
      intervention_type: "Biological",
    },
    {
      rank: 4,
      title: "Novel Antibody-Drug Conjugate in Pretreated Advanced NSCLC",
      nct_id: "NCT05002270",
      phase: "Phase I",
      sponsor: "Daiichi Sankyo",
      location: "New York, NY — 3.0 miles away",
      status: "Recruiting",
      fit_score: 63,
      why_this_fits:
        "An early-phase option for previously treated NSCLC. Fit is moderate because it's a broad dose-finding study not specific to KRAS G12C, but the site is close and it accepts your prior therapy.",
      plain_english:
        "This first-in-human study tests a drug that delivers chemotherapy directly to cancer cells, aiming to spare healthy tissue.",
      eligibility_summary:
        "Advanced NSCLC after at least one prior therapy. Measurable disease. ECOG 0–1.",
      warning_flags: [
        "Phase I dose-escalation — the optimal dose is still being determined.",
      ],
      source_url: "https://clinicaltrials.gov/study/NCT05002270",
      intervention_type: "Drug",
    },
    {
      rank: 5,
      title: "Exercise and Nutrition Support Program During NSCLC Treatment",
      nct_id: "NCT04866680",
      phase: "N/A",
      sponsor: "NYU Langone Health",
      location: "New York, NY — 4.2 miles away",
      status: "Recruiting",
      fit_score: 48,
      why_this_fits:
        "A supportive-care study rather than a treatment trial. Lower fit for tumor control, but it's local, low-risk, and can be combined with other therapy.",
      plain_english:
        "This program studies whether a structured exercise and nutrition plan improves energy and quality of life during lung cancer treatment.",
      eligibility_summary:
        "Active NSCLC treatment. Able to participate in light physical activity.",
      warning_flags: [],
      source_url: "https://clinicaltrials.gov/study/NCT04866680",
      intervention_type: "Behavioral",
    },
  ],
};
