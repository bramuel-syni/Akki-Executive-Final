import React, { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { api, apiErrorMessage } from "@/lib/api";
import { toast } from "sonner";
import { ArrowRight, FileText, Send, Eye } from "lucide-react";

/**
 * QuickActions — three intent-anchored tiles on Home that map directly
 * to the workflows the user wants to start *right now*. Each tile is
 * the workflow — clicking opens the relevant Workflow at the right
 * stage, NOT a library page.
 *
 * Variants by active role:
 *   - executive  → "Review what your team sent" (Board Pack stage 0)
 *                + "Send the deck up"            (Board Pack stage 3)
 *                + "Read & prepare for a meeting" (Pre-Board stage 0)
 *   - ned        → "Read & prepare for a meeting" (Pre-Board stage 0)
 *                + "Review what's been submitted" (Board Pack stage 0)
 *                + "Send up your view"            (Board Pack stage 3)
 *
 * If there's an in-progress workflow of that type, "Resume" replaces "Start".
 */
const TILE_DEFS = [
  {
    key: "review_submissions",
    role: "executive", playType: "board_pack", stageHint: 0,
    label: "Review what your team sent",
    body: "Open the Q-cycle inbox, see who's reported and where the gaps are.",
    icon: Eye,
  },
  {
    key: "send_deck",
    role: "executive", playType: "board_pack", stageHint: 3,
    label: "Send the deck up",
    body: "Move a finalised report to the next reviewer in your chain.",
    icon: Send,
  },
  {
    key: "prepare_meeting",
    role: "any", playType: "pre_board", stageHint: 0,
    label: "Read & prepare for tomorrow",
    body: "Pull in a freshly-arrived board pack. Walk in with a one-page brief.",
    icon: FileText,
  },
];

export default function QuickActions() {
  const navigate = useNavigate();
  const { activeContext, activeRole } = useAuth();
  const cid = activeContext?.id;
  const [plays, setPlays] = useState([]);
  const [starting, setStarting] = useState(null);

  const load = useCallback(async () => {
    if (!cid) return;
    try {
      const { data } = await api.get(`/contexts/${cid}/plays`);
      setPlays((data.plays || []).filter((p) => ["active", "paused"].includes(p.status)));
    } catch { setPlays([]); }
  }, [cid]);
  useEffect(() => { load(); }, [load]);

  const findExisting = (playType) => plays.find((p) => p.play_type === playType);

  const onStart = async (tile) => {
    if (!cid) { toast.error("No active context."); return; }
    setStarting(tile.key);
    const existing = findExisting(tile.playType);
    try {
      let playId;
      if (existing) {
        playId = existing.id;
        // Optional jump to the requested stage if not already there.
        if (existing.current_stage !== tile.stageHint) {
          await api.post(`/contexts/${cid}/plays/${existing.id}/jump`, {
            stage_idx: tile.stageHint, confirm: true,
          });
        }
      } else {
        const { data } = await api.post(`/contexts/${cid}/plays`, { play_type: tile.playType });
        playId = data.play.id;
        if (tile.stageHint > 0) {
          await api.post(`/contexts/${cid}/plays/${playId}/jump`, {
            stage_idx: tile.stageHint, confirm: true,
          });
        }
      }
      navigate(`/app/plays/${playId}`);
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setStarting(null); }
  };

  // Filter tiles by active role (executive sees executive + any; ned sees ned + any)
  const visible = TILE_DEFS.filter((t) =>
    t.role === "any" ||
    (activeRole === "executive" && t.role === "executive") ||
    (activeRole === "ned" && (t.role === "ned" || t.role === "executive")) // NEDs sometimes review too
  );

  if (!cid) return null;

  return (
    <section className="mb-7 shrink-0" data-testid="home-quick-actions">
      <p className="akki-overline mb-3">Quick actions</p>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {visible.map((t) => {
          const existing = findExisting(t.playType);
          const Icon = t.icon;
          return (
            <button
              key={t.key}
              onClick={() => onStart(t)}
              disabled={starting === t.key}
              className="text-left bg-white border border-[var(--rule)] hover:border-[var(--accent)]/40 rounded-lg p-4 transition-colors group flex flex-col h-full"
              data-testid={`home-action-${t.key}`}
            >
              <div className="flex items-start gap-3 mb-2">
                <Icon className="w-4 h-4 text-[var(--accent)] mt-1 shrink-0" strokeWidth={1.7} />
                <p className="akki-serif text-[16px] text-[var(--ink)] leading-tight flex-1">{t.label}</p>
              </div>
              <p className="text-[12.5px] text-[var(--deep)] italic leading-relaxed mb-3 flex-1">{t.body}</p>
              <p className="text-[11.5px] text-[var(--accent)] inline-flex items-center gap-1 group-hover:underline">
                {existing ? "Resume" : "Start"} <ArrowRight className="w-3 h-3" />
              </p>
            </button>
          );
        })}
      </div>
    </section>
  );
}
