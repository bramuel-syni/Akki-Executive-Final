/**
 * agentCyclePreview — Patch 2B.2 Step 3.
 *
 * Deterministic preview generator for the wizard. NO LLM. Receives the
 * user's wizard selections and returns 3–5 bullet strings describing
 * what Agent Cycle will do.
 */
const KIND_LABEL = {
  board_pack:     "Board Pack",
  minutes:        "Minutes",
  committee_pack: "Committee Pack",
  deck:           "Deck",
  report:         "Report",
  briefing:       "Briefing",
};

const CADENCE_LABEL = {
  one_off:   "one-off",
  recurring: "recurring cadence",
  scheduled: "scheduled run",
};

function uniqueKinds(sources) {
  const ks = new Set();
  for (const s of sources) {
    const kind = s?.kind;
    if (!kind) continue;
    ks.add(KIND_LABEL[kind] || kind);
  }
  return [...ks];
}

export function agentCyclePreview({ sources = [], contributors = [], templateName = "Standard",
                                    cadenceKind = "one_off", cadencePayload = {},
                                    formats = [] }) {
  const kinds = uniqueKinds(sources);
  const kindsLabel = kinds.length ? kinds.join(" + ") : "selected sources";
  const formatsLabel = (formats.length ? formats : ["docx"]).map((f) => f.toUpperCase()).join(" + ");
  let cadenceLabel = CADENCE_LABEL[cadenceKind] || "one-off";
  if (cadenceKind === "recurring" && cadencePayload?.interval) {
    cadenceLabel = `${cadencePayload.interval} cadence`;
  } else if (cadenceKind === "scheduled" && cadencePayload?.scheduled_at) {
    try {
      const dt = new Date(cadencePayload.scheduled_at);
      cadenceLabel = `scheduled for ${dt.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })}`;
    } catch { /* keep generic */ }
  }

  const bullets = [
    `Aggregate ${sources.length} source item${sources.length === 1 ? "" : "s"} across ${kindsLabel}.`,
    `Notify ${contributors.length} contributor${contributors.length === 1 ? "" : "s"} before compilation.`,
    `Apply the ${templateName} template.`,
    `Produce ${formatsLabel} output as a ${cadenceLabel}.`,
  ];
  if (cadenceKind !== "one_off") {
    bullets.push("Watch readiness — re-run if any source drops below 80%.");
  }
  return bullets;
}

export default agentCyclePreview;
