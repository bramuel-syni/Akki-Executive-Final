/**
 * Activity — chronological timeline page for one of the five categories.
 *
 * Surfaced when the user clicks a tile on the Home /app/activity feed.
 * Uses ?cat={key} as the source-of-truth selector. We re-fetch all five
 * sources on mount (cheap because the user just came from the same data
 * on Home) and filter to the chosen category.
 *
 * The reverse-chronological list carries verbs ("DOCUMENT ADDED",
 * "BRIEFING DRAFTED") and time stamps. Items are clickable through to
 * their respective surface (Document Journal, Prepare, etc.).
 */
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import AppShell from "@/components/layout/AppShell";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import {
  Sparkles, ScrollText, FileText, Mail, MessageCircle, ArrowLeft,
} from "lucide-react";

const CATEGORIES = {
  meetings: {
    label: "Briefings & meetings",
    intro: "Packs AKKI prepared so you walk into the room oriented.",
    icon: ScrollText,
    surface: "/app/prepare",
  },
  answers: {
    label: "Questions answered",
    intro: "Briefs you generated — claims, proposals, topics, periods, reports.",
    icon: MessageCircle,
    surface: "/app/prepare",
  },
  signals: {
    label: "Signals surfaced",
    intro: "What the board needs to notice — risks, opportunities, gaps.",
    icon: Sparkles,
    surface: "/app/prepare",
  },
  documents: {
    label: "Documents added",
    intro: "Fresh material on your desk. AKKI has read each one.",
    icon: FileText,
    surface: "/app/workspace",
  },
  shared: {
    label: "Sent your way",
    intro: "Items a colleague forwarded — with or without a note.",
    icon: Mail,
    surface: "/app/prepare",
  },
};

function fmtDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    month: "short", day: "numeric", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

export default function Activity() {
  const [params] = useSearchParams();
  const cat = params.get("cat") || "signals";
  const meta = CATEGORIES[cat] || CATEGORIES.signals;

  const { activeContext } = useAuth();
  const cid = activeContext?.id;
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    if (!cid) return;
    setLoading(true);
    try {
      let raw = [];
      if (cat === "signals") {
        const { data } = await api.get(`/contexts/${cid}/signals`);
        raw = (Array.isArray(data) ? data : (data?.signals || [])).map((s) => ({
          id: s.id, ts: s.created_at, title: s.headline || s.title,
          meta: s.type || s.tone, to: "/app/prepare",
        }));
      } else if (cat === "meetings") {
        const { data } = await api.get(`/contexts/${cid}/briefings`);
        raw = (Array.isArray(data) ? data : (data?.briefings || [])).map((b) => ({
          id: b.id, ts: b.created_at || b.published_at, title: b.title,
          meta: "briefing", to: "/app/prepare",
        }));
      } else if (cat === "answers") {
        const { data } = await api.get(`/contexts/${cid}/briefs?limit=200`);
        raw = (data?.items || []).map((b) => ({
          id: b.id, ts: b.created_at, title: b.title,
          meta: b.kind, to: "/app/prepare",
        }));
      } else if (cat === "documents") {
        const { data } = await api.get(`/contexts/${cid}/documents`);
        raw = (Array.isArray(data) ? data : (data?.documents || data?.docs || [])).map((d) => ({
          id: d.id, ts: d.created_at, title: d.name || d.original_filename,
          meta: d.trust_level || "doc", to: `/app/documents/${d.id}`,
        }));
      } else if (cat === "shared") {
        const { data } = await api.get(`/contexts/${cid}/shares?direction=in`).catch(() => ({ data: { shares: [] } }));
        const items = data?.shares || data || [];
        raw = (Array.isArray(items) ? items : []).map((sh) => ({
          id: sh.id, ts: sh.created_at,
          title: sh.item_preview || sh.subject || "(no preview)",
          meta: `from ${(sh.shared_by_name || sh.shared_by_email || "someone").split(" ")[0]}`,
          to: "/app/prepare",
        }));
      }
      setItems(raw.filter((x) => x.title && x.ts).sort((a, b) => new Date(b.ts) - new Date(a.ts)));
    } catch { setItems([]); }
    finally { setLoading(false); }
  }, [cid, cat]);
  useEffect(() => { load(); }, [load]);

  const Icon = meta.icon;

  const grouped = useMemo(() => {
    // Group by day for editorial rhythm.
    const out = [];
    const seen = new Set();
    for (const it of items) {
      const day = new Date(it.ts).toLocaleDateString(undefined, {
        weekday: "long", month: "short", day: "numeric",
      });
      if (!seen.has(day)) {
        out.push({ kind: "day", label: day });
        seen.add(day);
      }
      out.push({ kind: "item", ...it });
    }
    return out;
  }, [items]);

  return (
    <AppShell>
      <div className="max-w-[920px] mx-auto px-6 py-10">
        <Link to="/app" className="akki-gesture text-[12.5px] inline-flex items-center mb-6" data-testid="activity-back">
          <ArrowLeft className="w-3.5 h-3.5 mr-1.5" /> Back to Home
        </Link>

        <div className="flex items-start gap-3 mb-2">
          <Icon className="w-5 h-5 text-[var(--accent)] mt-1.5" strokeWidth={1.7} />
          <div>
            <p className="akki-overline">Timeline · {activeContext?.name}</p>
            <h1 className="akki-greeting">{meta.label}</h1>
          </div>
        </div>
        <p className="akki-meta max-w-2xl mb-8">{meta.intro}</p>

        {/* Category switcher */}
        <div className="flex flex-wrap gap-2 mb-8" data-testid="activity-cat-switcher">
          {Object.entries(CATEGORIES).map(([key, v]) => {
            const active = key === cat;
            return (
              <Link
                key={key}
                to={`/app/activity?cat=${key}`}
                className={`px-3 py-1.5 rounded-full border text-[12.5px] transition-colors ${
                  active
                    ? "bg-[var(--ink)] text-[var(--cream)] border-[var(--ink)]"
                    : "bg-white text-[var(--deep)] border-[var(--rule)] hover:border-[var(--accent)]"
                }`}
                data-testid={`activity-cat-link-${key}${active ? "-active" : ""}`}
              >
                {v.label}
              </Link>
            );
          })}
        </div>

        {loading ? (
          <p className="text-[13px] text-[var(--muted)] italic">Loading…</p>
        ) : items.length === 0 ? (
          <div className="bg-white border border-[var(--rule)] rounded-md px-5 py-10 text-center">
            <p className="text-[13px] text-[var(--muted)] italic">
              Nothing in this category yet.
            </p>
          </div>
        ) : (
          <ul className="bg-white border border-[var(--rule)] rounded-md divide-y divide-[var(--rule)]" data-testid="activity-timeline">
            {grouped.map((row, i) =>
              row.kind === "day" ? (
                <li key={`d-${i}`} className="px-5 py-2.5 bg-[var(--cream-deep)]/30">
                  <p className="akki-overline text-[var(--muted)]">{row.label}</p>
                </li>
              ) : (
                <li key={row.id}>
                  <Link
                    to={row.to}
                    className="block px-5 py-3.5 hover:bg-[var(--cream-deep)]/30 transition-colors group"
                    data-testid={`activity-item-${row.id}`}
                  >
                    <div className="flex items-baseline gap-3 mb-0.5">
                      <span className="text-[10.5px] uppercase tracking-[0.18em] text-[var(--accent)] font-mono">
                        {row.meta}
                      </span>
                      <span className="ml-auto text-[11px] text-[var(--muted)] tabular-nums">
                        {fmtDate(row.ts)}
                      </span>
                    </div>
                    <p className="akki-serif text-[15px] text-[var(--ink)] leading-snug group-hover:text-[var(--accent)] transition-colors">
                      {row.title}
                    </p>
                  </Link>
                </li>
              )
            )}
          </ul>
        )}
      </div>
    </AppShell>
  );
}
