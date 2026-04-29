/**
 * EnterpriseFeature — full-bleed navy band positioning the Decks + Reports
 * Studio surface as the enterprise differentiator.
 *
 * Includes a live sensitivity demo: paste any board-pack snippet and the
 * regex scorer returns a classification + reasons in real time. Powered by
 * /api/public/studio/sensitivity-demo (no auth, IP rate-limited).
 *
 * iter65 — design brief specifies full-bleed #0A1F44 background with cream
 * text and high-contrast layout to signal Enterprise security visually.
 */
import React, { useState, useRef } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Loader2, Sparkles, ArrowRight, ShieldCheck, Eye } from "lucide-react";

const NAVY = "#0A1F44";
const CREAM = "#F7F3EA";
const OXBLOOD = "#8B2E2B";

const CLASSIFICATION_TONE = {
  public:       { ring: "#10B981", chip: "bg-emerald-500/20 text-emerald-200 border-emerald-400/40" },
  internal:     { ring: "#F59E0B", chip: "bg-amber-500/20 text-amber-200 border-amber-400/40" },
  confidential: { ring: "#F97316", chip: "bg-orange-500/20 text-orange-200 border-orange-400/40" },
  restricted:   { ring: "#EF4444", chip: "bg-red-500/20 text-red-200 border-red-400/40" },
};

const SAMPLE_TEXT =
  "Q3 board pack draft — preliminary view: Whilst the executive team has " +
  "framed the customer-concentration story as macro-driven, the data " +
  "suggests a structural gap. We anticipate fines from the regulator " +
  "in the next quarter and are evaluating a £45m bolt-on acquisition.";

const API_BASE = process.env.REACT_APP_BACKEND_URL || "";

export default function EnterpriseFeature() {
  const [text, setText] = useState("");
  const [scoring, setScoring] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const debounceRef = useRef(null);

  const score = async (snippet) => {
    if (!snippet || snippet.length < 4) {
      setResult(null);
      return;
    }
    setScoring(true);
    setError("");
    try {
      const r = await fetch(`${API_BASE}/api/public/studio/sensitivity-demo`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: snippet.slice(0, 4000) }),
      });
      if (r.status === 429) {
        setError("Hold on a second…");
        setScoring(false);
        return;
      }
      if (!r.ok) throw new Error("Couldn't classify that snippet.");
      const data = await r.json();
      setResult(data.sensitivity);
    } catch (e) {
      setError(e.message || "Couldn't classify that snippet.");
    } finally {
      setScoring(false);
    }
  };

  const onChange = (e) => {
    const v = e.target.value;
    setText(v);
    if (debounceRef.current) window.clearTimeout(debounceRef.current);
    debounceRef.current = window.setTimeout(() => score(v), 800);
  };

  const trySample = () => {
    setText(SAMPLE_TEXT);
    score(SAMPLE_TEXT);
  };

  const tone = result ? CLASSIFICATION_TONE[result.classification] || CLASSIFICATION_TONE.internal : null;

  return (
    <section
      className="border-b border-black/30"
      style={{ backgroundColor: NAVY, color: CREAM }}
      data-testid="landing-enterprise-section"
    >
      <div className="max-w-[1280px] mx-auto px-6 md:px-12 py-20 md:py-28 grid md:grid-cols-12 gap-10 md:gap-16 items-start">
        <div className="md:col-span-5">
          <p className="akki-overline mb-4" style={{ color: OXBLOOD }}>
            <ShieldCheck className="w-3 h-3 inline mr-1.5 -mt-0.5" />
            Decks + Reports Studio · Enterprise
          </p>
          <h2
            className="akki-serif text-[36px] md:text-[48px] leading-[1.06] tracking-[-0.015em] font-normal mb-5 max-w-[18ch]"
            style={{ color: CREAM }}
          >
            Produce board-grade reports securely.
          </h2>
          <p
            className="akki-serif text-[16.5px] md:text-[18px] leading-[1.65] mb-7 max-w-[44ch]"
            style={{ color: `${CREAM}D9` }}
          >
            Every saved artefact is auto-classified for confidentiality and
            tracks who's read it — so you know your information exposure
            before you share.
          </p>
          <ul className="space-y-3 mb-9 text-[14px] max-w-[48ch]" style={{ color: `${CREAM}CC` }}>
            <li className="flex gap-3" data-testid="enterprise-bullet-1">
              <Sparkles className="w-3.5 h-3.5 mt-1 shrink-0" style={{ color: OXBLOOD }} />
              <span>Auto-sensitivity scoring on every artefact — Public · Internal · Confidential · Restricted.</span>
            </li>
            <li className="flex gap-3" data-testid="enterprise-bullet-2">
              <Eye className="w-3.5 h-3.5 mt-1 shrink-0" style={{ color: OXBLOOD }} />
              <span>Electronic read-tracking marker on every distributed document.</span>
            </li>
            <li className="flex gap-3" data-testid="enterprise-bullet-3">
              <ShieldCheck className="w-3.5 h-3.5 mt-1 shrink-0" style={{ color: OXBLOOD }} />
              <span>Information exposure score — know who saw it, when, how often.</span>
            </li>
          </ul>
          <div className="flex flex-wrap gap-3">
            <Link to="/signup?from=enterprise">
              <Button
                className="rounded-sm h-11 px-6 text-[13.5px] tracking-wide font-medium"
                style={{ backgroundColor: CREAM, color: NAVY }}
                data-testid="enterprise-demo-request"
              >
                Request a team workspace <ArrowRight className="w-4 h-4 ml-2" />
              </Button>
            </Link>
            <Link to="/security">
              <Button
                variant="outline"
                className="rounded-sm h-11 px-6 text-[13.5px] bg-transparent hover:bg-white/10"
                style={{ borderColor: `${CREAM}30`, color: CREAM }}
                data-testid="enterprise-security-link"
              >
                Security design
              </Button>
            </Link>
          </div>
        </div>

        {/* Live sensitivity demo */}
        <div
          className="md:col-span-7 rounded-md p-6 md:p-7"
          style={{ backgroundColor: `${CREAM}0A`, border: `1px solid ${CREAM}26` }}
          data-testid="enterprise-live-demo"
        >
          <div className="flex items-baseline justify-between mb-4">
            <p className="akki-overline" style={{ color: `${CREAM}99` }}>
              Try it · paste any board-pack snippet
            </p>
            <button
              type="button"
              onClick={trySample}
              className="text-[11.5px] uppercase tracking-[0.16em] hover:underline"
              style={{ color: OXBLOOD }}
              data-testid="enterprise-demo-sample"
            >
              Use sample
            </button>
          </div>
          <textarea
            value={text}
            onChange={onChange}
            rows={5}
            placeholder="e.g. We are evaluating a £45m bolt-on acquisition; the CFO has indicated three regulatory inquiries are pending…"
            className="w-full rounded-sm p-3 text-[13px] leading-[1.55] resize-none outline-none"
            style={{
              backgroundColor: `${CREAM}0F`,
              color: CREAM,
              border: `1px solid ${CREAM}26`,
            }}
            data-testid="enterprise-demo-input"
            maxLength={4000}
          />
          <div className="mt-4 flex items-center justify-between gap-4">
            <p className="text-[11px]" style={{ color: `${CREAM}66` }}>
              {text.length}/4000 chars · regex-scored, no LLM, no storage
            </p>
            {scoring && (
              <span className="inline-flex items-center gap-1.5 text-[11.5px]" style={{ color: `${CREAM}99` }}>
                <Loader2 className="w-3 h-3 animate-spin" /> Classifying…
              </span>
            )}
          </div>

          {error && (
            <p className="mt-3 text-[12px]" style={{ color: "#FCA5A5" }} data-testid="enterprise-demo-error">
              {error}
            </p>
          )}

          {result && tone && (
            <div
              className="mt-5 rounded-sm p-5"
              style={{
                backgroundColor: `${CREAM}0F`,
                border: `1px solid ${tone.ring}66`,
                borderLeft: `3px solid ${tone.ring}`,
              }}
              data-testid="enterprise-demo-result"
            >
              <div className="flex items-center justify-between mb-3">
                <p className="akki-overline" style={{ color: `${CREAM}99` }}>
                  Classification
                </p>
                <span
                  className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-sm border text-[10px] uppercase tracking-[0.14em] ${tone.chip}`}
                  data-testid={`enterprise-demo-classification-${result.classification}`}
                >
                  {result.label} · score {result.score}
                </span>
              </div>
              {result.reasons?.length > 0 && (
                <>
                  <p className="text-[10.5px] uppercase tracking-[0.16em] mb-2" style={{ color: `${CREAM}66` }}>
                    Why
                  </p>
                  <ul className="text-[12.5px] space-y-1" style={{ color: `${CREAM}CC` }}>
                    {result.reasons.map((r, i) => (
                      <li key={i} className="flex gap-2">
                        <span style={{ color: tone.ring }}>·</span>
                        <span>{r}</span>
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </div>
          )}

          {!result && !scoring && (
            <p className="mt-5 text-[12.5px] italic" style={{ color: `${CREAM}77` }}>
              Type or paste anything board-related — names, deal sizes, succession,
              regulator notes — and we'll classify it the way the Studio would
              when you save it.
            </p>
          )}
        </div>
      </div>
    </section>
  );
}
