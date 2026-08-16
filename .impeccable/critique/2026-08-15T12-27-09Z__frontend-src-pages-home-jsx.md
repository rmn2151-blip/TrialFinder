---
target: the homepage (frontend/src/pages/Home.jsx)
total_score: 28
max_score: 40
na_heuristics: 
p0_count: 1
p1_count: 1
timestamp: 2026-08-15T12-27-09Z
slug: frontend-src-pages-home-jsx
---
Method: dual-agent (Assessment A: design review · Assessment B: detector evidence)

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 3 | Step ticker and chat typing indicator are solid; hero CTA's DOM reveal has no transition affordance |
| 2 | Match System / Real World | 3 | Mostly plain-English, but some unexplained clinical jargon (e.g. "ECOG status") leaks through |
| 3 | User Control and Freedom | 3 | Good escape hatches (Back/blank-search), but no way to collapse the form once opened |
| 4 | Consistency and Standards | 3 | Faithful to DESIGN.md tokens except the hero's stat/badge pattern, which breaks the system's own restraint |
| 5 | Error Prevention | 3 | Jumps to first invalid step on submit; no inline validation while typing |
| 6 | Recognition Rather Than Recall | 3 | Concrete placeholders throughout; state persists across steps |
| 7 | Flexibility and Efficiency of Use | 3 | Saved-profile fast path is a genuine expert path; form itself has no bulk-entry shortcuts |
| 8 | Aesthetic and Minimalist Design | 2 | Hero stacks 6 copy blocks before the task starts; stat bar and badges are marked `aria-hidden` by the implementation itself, suggesting even the code treats them as filler |
| 9 | Error Recovery | 3 | Specific, human-readable error copy; chat mode risks leaking raw API error text |
| 10 | Help and Documentation | 2 | "What is a trial?"/"Why participate" exist in nav but nothing contextual on the intake path itself |
| **Total** | | **28/40** | **Good** |

## Design Specificity Verdict

**LLM assessment:** The page is a hybrid — genuinely specific in its task layer, generic in its persuasion layer. `IntakeForm.jsx`'s hint copy ("Biomarker matches are the #1 reason cancer trials accept or reject patients," washout-period explanations, an oncology-specific treatment-history placeholder) could not be dropped into an unrelated product unchanged. But the hero (eyebrow + display headline + subhead + CTA pair + stat bar + trust-badge row) is a stock growth-marketing composition that would work unchanged for a job board or real-estate app with a find-and-replace. Worse, the "500,000+ trials searched" stat is a fabricated usage number that directly contradicts PRODUCT.md's own Evidence on Hand section ("no user-count/outcome claims exist... must not fabricate any of these") — the hero imports a generic-SaaS content pattern (vanity metrics as trust signal) into a product whose actual, documented trust strategy is radical evidence-based transparency.

**Deterministic scan:** `detect.mjs --json frontend/src/pages/Home.jsx` returned **zero findings** (verified clean via a full file read and re-runs bypassing config/advisory filters — genuine zero, not a tooling gap). This doesn't contradict the LLM read: mechanical anti-pattern detection catches AI-slop *tells* (side-tabs, bounce easing, overused fonts), not content-level issues like a fabricated statistic or a hero pattern that's structurally generic but syntactically clean CSS. The two assessments are complementary, not in tension.

**Visual overlays:** Not available — no browser automation tool was exposed in this session, so no live-tab injection or console-based overlay was attempted by either assessment. This report is based entirely on source reading.

## Overall Impression

The intake flow itself is the strongest part of this page — specific, well-hinted, and genuinely built for a stressed, non-clinical reader. The hero above it undercuts that work: it's a template growth-marketing pattern carrying a fabricated stat that violates the product's own documented evidence rules, and it delays the one reassurance (privacy/security) that actually matters at the moment the user is about to type their diagnosis. The single biggest opportunity is making the hero as evidence-specific as the form already is.

## What's Working

1. **Saved-profile fast path** (`searchDirectly`, `Home.jsx`): personalized down to the label ("Search trials for {selected.label}"), skips the form entirely — genuinely low-friction for the caregiver-checking-on-a-parent use case PRODUCT.md names as equally primary.
2. **Domain-grounded hint copy** (`IntakeForm.jsx` field hints): explains *why* each question is asked in real clinical terms (washout period, biomarker match rate) rather than generic form-UX filler — the clearest evidence of product-specific thinking on the page.
3. **Step-ticker implementation**: correctly executes DESIGN.md's pill/circle shape language and green "done" marker — the system's stated philosophy actually shows up here, not just in the doc.

## Priority Issues

**[P0] Fabricated usage stat contradicts the product's own evidence rules**
- **Why it matters:** "500,000+ trials searched" (`Home.jsx`) has no stated source and directly violates PRODUCT.md's explicit rule against inventing user-count claims. Shipping an unverifiable number on the first screen of a product being pitched to Pfizer is a credibility risk, not a cosmetic one.
- **Fix:** Remove it, or replace with something true and sourced today (e.g. "Live data from ClinicalTrials.gov").
- **Suggested command:** `/impeccable harden`

**[P1] No privacy/security reassurance at the point of disclosure**
- **Why it matters:** The first field a user fills in is their condition/diagnosis, but the product's only privacy/security statement lives in the footer — the literal bottom of the page. PRODUCT.md calls this "load-bearing product truth, not legal boilerplate," yet it's positioned exactly like boilerplate.
- **Fix:** Add one line of trust microcopy near the Condition field itself (e.g. "Encrypted, private — visible only to you").
- **Suggested command:** `/impeccable onboard`

**[P2] Hero reads as generic SaaS marketing, undercutting the product's own positioning**
- **Why it matters:** The eyebrow/stat-bar/trust-badge stack is a stock composition that duplicates its own message ("Powered by real-time trial data" and "Real-time trial data" badge say the same thing twice on one screen), pulling the page toward consumer growth-marketing when DESIGN.md positions the product as restrained and evidence-based.
- **Fix:** Drop the redundant eyebrow/badge overlap; replace vanity-style badges with source-grounded statements the product can actually back up.
- **Suggested command:** `/impeccable distill`

**[P2] Mode toggle forces an unexplained decision before the task starts**
- **Why it matters:** "Form intake" vs "Chat with our assistant" appears with zero differentiating copy the moment the form opens — an ambiguous extra fork for someone reading this hours after a diagnosis.
- **Fix:** Add one line clarifying the tradeoff, or demote chat to a lower-weight link rather than a co-equal control.
- **Suggested command:** `/impeccable clarify`

**[P3] Accessibility: hidden trust content + no focus management on reveal**
- **Why it matters:** The three trust badges are wrapped in `aria-hidden="true"` — screen-reader users, who skew toward the "older or less tech-fluent" segment PRODUCT.md names, never hear this reassurance copy at all. Separately, opening the form only scrolls the page; keyboard/AT users must tab past the entire hero again to reach it.
- **Fix:** Remove `aria-hidden` from the badges; move focus into the form's first field/legend after reveal.
- **Suggested command:** `/impeccable harden`

## Persona Red Flags

**Jordan (Confused First-Timer):** Lands on the Form-vs-Chat toggle immediately after "Get started" with no guidance on which to pick — an unexplained fork before the real task. Types a diagnosis into the Condition field with no privacy cue anywhere nearby.

**Morgan (Caregiver, project-specific persona — PRODUCT.md names caregivers as equally primary):** All copy is second-person-singular ("Describe *your* condition," "trials that actually fit *you*"). A caregiver typing on behalf of a parent has to mentally translate every "you" into "my mother," with no acknowledgment on this page that user and patient may differ.

**Sam (Accessibility-Dependent User):** The mode toggle implements `role="tablist"`/`role="tab"` without the expected arrow-key navigation or `aria-controls`/`aria-labelledby` linkage. Combined with the `aria-hidden` trust badges, AT users get materially less reassurance content than sighted users on the exact same page.

## Minor Observations

- "Switch profiles in the header above" is a positional reference that reads oddly once the header stacks under the 720px breakpoint.
- The homepage's short medical-advice disclaimer and the footer's fuller one overlap in substance but are worded differently — worth keeping in sync.
- Medication/biomarker tag inputs accept one item at a time only; no paste-a-list shortcut.
- Inter is declared but never loaded (already flagged in DESIGN.md) — every user sees the system-ui fallback today.

## Questions to Consider

1. Given PRODUCT.md states there's zero real evidence to show today, what would this hero look like if it leaned into that honestly — leading with data provenance and the disclaimer instead of a borrowed SaaS stat bar?
2. If caregivers are truly equally primary, should the homepage open by asking "Who are you searching for — yourself or someone else?" rather than defaulting every string to second-person "you"?
3. Is the Form-vs-Chat toggle serving users, or is it a feature-parity artifact — would a single smart default reduce the first decision a stressed reader has to make?
