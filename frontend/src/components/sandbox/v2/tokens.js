/**
 * Sandbox v2 design tokens — mirror Phase I tokens with the four
 * additional brand surfaces called out in the brief §8.1.
 */
import { TOKEN as PHASE_I, FONT, SUBMODULE_LABELS } from "@/components/solva/flow/tokens";

export const TOKEN = Object.freeze({
  ...PHASE_I,
  // Sandbox v2-only tokens (none yet — the Phase I palette is sufficient).
});

export { FONT, SUBMODULE_LABELS };

/* Brief §3.1 — 7 roles + 'Other'. The label is the user-visible string;
 * the key is what we POST to /api/sandbox/v2/sessions.
 */
export const SANDBOX_V2_ROLES = Object.freeze([
  { key: "ceo",                 label: "CEO" },
  { key: "ned",                 label: "Non-executive director" },
  { key: "company_secretary",   label: "Company Secretary" },
  { key: "exco_member",         label: "Exco / leadership team" },
  { key: "government_executive",label: "Government executive" },
  { key: "regulator",           label: "Regulator" },
  { key: "investor",            label: "Investor" },
  { key: "other",               label: "Other" },
]);

/* Brief §3.1 — 8 org types. */
export const SANDBOX_V2_ORG_TYPES = Object.freeze([
  { key: "bank",             label: "Bank / financial services" },
  { key: "healthcare",       label: "Healthcare / medical" },
  { key: "logistics",        label: "Logistics / supply chain" },
  { key: "saas",             label: "SaaS / technology" },
  { key: "government",       label: "Government / regulator" },
  { key: "pre_ipo",          label: "Pre-IPO / growth-stage" },
  { key: "listed_corporate", label: "Listed corporate" },
  { key: "other",            label: "Other" },
]);

/* The brief's verbatim lead copy on the Welcome screen. */
export const WELCOME_LEAD = (
  "Four quick questions. Then we'll show you Akki working on your "
  + "kind of situation. Four steps — about eight minutes total. You can "
  + "stop at any point."
);
