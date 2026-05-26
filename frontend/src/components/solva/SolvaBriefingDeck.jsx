/**
 * SolvaBriefingDeck — Phase D.1 (2026-05-26).
 *
 * 4-slide modal that shows ahead of every Solva conversation entry
 * (per area), persisted via `/api/solva/briefing/state`.
 *
 * Contract:
 *   props:
 *     - area    : SolvaArea slug (one of seek-clarity / test-hypothesis
 *                                 / develop-strategy / different-perspective)
 *     - open    : boolean — controlled open state
 *     - onClose : (reason: "got_it" | "skip" | "x") => void
 *     - force   : optional boolean — if true, bypasses `suppressed`
 *                                    (used by the `(i)` reopen icon)
 *
 *   internal state:
 *     - slideIdx (0-3)
 *     - visit_count (from backend)
 *     - suppressChecked (bool, only on slide 4)
 *
 * Side effects:
 *   - On mount: GET /state, then POST /state action=increment IF the
 *     deck would actually open (not suppressed OR `force=true`).
 *   - On "Got it" with suppressCheck=true: POST /state action=suppress.
 *
 * Slide copy is sourced VERBATIM from
 * `frontend/src/data/solva-briefings.js`. No inline copy.
 */
import React, { useEffect, useMemo, useState } from "react";
import { SOLVA_AREAS } from "@/data/solva-briefings";
import { api } from "@/lib/api";
import {
  Dialog, DialogContent, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

// Render title with first WORD in oxblood, rest in default ink.
function SlideTitle({ text }) {
  const trimmed = (text || "").trim();
  const firstSpace = trimmed.indexOf(" ");
  const firstWord = firstSpace === -1 ? trimmed : trimmed.slice(0, firstSpace);
  const rest = firstSpace === -1 ? "" : trimmed.slice(firstSpace);
  return (
    <h2
      data-testid="solva-briefing-title"
      style={{
        fontFamily: "Georgia, serif",
        fontWeight: 700,
        fontSize: "1.5em",
        lineHeight: 1.25,
        margin: 0,
        textAlign: "center",
      }}
    >
      <span style={{ color: "var(--oxblood)" }} data-testid="solva-briefing-title-first-word">
        {firstWord}
      </span>
      {rest && <span style={{ color: "var(--ink)" }}>{rest}</span>}
    </h2>
  );
}

// Minimal markdown body: split paragraphs on \n\n, render bullets
// for lines starting with "- ".
function SlideBody({ markdown }) {
  const blocks = (markdown || "").split("\n\n");
  return (
    <div
      data-testid="solva-briefing-body"
      style={{
        maxWidth: 640,
        margin: "16px auto 0",
        textAlign: "left",
        lineHeight: 1.6,
        fontSize: "1rem",
        color: "var(--ink)",
      }}
    >
      {blocks.map((block, bi) => {
        const lines = block.split("\n");
        const isList = lines.every((ln) => ln.trim().startsWith("- "));
        if (isList) {
          return (
            <ul
              key={bi}
              style={{ paddingLeft: 22, margin: "0 0 16px 0", listStyleType: "disc" }}
            >
              {lines.map((ln, li) => (
                <li key={li} style={{ marginBottom: 6 }}>
                  {ln.replace(/^- /, "")}
                </li>
              ))}
            </ul>
          );
        }
        return (
          <p key={bi} style={{ margin: "0 0 16px 0", whiteSpace: "pre-wrap" }}>
            {block}
          </p>
        );
      })}
    </div>
  );
}

export default function SolvaBriefingDeck({ area, open, onClose, force = false }) {
  const [slideIdx, setSlideIdx] = useState(0);
  const [state, setState] = useState({ visit_count: 0, suppressed: false, loaded: false });
  const [suppressChecked, setSuppressChecked] = useState(false);
  const [fade, setFade] = useState(false);

  const areaData = SOLVA_AREAS[area];
  const slides = useMemo(() => areaData?.slides || [], [areaData]);

  // Bootstrap state when the deck opens.
  useEffect(() => {
    if (!open || !area) return;
    let dead = false;
    (async () => {
      try {
        const { data } = await api.get(`/solva/briefing/state`, { params: { area } });
        if (dead) return;
        setState({
          visit_count: data?.visit_count || 0,
          suppressed: !!data?.suppressed,
          loaded: true,
        });
        // Only increment if we're actually going to show the deck:
        //   - force=true (i-icon reopen) → increment + show.
        //   - suppressed=true && !force → don't show, don't increment.
        //   - otherwise → increment + show.
        const willShow = force || !data?.suppressed;
        if (willShow) {
          api.post(`/solva/briefing/state`, { area, action: "increment" })
            .catch(() => {});
        } else {
          // Suppressed and not forced — close immediately.
          onClose && onClose("skip");
        }
      } catch (_e) {
        if (!dead) setState((s) => ({ ...s, loaded: true }));
      }
    })();
    return () => { dead = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, area, force]);

  // Reset internal slide index when the deck (re)opens.
  useEffect(() => {
    if (open) {
      setSlideIdx(0);
      setSuppressChecked(false);
    }
  }, [open]);

  const transitionToSlide = (next) => {
    if (next < 0 || next >= slides.length) return;
    setFade(true);
    window.setTimeout(() => {
      setSlideIdx(next);
      setFade(false);
    }, 200);
  };

  const handleSkip = () => {
    onClose && onClose("skip");
  };

  const handleGotIt = async () => {
    if (suppressChecked) {
      try {
        await api.post(`/solva/briefing/state`, { area, action: "suppress" });
      } catch (_e) { /* swallow */ }
    }
    onClose && onClose("got_it");
  };

  if (!areaData) return null;
  const current = slides[slideIdx];
  const isFirst = slideIdx === 0;
  const isLast = slideIdx === slides.length - 1;
  // From the 2nd visit onwards (per area), show "Don't show me again".
  // visit_count reflects the count BEFORE this open's increment, so
  // we check >= 1 (second visit has visit_count==1 before increment).
  const showSuppressBox = isLast && (state.visit_count >= 1);

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) onClose && onClose("x"); }}>
      <DialogContent
        className="max-w-[720px]"
        data-testid="solva-briefing-deck"
        data-area={area}
        data-slide={slideIdx + 1}
      >
        <DialogTitle className="sr-only">{`${areaData.label} — briefing`}</DialogTitle>
        <DialogDescription className="sr-only">
          Pre-conversation briefing for the {areaData.label} area.
        </DialogDescription>
        <div
          style={{
            opacity: fade ? 0 : 1,
            transition: "opacity 200ms ease-out",
            padding: "8px 4px",
          }}
        >
          {current && (
            <>
              <SlideTitle text={current.title} />
              <SlideBody markdown={current.body} />
            </>
          )}
        </div>

        {/* Footer — slide-dependent button set */}
        <div
          className="flex items-center justify-between gap-3 pt-4 border-t border-[var(--rule)]"
          data-testid="solva-briefing-footer"
        >
          <div className="flex items-center gap-2 text-[12px] text-[var(--muted)] font-mono">
            <span data-testid="solva-briefing-progress">{slideIdx + 1} / {slides.length}</span>
          </div>

          <div className="flex items-center gap-3">
            {isLast && showSuppressBox && (
              <label
                className="flex items-center gap-2 text-[12.5px] text-[var(--muted)] cursor-pointer mr-2"
                data-testid="solva-briefing-suppress-label"
              >
                <input
                  type="checkbox"
                  checked={suppressChecked}
                  onChange={(e) => setSuppressChecked(e.target.checked)}
                  data-testid="solva-briefing-suppress-checkbox"
                />
                Don't show me again
              </label>
            )}

            {isFirst ? (
              <Button
                variant="ghost"
                onClick={handleSkip}
                data-testid="solva-briefing-skip-btn"
              >
                Skip briefing
              </Button>
            ) : (
              <Button
                variant="ghost"
                onClick={() => transitionToSlide(slideIdx - 1)}
                data-testid="solva-briefing-back-btn"
              >
                ← Back
              </Button>
            )}

            {isLast ? (
              <Button
                onClick={handleGotIt}
                style={{ backgroundColor: "var(--oxblood)", color: "white" }}
                data-testid="solva-briefing-gotit-btn"
              >
                Got it
              </Button>
            ) : (
              <Button
                onClick={() => transitionToSlide(slideIdx + 1)}
                style={{ backgroundColor: "var(--oxblood)", color: "white" }}
                data-testid="solva-briefing-next-btn"
              >
                Next →
              </Button>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
