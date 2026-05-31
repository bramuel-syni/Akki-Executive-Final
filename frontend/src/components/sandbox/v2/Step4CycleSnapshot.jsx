/**
 * Phase J.4 — Step 4 Cycle Manager snapshot.
 *
 * Pure read-only render of the corpus-provided cycle data. The shape
 * is sourced from `pick_cycle_snapshot(role, org_type)` via the
 * /api/sandbox/v2/sessions/{sid}/cycle-snapshot endpoint:
 *
 *   {
 *     framing:           "...",
 *     anchor_label:      "...",
 *     timeline:          [ { cycle, anchor, date, status }, ... ],
 *     open_items:        [ { text, status, owner }, ... ],
 *     strategic_baseline:[ "...", ... ],
 *     pulse_items:       [ { text, kind }, ... ],
 *     voice:             "..."   // banner copy, verbatim from pack
 *   }
 *
 * The brief asks for a short top banner: "This is a snapshot of what
 * your Cycle Manager would look like after three cycles in Akki. The
 * data is representative; the architecture is real." The corpus's
 * `voice` field is the verbatim version of that line, so we use it
 * directly — no new strings drafted client-side.
 */
import React, { useEffect, useState } from "react";
import axios from "axios";
import { TOKEN, FONT } from "./tokens";
import { Actions } from "@/lib/sandboxV2Flow";

import { resolveBackendOrigin } from "@/lib/api";
const API = resolveBackendOrigin();
const api = axios.create({
  baseURL: `${API}/api/sandbox/v2`,
  withCredentials: true,
  headers: { "Content-Type": "application/json" },
});

export default function Step4CycleSnapshot({ flow, dispatch, onComplete }) {
  const sid = flow.sessionId;
  const [snap, setSnap] = useState(null);
  const [err, setErr] = useState(null);

  useEffect(() => {
    let cancelled = false;
    async function init() {
      if (!sid) return;
      try {
        const r = await api.get(`/sessions/${sid}/cycle-snapshot`);
        if (cancelled) return;
        setSnap(r.data?.snapshot || null);
        dispatch(Actions.cycleViewed());
      } catch (e) {
        if (cancelled) return;
        setErr(e?.response?.data?.detail || e.message || "Could not load cycle snapshot.");
      }
    }
    init();
    return () => { cancelled = true; };
  }, [sid, dispatch]);

  if (err) {
    return <div role="alert" style={errBox}>{err}</div>;
  }

  if (!snap) {
    return (
      <div style={{ fontFamily: FONT.GEORGIA, fontStyle: "italic", color: TOKEN.MUTED, padding: 40, textAlign: "center" }}>
        Building your snapshot…
      </div>
    );
  }

  return (
    <div data-testid="sandbox-v2-step4" style={{ width: "100%" }}>
      <Header voice={snap.voice} framing={snap.framing} />

      <SectionTimeline timeline={snap.timeline || []} anchorLabel={snap.anchor_label} />
      <SectionOpenItems items={snap.open_items || []} />
      <SectionStrategicBaseline lines={snap.strategic_baseline || []} />
      <SectionPulseItems items={snap.pulse_items || []} />

      <div style={{ marginTop: 36, textAlign: "center" }}>
        <button
          type="button"
          onClick={onComplete}
          data-testid="sandbox-v2-step4-continue"
          style={{
            fontFamily: FONT.CALIBRI,
            fontSize: 14,
            background: TOKEN.ACCENT_DARK,
            color: TOKEN.LIGHT,
            border: "none",
            padding: "12px 28px",
            cursor: "pointer",
            borderRadius: 2,
            letterSpacing: 0.5,
          }}
        >
          See what just happened &rarr;
        </button>
      </div>
    </div>
  );
}

function Header({ voice, framing }) {
  return (
    <>
      <div style={{ width: 56, height: 1, background: TOKEN.ACCENT, margin: "0 auto 22px" }} />
      <h1 style={{
        fontFamily: FONT.GEORGIA, fontSize: 26, fontWeight: 700,
        color: TOKEN.INK, margin: "0 0 18px 0", textAlign: "center", lineHeight: 1.2,
      }}>
        Cycle Manager — three cycles in.
      </h1>

      {/* Banner uses the corpus `voice` field, verbatim. */}
      <div
        role="note"
        data-testid="sandbox-v2-step4-banner"
        style={{
          background: TOKEN.CREAM_DEEP,
          border: `1px solid ${TOKEN.RULE}`,
          padding: "16px 18px",
          fontFamily: FONT.GEORGIA,
          fontStyle: "italic",
          fontSize: 14,
          color: TOKEN.DEEP,
          lineHeight: 1.6,
          margin: "0 0 28px 0",
          borderRadius: 2,
        }}
      >
        {voice}
      </div>

      {framing && (
        <div style={kicker}>{framing}</div>
      )}
    </>
  );
}

function SectionTimeline({ timeline, anchorLabel }) {
  return (
    <Section title={`Timeline · ${anchorLabel || "Cadence"}`}>
      <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
        {timeline.map((row, i) => (
          <li
            key={i}
            data-testid={`sandbox-v2-step4-timeline-row-${i}`}
            style={{
              display: "grid",
              gridTemplateColumns: "100px 1fr 160px 100px",
              gap: 14,
              padding: "10px 4px",
              borderBottom: i === timeline.length - 1 ? "none" : `1px solid ${TOKEN.RULE}`,
              alignItems: "baseline",
            }}
          >
            <span style={{ fontFamily: FONT.CALIBRI, fontSize: 11, textTransform: "uppercase", letterSpacing: 1.2, color: TOKEN.MUTED }}>
              {row.cycle}
            </span>
            <span style={{ fontFamily: FONT.GEORGIA, fontSize: 14, color: TOKEN.INK }}>
              {row.anchor}
            </span>
            <span style={{ fontFamily: FONT.CALIBRI, fontSize: 12, color: TOKEN.DEEP }}>
              {row.date}
            </span>
            <StatusPill status={row.status} />
          </li>
        ))}
      </ul>
    </Section>
  );
}

function SectionOpenItems({ items }) {
  return (
    <Section title="Open items carried forward">
      <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
        {items.map((it, i) => (
          <li
            key={i}
            data-testid={`sandbox-v2-step4-open-${i}`}
            style={{
              padding: "12px 0",
              borderBottom: i === items.length - 1 ? "none" : `1px dotted ${TOKEN.RULE}`,
            }}
          >
            <div style={{ fontFamily: FONT.GEORGIA, fontSize: 14, color: TOKEN.INK, lineHeight: 1.55, marginBottom: 4 }}>
              {it.text}
            </div>
            <div style={{ display: "flex", gap: 14, alignItems: "center", fontFamily: FONT.CALIBRI, fontSize: 12 }}>
              <StatusPill status={it.status} />
              <span style={{ color: TOKEN.MUTED }}>{it.owner}</span>
            </div>
          </li>
        ))}
      </ul>
    </Section>
  );
}

function SectionStrategicBaseline({ lines }) {
  return (
    <Section title="Strategic baseline">
      <ul style={{ listStyle: "disc", paddingLeft: 22, margin: 0 }}>
        {lines.map((ln, i) => (
          <li key={i}
            style={{ fontFamily: FONT.GEORGIA, fontSize: 14, color: TOKEN.DEEP, lineHeight: 1.6, marginBottom: 8 }}>
            {ln}
          </li>
        ))}
      </ul>
    </Section>
  );
}

function SectionPulseItems({ items }) {
  return (
    <Section title="Pulse-derived items">
      <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
        {items.map((it, i) => (
          <li
            key={i}
            data-testid={`sandbox-v2-step4-pulse-${i}`}
            style={{
              padding: "10px 0",
              display: "grid",
              gridTemplateColumns: "1fr 80px",
              gap: 12,
              alignItems: "baseline",
              borderBottom: i === items.length - 1 ? "none" : `1px dotted ${TOKEN.RULE}`,
            }}
          >
            <span style={{ fontFamily: FONT.GEORGIA, fontSize: 14, color: TOKEN.INK, lineHeight: 1.55 }}>
              {it.text}
            </span>
            <span style={{
              fontFamily: FONT.CALIBRI,
              fontSize: 11,
              textTransform: "uppercase",
              letterSpacing: 1.2,
              color: it.kind === "external" ? TOKEN.ACCENT_DARK : TOKEN.MUTED,
              textAlign: "right",
            }}>
              {it.kind || "internal"}
            </span>
          </li>
        ))}
      </ul>
    </Section>
  );
}

function Section({ title, children }) {
  return (
    <section style={{ marginBottom: 28 }}>
      <div style={kicker}>{title}</div>
      <div
        style={{
          background: TOKEN.LIGHT,
          border: `1px solid ${TOKEN.RULE}`,
          borderRadius: 2,
          padding: "16px 18px",
        }}
      >
        {children}
      </div>
    </section>
  );
}

function StatusPill({ status }) {
  const s = (status || "").toLowerCase();
  const isAlert = s === "at risk" || s === "blocked";
  const isAhead = s === "closed";
  const fg = isAlert ? TOKEN.ACCENT_DARK : (isAhead ? TOKEN.MUTED : TOKEN.INK);
  return (
    <span style={{
      fontFamily: FONT.CALIBRI,
      fontSize: 11,
      textTransform: "uppercase",
      letterSpacing: 1.2,
      color: fg,
      textAlign: "right",
    }}>
      {status}
    </span>
  );
}

const kicker = {
  fontFamily: FONT.CALIBRI,
  fontSize: 11,
  textTransform: "uppercase",
  letterSpacing: 1.4,
  color: TOKEN.MUTED,
  marginBottom: 10,
};
const errBox = {
  padding: 24,
  fontFamily: FONT.CALIBRI,
  color: TOKEN.ACCENT_DARK,
  border: `1px solid ${TOKEN.ACCENT_DARK}`,
  background: TOKEN.LIGHT,
  borderRadius: 2,
};
