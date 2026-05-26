import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuLabel, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { AtSign, Check, Inbox } from "lucide-react";

/** Polls the current context's mention inbox every 60s and renders a bell
 *  with an unread count. Clicking an item marks it read and navigates to
 *  the artefact where the mention was posted. */
export default function MentionInbox() {
  const { activeContext } = useAuth();
  const contextId = activeContext?.id;
  const navigate = useNavigate();
  const [mentions, setMentions] = useState([]);
  const [open, setOpen] = useState(false);

  const load = useCallback(async () => {
    if (!contextId) return;
    try {
      const { data } = await api.get(`/contexts/${contextId}/mentions`, { params: { limit: 20 } });
      setMentions(data || []);
    } catch { /* silent — bell hides if endpoint fails */ }
  }, [contextId]);

  useEffect(() => {
    load();
    const h = setInterval(load, 60_000);
    return () => clearInterval(h);
  }, [load]);

  const unread = useMemo(() => mentions.filter((m) => !m.read).length, [mentions]);

  const onOpen = async (m) => {
    try { await api.post(`/contexts/${contextId}/mentions/${m.id}/read`); } catch { /* ignore */ }
    setMentions((prev) => prev.map((x) => (x.id === m.id ? { ...x, read: true } : x)));
    setOpen(false);
    // Route to the artefact that hosts the comment
    if (m.artefact_type === "briefing") navigate("/app/prepare");
    else if (m.artefact_type === "document") navigate(`/app/work-studio?doc_id=${m.artefact_id}`); // E.4: drawer
    else if (m.artefact_type === "simulation") navigate("/app/simulate");
    else if (m.artefact_type === "signal") navigate("/app/prepare");
  };

  const markAllRead = async () => {
    const unreadOnes = mentions.filter((m) => !m.read);
    await Promise.all(
      unreadOnes.map((m) => api.post(`/contexts/${contextId}/mentions/${m.id}/read`).catch(() => null))
    );
    setMentions((prev) => prev.map((m) => ({ ...m, read: true })));
  };

  if (!contextId) return null;

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <button
          className="relative flex items-center px-2 py-1.5 text-[var(--deep)] hover:bg-[var(--cream-deep)] rounded-md transition-colors"
          data-testid="mention-inbox-btn"
          title="Mentions"
          aria-label={unread > 0 ? `Mentions · ${unread} unread` : "Mentions"}
        >
          {/* Phase-tidy 2026-05: was a second <Bell> sitting next to
              ReviewBadge in the top nav — two bells side-by-side is a
              UX bug. ReviewBadge keeps the bell (queue semantics);
              this Mentions inbox switches to <Inbox> so the two
              affordances are visually distinct. */}
          <Inbox className="w-4 h-4" strokeWidth={1.8} />
          {unread > 0 && (
            <span
              className="absolute -top-0.5 -right-0.5 min-w-[16px] h-[16px] px-[4px] bg-[var(--accent)] text-white text-[9px] font-semibold rounded-full flex items-center justify-center"
              data-testid="mention-inbox-count"
            >
              {unread > 9 ? "9+" : unread}
            </span>
          )}
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-80 rounded-md p-0 overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--rule)]">
          <DropdownMenuLabel className="p-0 text-[10px] uppercase tracking-[0.2em] text-[var(--muted)] font-normal">
            <span className="flex items-center gap-1.5">
              <AtSign className="w-3 h-3" /> Mentions
            </span>
          </DropdownMenuLabel>
          {unread > 0 && (
            <button
              onClick={markAllRead}
              className="text-[11px] text-[var(--accent)] hover:underline flex items-center gap-1"
              data-testid="mention-inbox-mark-all-read"
            >
              <Check className="w-3 h-3" /> Mark all read
            </button>
          )}
        </div>
        <div className="max-h-96 overflow-y-auto" data-testid="mention-inbox-list">
          {mentions.length === 0 ? (
            <p className="px-4 py-8 text-center text-[12px] text-[var(--muted)] italic">
              No mentions yet. You'll get pinged when someone @-mentions you in this context.
            </p>
          ) : (
            mentions.map((m) => (
              <button
                key={m.id}
                onClick={() => onOpen(m)}
                className={`w-full text-left px-4 py-3 border-b border-[var(--rule)] last:border-0 hover:bg-[var(--cream-deep)] transition-colors ${
                  !m.read ? "bg-[var(--accent-soft)]/40" : ""
                }`}
                data-testid={`mention-item-${m.id}`}
              >
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-[11.5px] font-medium text-[var(--ink)]">{m.source_name || "Someone"}</span>
                  <span className="text-[10px] text-[var(--muted)]">· {m.artefact_type}</span>
                  {!m.read && (
                    <span className="ml-auto w-1.5 h-1.5 rounded-full bg-[var(--accent)]" />
                  )}
                </div>
                <p className="text-[12px] text-[var(--deep)] leading-snug line-clamp-2 akki-serif italic">
                  "{m.preview}"
                </p>
                <p className="text-[10px] text-[var(--muted)] mt-1">
                  {formatRel(m.created_at)}
                </p>
              </button>
            ))
          )}
        </div>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function formatRel(ts) {
  if (!ts) return "";
  const diffSec = (Date.now() - new Date(ts).getTime()) / 1000;
  if (diffSec < 60) return "just now";
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`;
  if (diffSec < 86400 * 7) return `${Math.floor(diffSec / 86400)}d ago`;
  return new Date(ts).toLocaleDateString();
}
