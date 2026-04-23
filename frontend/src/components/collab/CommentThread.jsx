import React, { useCallback, useEffect, useMemo, useState } from "react";
import { api, apiErrorMessage } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import {
  MessageSquare, Send, Loader2, AtSign, Reply, Trash2,
} from "lucide-react";

/**
 * Threaded comments on any AKKI artefact: signal · briefing · document · simulation.
 * Flat list with single-level replies via parent_id. Renders inline in host surface.
 *
 * Props:
 *   artefactType: "signal" | "briefing" | "document" | "simulation"
 *   artefactId:   string (uuid)
 *   compact?:     boolean — tighter spacing for popovers
 */
export default function CommentThread({ artefactType, artefactId, compact = false }) {
  const { account, activeContext } = useAuth();
  const contextId = activeContext?.id;
  const [comments, setComments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [body, setBody] = useState("");
  const [posting, setPosting] = useState(false);
  const [replyTo, setReplyTo] = useState(null); // comment being replied to

  const load = useCallback(async () => {
    if (!contextId || !artefactType || !artefactId) return;
    try {
      setLoading(true);
      const { data } = await api.get(
        `/contexts/${contextId}/${artefactType}/${artefactId}/comments`
      );
      setComments(data);
    } catch (e) {
      toast.error(apiErrorMessage(e));
    } finally {
      setLoading(false);
    }
  }, [contextId, artefactType, artefactId]);

  useEffect(() => { load(); }, [load]);

  const onPost = async () => {
    const text = body.trim();
    if (!text) return;
    setPosting(true);
    try {
      const { data } = await api.post(
        `/contexts/${contextId}/${artefactType}/${artefactId}/comments`,
        { body: text, parent_id: replyTo?.id || null },
      );
      setComments((prev) => [...prev, data]);
      setBody("");
      setReplyTo(null);
      if ((data.mentions || []).length > 0) {
        toast.success(`Posted. Pinged ${data.mentions.length} colleague${data.mentions.length > 1 ? "s" : ""}.`);
      }
    } catch (e) {
      toast.error(apiErrorMessage(e));
    } finally {
      setPosting(false);
    }
  };

  const onDelete = async (c) => {
    try {
      await api.delete(`/contexts/${contextId}/comments/${c.id}`);
      setComments((prev) => prev.filter((x) => x.id !== c.id));
    } catch (e) { toast.error(apiErrorMessage(e)); }
  };

  // Group: top-level + replies
  const { roots, childrenByParent } = useMemo(() => {
    const kids = {};
    const top = [];
    comments.forEach((c) => {
      if (c.parent_id) {
        (kids[c.parent_id] = kids[c.parent_id] || []).push(c);
      } else {
        top.push(c);
      }
    });
    return { roots: top, childrenByParent: kids };
  }, [comments]);

  const padding = compact ? "p-3" : "p-4";

  return (
    <div className={`bg-[var(--cream)] border border-[var(--rule)] rounded-md ${padding}`} data-testid={`comments-${artefactType}-${artefactId}`}>
      <div className="flex items-center gap-2 mb-3">
        <MessageSquare className="w-3.5 h-3.5 text-[var(--accent)]" strokeWidth={1.8} />
        <p className="akki-overline">Discussion · {comments.length}</p>
      </div>

      {loading ? (
        <p className="text-[12px] text-[var(--muted)] italic py-2">Loading…</p>
      ) : roots.length === 0 ? (
        <p className="text-[12.5px] text-[var(--muted)] italic py-2">
          No comments yet. Be the first — use <span className="text-[var(--ink)]">@name</span> to ping a colleague.
        </p>
      ) : (
        <div className={`space-y-${compact ? "3" : "4"}`} data-testid="comments-list">
          {roots.map((c) => (
            <CommentItem
              key={c.id}
              c={c}
              replies={childrenByParent[c.id] || []}
              currentAccountId={account?.id}
              onReply={() => setReplyTo(c)}
              onDelete={onDelete}
            />
          ))}
        </div>
      )}

      {/* Composer */}
      <div className="mt-4 pt-3 border-t border-[var(--rule)]">
        {replyTo && (
          <div className="flex items-center gap-2 text-[11px] text-[var(--muted)] mb-2">
            <Reply className="w-3 h-3" />
            <span>Replying to <span className="text-[var(--ink)] font-medium">{replyTo.author_name}</span></span>
            <button
              onClick={() => setReplyTo(null)}
              className="ml-auto text-[var(--accent)] hover:underline"
              data-testid="comment-cancel-reply"
            >
              cancel
            </button>
          </div>
        )}
        <textarea
          value={body}
          onChange={(e) => setBody(e.target.value)}
          placeholder={replyTo ? "Write your reply…" : "Leave a note for the board. Use @name to ping someone."}
          rows={compact ? 2 : 3}
          className="w-full bg-white border border-[var(--rule)] rounded-sm text-[13px] p-2.5 resize-none focus:outline-none focus:border-[var(--accent)] akki-serif leading-relaxed"
          data-testid="comment-composer"
        />
        <div className="flex items-center justify-between mt-2">
          <p className="text-[10.5px] text-[var(--muted)] flex items-center gap-1">
            <AtSign className="w-3 h-3" /> Mention context members by @email-prefix or @first-name.
          </p>
          <Button
            onClick={onPost}
            disabled={posting || !body.trim()}
            className="bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white rounded-sm h-8 px-3 text-[12px] font-medium"
            data-testid="comment-post-btn"
          >
            {posting
              ? <><Loader2 className="w-3 h-3 mr-1.5 animate-spin" /> Posting…</>
              : <><Send className="w-3 h-3 mr-1.5" /> Post</>}
          </Button>
        </div>
      </div>
    </div>
  );
}

function CommentItem({ c, replies, currentAccountId, onReply, onDelete }) {
  const initials = (c.author_name || c.author_email || "?").trim().charAt(0).toUpperCase();
  const isMine = currentAccountId === c.author_id;
  return (
    <div className="akki-fade-up" data-testid={`comment-${c.id}`}>
      <div className="flex gap-3">
        <div className="w-7 h-7 rounded-full bg-[var(--navy)] text-white text-[11px] font-semibold flex items-center justify-center shrink-0">
          {initials}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-[12.5px] font-medium text-[var(--ink)]">{c.author_name || c.author_email}</span>
            <span className="text-[10.5px] text-[var(--muted)]">· {formatRel(c.created_at)}</span>
            {(c.mentions || []).length > 0 && (
              <span className="text-[10px] uppercase tracking-wider text-[var(--accent)] bg-[var(--accent-soft)] px-1.5 py-0.5 rounded">
                @{c.mentions.length}
              </span>
            )}
          </div>
          <p className="akki-serif text-[14px] text-[var(--deep)] leading-[1.6] mt-1 whitespace-pre-wrap break-words">
            {renderBody(c.body)}
          </p>
          <div className="flex items-center gap-4 mt-1.5 text-[11px]">
            <button
              onClick={onReply}
              className="akki-gesture text-[11.5px]"
              data-testid={`comment-reply-${c.id}`}
            >
              <Reply className="w-3 h-3" /> Reply
            </button>
            {isMine && (
              <button
                onClick={() => onDelete(c)}
                className="text-[var(--muted)] hover:text-red-600 flex items-center gap-1"
                data-testid={`comment-delete-${c.id}`}
              >
                <Trash2 className="w-3 h-3" /> Delete
              </button>
            )}
          </div>
        </div>
      </div>

      {replies.length > 0 && (
        <div className="ml-10 mt-3 space-y-3 pl-3 border-l-2 border-[var(--rule)]" data-testid={`comment-replies-${c.id}`}>
          {replies.map((r) => {
            const rInitials = (r.author_name || r.author_email || "?").charAt(0).toUpperCase();
            const rIsMine = currentAccountId === r.author_id;
            return (
              <div key={r.id} className="akki-fade-up" data-testid={`comment-${r.id}`}>
                <div className="flex gap-2.5">
                  <div className="w-6 h-6 rounded-full bg-[var(--navy)] text-white text-[10px] font-semibold flex items-center justify-center shrink-0">
                    {rInitials}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-[12px] font-medium text-[var(--ink)]">{r.author_name || r.author_email}</span>
                      <span className="text-[10.5px] text-[var(--muted)]">· {formatRel(r.created_at)}</span>
                    </div>
                    <p className="akki-serif text-[13.5px] text-[var(--deep)] leading-[1.55] mt-0.5 whitespace-pre-wrap break-words">
                      {renderBody(r.body)}
                    </p>
                    {rIsMine && (
                      <button
                        onClick={() => onDelete(r)}
                        className="text-[10.5px] text-[var(--muted)] hover:text-red-600 flex items-center gap-1 mt-1"
                        data-testid={`comment-delete-${r.id}`}
                      >
                        <Trash2 className="w-2.5 h-2.5" /> Delete
                      </button>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// Highlight @mentions visually; leaves rest as plain text.
function renderBody(body) {
  const parts = body.split(/(@[A-Za-z0-9_.\-@]+)/g);
  return parts.map((p, i) =>
    p.startsWith("@")
      ? <span key={i} className="text-[var(--accent)] font-medium">{p}</span>
      : <React.Fragment key={i}>{p}</React.Fragment>
  );
}

function formatRel(ts) {
  if (!ts) return "just now";
  const diffSec = (Date.now() - new Date(ts).getTime()) / 1000;
  if (diffSec < 60) return "just now";
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`;
  if (diffSec < 86400 * 7) return `${Math.floor(diffSec / 86400)}d ago`;
  return new Date(ts).toLocaleDateString();
}
