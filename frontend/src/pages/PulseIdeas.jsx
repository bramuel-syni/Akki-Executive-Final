/**
 * Phase P5.15 — Pulse · Ideas by Akki tab.
 *
 * Weekly cited synthesis across 4 lenses (Strategy / Board
 * navigation / Capital / Governance). Layout:
 *
 *   • 4-column grid at lg+ (≥1024)
 *   • 2x2 at md (≥768)
 *   • single-column stack at mobile
 *
 * Pulls from `/api/ideas/digest/current`. Lazy-generates server-
 * side on first hit of the week. Past weeks via the dropdown
 * (`/api/ideas/digest/history` + `/api/ideas/digest/{week_iso}`).
 *
 * No fake placeholder cards in any state. Empty corpus →
 * polite empty-state copy. Dropped lens → caveat row.
 */
import React, { useEffect, useState } from "react";
import AppShell from "@/components/layout/AppShell";
import PulseMasterTabs from "@/components/pulse/PulseMasterTabs";
import { api, apiErrorMessage } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

const LENS_ORDER = ["strategy", "board_navigation", "capital", "governance"];
const LENS_DISPLAY = {
  strategy:         { label: "Strategy",         glyph: "◆" },
  board_navigation: { label: "Board navigation", glyph: "◇" },
  capital:          { label: "Capital",          glyph: "◈" },
  governance:       { label: "Governance",       glyph: "◉" },
};

const BAND_DISPLAY = {
  low:    { label: "Low confidence",    color: "bg-[color:#fde68a] text-[color:#78350f]" },
  medium: { label: "Medium confidence", color: "bg-[color:#bfdbfe] text-[color:#1e3a8a]" },
  high:   { label: "High confidence",   color: "bg-[color:#bbf7d0] text-[color:#14532d]" },
};

export default function PulseIdeas() {
  const [digest, setDigest] = useState(null);
  const [history, setHistory] = useState([]);
  const [selectedWeek, setSelectedWeek] = useState(null); // null = current
  const [prefs, setPrefs] = useState(null);
  const [loading, setLoading] = useState(true);
  const [prefsOpen, setPrefsOpen] = useState(false);
  const [citationsCardId, setCitationsCardId] = useState(null);

  // ── Loaders ───────────────────────────────────────────────────
  const loadDigest = async (weekIso) => {
    setLoading(true);
    try {
      const url = weekIso ? `/ideas/digest/${weekIso}` : "/ideas/digest/current";
      const { data } = await api.get(url);
      setDigest(data);
    } catch (e) {
      toast.error(apiErrorMessage(e));
      setDigest(null);
    } finally {
      setLoading(false);
    }
  };

  const loadHistory = async () => {
    try {
      const { data } = await api.get("/ideas/digest/history?limit=12");
      setHistory(data.items || []);
    } catch (e) {
      /* non-fatal */
    }
  };

  const loadPrefs = async () => {
    try {
      const { data } = await api.get("/ideas/preferences");
      setPrefs(data);
    } catch (e) {
      /* non-fatal */
    }
  };

  useEffect(() => {
    loadDigest(null);
    loadHistory();
    loadPrefs();
  }, []);

  const onSwitchWeek = (week) => {
    setSelectedWeek(week);
    loadDigest(week);
  };

  const savePrefs = async () => {
    try {
      await api.put("/ideas/preferences", {
        custom_instructions: prefs.custom_instructions || "",
        lenses_enabled: prefs.lenses_enabled || LENS_ORDER,
      });
      toast.success("Preferences saved");
      setPrefsOpen(false);
      // Re-fetch the current digest so the new preferences flow
      // through (though for an existing-week row they only flow
      // through after the next regeneration; we hint at this via
      // the polite admin caveat below).
      loadDigest(selectedWeek);
    } catch (e) {
      toast.error(apiErrorMessage(e));
    }
  };

  const currentCardForCitations = digest && citationsCardId != null
    ? digest.cards[citationsCardId]
    : null;

  // ── Render ────────────────────────────────────────────────────
  const emptyState = !loading && (!digest || (digest.cards.length === 0));

  return (
    <AppShell>
      <div className="akki-w-medium px-8 pt-10 pb-12" data-testid="pulse-ideas-page">
        <PulseMasterTabs />
        <header className="flex items-baseline justify-between gap-4 mb-6">
          <div>
            <h1 className="text-3xl font-medium tracking-tight" data-testid="pulse-ideas-h1">
              Ideas by Akki
            </h1>
            <p className="mt-2 text-[var(--muted)] text-sm max-w-2xl">
              Each week, Akki reads what your library has accreted and surfaces
              observations across four lenses. Every claim cites a real chunk;
              the confidence band is calibrated from corpus coverage, not
              self-reported.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <select
              data-testid="pulse-ideas-week-selector"
              value={selectedWeek || ""}
              onChange={(e) => onSwitchWeek(e.target.value || null)}
              className="rounded border border-[var(--rule)] bg-transparent text-xs px-2 py-1"
            >
              <option value="">Current week</option>
              {history.map((h) => (
                <option key={h.id} value={h.week_iso}>
                  {h.week_iso}
                </option>
              ))}
            </select>
            <Button
              variant="outline"
              onClick={() => setPrefsOpen(true)}
              data-testid="pulse-ideas-adjust-focus-btn"
            >Adjust focus</Button>
          </div>
        </header>

        {loading && (
          <div data-testid="pulse-ideas-loading" className="text-sm text-[var(--muted)]">
            Loading this week's ideas…
          </div>
        )}

        {emptyState && (
          <div
            data-testid="pulse-ideas-empty"
            className="border border-dashed border-[var(--rule)] rounded-lg p-10 text-center text-[var(--muted)]"
          >
            <div className="text-sm">
              Akki is still reading your library.
            </div>
            <div className="text-xs mt-2 max-w-md mx-auto">
              Your first weekly ideas will surface once seven days of activity
              are indexed. In the meantime, the Signals tab carries every
              indexed item Akki has already read.
            </div>
          </div>
        )}

        {digest && digest.cards.length > 0 && (
          <>
            <div
              data-testid="pulse-ideas-grid"
              className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4"
            >
              {LENS_ORDER.map((lens, idx) => {
                const card = digest.cards.find((c) => c.lens === lens);
                if (!card) return null;
                const band = BAND_DISPLAY[card.confidence_band] || BAND_DISPLAY.low;
                const cardIndex = digest.cards.indexOf(card);
                return (
                  <article
                    key={lens}
                    data-testid={`pulse-ideas-card-${lens}`}
                    className="border border-[var(--rule)] rounded-lg p-5 flex flex-col"
                  >
                    <div className="flex items-baseline justify-between gap-2 mb-2">
                      <span className="text-xs tracking-[0.14em] uppercase text-[var(--muted)]">
                        <span aria-hidden="true">{LENS_DISPLAY[lens].glyph}</span>{" "}
                        {LENS_DISPLAY[lens].label}
                      </span>
                      <span
                        data-testid={`pulse-ideas-card-${lens}-band`}
                        className={`px-2 py-0.5 rounded text-[10px] ${band.color}`}
                        title={card.confidence_rationale}
                      >
                        {band.label}
                      </span>
                    </div>
                    <h3 className="font-medium text-base mb-2">{card.title}</h3>
                    <p className="text-sm text-[var(--ink)] flex-1">{card.body}</p>
                    <button
                      type="button"
                      data-testid={`pulse-ideas-card-${lens}-citations-btn`}
                      onClick={() => setCitationsCardId(cardIndex)}
                      className="mt-3 self-start text-xs text-[var(--accent)] underline-offset-2 hover:underline"
                    >
                      Cited from {card.citations.length} chunk(s)
                    </button>
                  </article>
                );
              })}
            </div>
            {digest.dropped_lenses && digest.dropped_lenses.length > 0 && (
              <div
                data-testid="pulse-ideas-caveat"
                className="mt-6 text-xs text-[var(--muted)] border-l-2 border-[color:#fde68a] pl-3"
              >
                {digest.dropped_lenses.length} of 4 lenses did not produce a
                card this week — the corpus did not surface enough evidence to
                support them. Acceptable thresholds: ≥2 chunks per lens.
              </div>
            )}
          </>
        )}
      </div>

      {/* Preferences drawer */}
      {prefsOpen && prefs && (
        <div
          data-testid="pulse-ideas-prefs-drawer"
          className="fixed inset-0 z-40 bg-black/30 flex items-stretch justify-end"
          onClick={(e) => { if (e.target === e.currentTarget) setPrefsOpen(false); }}
        >
          <div className="w-full max-w-md bg-[var(--bg)] border-l border-[var(--rule)] h-full p-6 overflow-y-auto">
            <h2 className="text-lg font-medium mb-1">Adjust focus</h2>
            <p className="text-xs text-[var(--muted)] mb-4">
              Akki uses these instructions to weight relevance. The four lenses
              still each produce one card unless the corpus does not support it.
              Imperative-to-user phrasing is rejected by the safety validator.
            </p>
            <label className="block text-xs tracking-[0.14em] uppercase text-[var(--muted)] mt-4 mb-1">
              Custom instructions
            </label>
            <textarea
              data-testid="pulse-ideas-prefs-custom-instructions"
              value={prefs.custom_instructions || ""}
              onChange={(e) => setPrefs({ ...prefs, custom_instructions: e.target.value })}
              maxLength={2000}
              className="w-full h-32 rounded border border-[var(--rule)] bg-transparent p-2 text-sm"
              placeholder={"E.g. \"This quarter I am most interested in regulatory shifts in EMEA and the unit-economics of our APAC pilot.\""}
            />
            <label className="block text-xs tracking-[0.14em] uppercase text-[var(--muted)] mt-6 mb-1">
              Lenses to include
            </label>
            <div className="space-y-2">
              {LENS_ORDER.map((lens) => {
                const isOn = (prefs.lenses_enabled || []).includes(lens);
                return (
                  <label key={lens} className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      data-testid={`pulse-ideas-prefs-lens-${lens}`}
                      checked={isOn}
                      onChange={(e) => {
                        const next = e.target.checked
                          ? Array.from(new Set([...(prefs.lenses_enabled || []), lens]))
                          : (prefs.lenses_enabled || []).filter((l) => l !== lens);
                        setPrefs({ ...prefs, lenses_enabled: next });
                      }}
                    />
                    {LENS_DISPLAY[lens].label}
                  </label>
                );
              })}
            </div>
            <div className="mt-8 flex items-center gap-2">
              <Button
                onClick={savePrefs}
                data-testid="pulse-ideas-prefs-save-btn"
              >Save</Button>
              <Button
                variant="outline"
                onClick={() => setPrefsOpen(false)}
                data-testid="pulse-ideas-prefs-cancel-btn"
              >Cancel</Button>
            </div>
          </div>
        </div>
      )}

      {/* Citations drawer */}
      {currentCardForCitations && (
        <div
          data-testid="pulse-ideas-citations-drawer"
          className="fixed inset-0 z-40 bg-black/30 flex items-stretch justify-end"
          onClick={(e) => { if (e.target === e.currentTarget) setCitationsCardId(null); }}
        >
          <div className="w-full max-w-md bg-[var(--bg)] border-l border-[var(--rule)] h-full p-6 overflow-y-auto">
            <h2 className="text-lg font-medium">Citations</h2>
            <p className="text-xs text-[var(--muted)] mb-4">
              {currentCardForCitations.title}
            </p>
            <ol className="space-y-3 text-sm" data-testid="pulse-ideas-citations-list">
              {currentCardForCitations.citations.map((c, i) => (
                <li
                  key={i}
                  data-testid={`pulse-ideas-citation-${i}`}
                  className="border-l-2 border-[color:var(--oxblood)] pl-3"
                >
                  <div className="text-xs text-[var(--muted)]">
                    document <code>{c.document_id}</code>
                    {c.chunk_id ? <>{" · chunk "}<code>{c.chunk_id}</code></> : null}
                  </div>
                  <p className="mt-1">{c.excerpt}</p>
                </li>
              ))}
            </ol>
            <div className="mt-8">
              <Button
                variant="outline"
                onClick={() => setCitationsCardId(null)}
                data-testid="pulse-ideas-citations-close-btn"
              >Close</Button>
            </div>
          </div>
        </div>
      )}
    </AppShell>
  );
}
