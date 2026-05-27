/**
 * Chat — AKKI's privacy-shielded multi-model conversation surface.
 *
 * Untethered from any company context. The whole point: an executive
 * can ask AKKI anything (think ChatGPT/Claude/Gemini) without exposing
 * internal materials in the clear, without paying for three separate
 * AI subscriptions, and with a bank-grade audit trail behind every
 * shielding decision.
 *
 *   • Sidebar: list of conversations + new-chat button
 *   • Header: model picker + shielding policy + audit gesture
 *   • Body:   message thread with shield badges per message
 *   • Footer: composer with sensitivity confirm dialog when auto-policy
 *             would shield and the user wants to bypass
 */
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams, Link, useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import AppShell from "@/components/layout/AppShell";
import { api, apiErrorMessage } from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Plus, Send, Loader2, Shield, ShieldOff, Trash2, MessageCircle,
  ChevronDown, FileLock2, Eye, AlertTriangle, Download,
  Search, Paperclip, X, FileText, StopCircle,
  Brain, ChevronRight, Info, ArchiveRestore, Trash,
  // Phase C fix bundle (2026-05-13) — ArrowLeft used by the
  // "Back to active chats" affordance on the archive list; missing
  // import was causing a runtime ReferenceError that crashed the
  // archive surface. Imported now.
  ArrowLeft,
  // Phase C Chat cleanup (2026-05-26) — three-dot per-thread menu.
  MoreVertical,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
// Phase C (2026-05-13) — Synisense audit panel + protective layer
// intervention rendering. Components live under components/chat/ so
// other consumer surfaces (Solva, Work Studio) can reuse them in
// later phases.
import AuditPanel from "@/components/chat/AuditPanel";
import AggregateStrip from "@/components/chat/AggregateStrip";
import ProtectiveInterventionCard from "@/components/chat/ProtectiveInterventionCard";
import { useMessagesSynisense } from "@/hooks/useMessagesSynisense";
import PerMessageSynisenseBadge from "@/components/chat/PerMessageSynisenseBadge";
import ProviderLine from "@/components/chat/ProviderLine";
import WorkspaceEntryGate from "@/components/transitions/WorkspaceEntryGate";
import rehypeHighlight from "rehype-highlight";
import "highlight.js/styles/github.css";
import ModelAvatar from "@/components/chat/ModelAvatar";
import MarkdownMessage from "@/components/chat/MarkdownMessage";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
// Phase C Chat cleanup (2026-05-26) — per-thread row menu (Claude
// pattern). Initial menu ships with "Delete" only; menu is left
// extensible for future per-thread actions.
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
} from "@/components/ui/dropdown-menu";

const POLICY_LABEL = {
  auto: "Auto-shield",
  always: "Always shield",
  off: "Off (acknowledge per send)",
};

const BAND_COLOR = {
  public: "bg-slate-100 text-slate-700 border-slate-200",
  internal: "bg-amber-50 text-amber-800 border-amber-200",
  confidential: "bg-orange-50 text-orange-800 border-orange-200",
  restricted: "bg-red-50 text-red-800 border-red-200",
};

function _humanBytes(n) {
  if (!n && n !== 0) return "";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(2)} MB`;
}

/**
 * Patch 26B — Cap a title at N word-tokens for prominent display.
 * Splits on whitespace, keeps first N, appends `…` if truncation
 * happened. Punctuation is treated as part of the adjacent word
 * (matches the "7 tokens" intent in the brief). Empty / short
 * titles pass through unchanged.
 */
function truncateTitleWords(title, n = 7) {
  if (!title) return "";
  const tokens = String(title).trim().split(/\s+/);
  if (tokens.length <= n) return title;
  return tokens.slice(0, n).join(" ") + "…";
}

/**
 * Patch 26E — Chat privacy-first phase captions.
 * Backend emits {type:"phase", phase:"reading_context"|...} on the
 * SSE stream. We render the corresponding label above the streaming
 * bubble. After 10s on the same phase, we swap to the stall message
 * so the user knows we haven't hung — *"Taking longer, but making
 * sure you are safe."*
 */
const CHAT_PRIVACY_LABELS = {
  reading_context: "Reading your context",
  shielding_input_a: "Making your data anonymous",
  shielding_input_b: "Identifying and removing identifiers",
  reasoning:       "Thinking privately on your behalf",
  drafting:        "Drafting a response",
  refining:        "Polishing",
  _stall:          "Taking longer, but making sure you are safe.",
};
// Module-level rotation counter for shielding_input phrasing. Persists
// across renders so phrasings genuinely alternate per request.
let _shieldRotationCounter = 0;

function ChatPhaseCaption({ phase }) {
  const [stalled, setStalled] = React.useState(false);
  const [rotation] = React.useState(() => _shieldRotationCounter++);
  React.useEffect(() => {
    setStalled(false);
    const t = setTimeout(() => setStalled(true), 10000);
    return () => clearTimeout(t);
  }, [phase]);

  let label;
  if (stalled) {
    label = CHAT_PRIVACY_LABELS._stall;
  } else if (phase === "shielding_input") {
    label = rotation % 2 === 0
      ? CHAT_PRIVACY_LABELS.shielding_input_a
      : CHAT_PRIVACY_LABELS.shielding_input_b;
  } else {
    label = CHAT_PRIVACY_LABELS[phase] || "";
  }
  if (!label) return null;
  return (
    <p
      className="text-[10.5px] uppercase tracking-[0.18em] font-mono text-[var(--muted)] mb-2"
      data-testid="chat-phase-label"
      data-phase={phase}
      data-stalled={stalled || undefined}
    >
      {label}
    </p>
  );
}

export default function Chat() {
  const { activeContext } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const [models, setModels] = useState([]);
  const [defaultModel, setDefaultModel] = useState("claude-sonnet-4-5");
  const [chats, setChats] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const [activeChat, setActiveChat] = useState(null);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [loading, setLoading] = useState(true);
  const [bypassDlg, setBypassDlg] = useState(null); // {detected}
  const [auditOpen, setAuditOpen] = useState(false);
  const messagesEndRef = useRef(null);

  // K1 (2026-05-12) — Per-message Synisense badge.
  // We batch-fetch redaction counts for visible messages on a single
  // 30s loop (one request per message, but coalesced into a single
  // CHAT sprint (2026-05-12) — batched per-message Synisense metrics
  // (single POST, no N+1). The hook polls every 30s while the chat is
  // open so the count ticks up as audit rows land.
  const assistantMsgIds = useMemo(
    () => (activeChat?.messages || []).filter((m) => m.role !== "user" && m.id).map((m) => m.id),
    [activeChat?.messages]
  );
  const { map: messageSynisense } = useMessagesSynisense({
    chatId: activeChat?.id,
    msgIds: assistantMsgIds,
  });



  // Phase B.1 — Cancel in flight via AbortController. We hold the
  // controller in a ref so the Cancel button reads the current value
  // without re-rendering on every keystroke.
  const abortRef = useRef(null);

  // Phase B.1 — Attachments staged for the next turn. Each entry is
  // {document_id, name, size_bytes, sensitivity, char_len}. Cleared
  // when the message is sent (success or cancel) or when the user
  // removes the chip.
  const [attachments, setAttachments] = useState([]);

  // Phase B.1 — Conversation search across the active context. When
  // searchQ is non-empty (>= 2 chars), the visible chats list is the
  // server's /chats/search hits rather than the full list.
  const [searchQ, setSearchQ] = useState("");
  const [searchHits, setSearchHits] = useState(null);   // null = no search active
  const [searching, setSearching] = useState(false);

  // Phase B.2 — "Think harder" toggle. Per-message state: when ON, the
  // next send carries `force_class: "strategic_deliverable"` and
  // `show_pass_1: true`. Resets to false after every successful send so
  // the user has to opt in for each turn (per memo Item 8 — silent
  // four-check is the default, visible reasoning is the exception).
  const [thinkHarder, setThinkHarder] = useState(false);

  // Phase C Chat cleanup (2026-05-26, post-test fix): lock body
  // overflow while the chat surface is mounted. The AppShell's
  // `.min-h-screen` parent + tabs row inflate the document height
  // above the viewport (~1185px on a 1080px viewport), which lets
  // the page scroll despite the chat-page container being
  // `overflow-hidden`. Locking body overflow stops scroll at the
  // root, so only the chat-page's inner scrollable children
  // (chat-list + chat-messages) can scroll — matching the brief.
  useEffect(() => {
    const prevBody = document.body.style.overflow;
    const prevHtml = document.documentElement.style.overflow;
    document.body.style.overflow = "hidden";
    document.documentElement.style.overflow = "hidden";
    window.scrollTo(0, 0);
    return () => {
      document.body.style.overflow = prevBody;
      document.documentElement.style.overflow = prevHtml;
    };
  }, []);

  // ── Bootstrap: fetch models + chats list
  useEffect(() => {
    (async () => {
      try {
        const [m, c] = await Promise.all([
          api.get("/chat/models"),
          api.get("/chats"),
        ]);
        setModels(m.data?.models || []);
        setDefaultModel(m.data?.default_model_id || "claude-sonnet-4-5");
        setChats(c.data || []);
        if ((c.data || []).length > 0) setActiveId(c.data[0].id);
      } catch (e) { toast.error(apiErrorMessage(e)); }
      finally { setLoading(false); }
    })();
  }, []);

  // ── Load active chat
  useEffect(() => {
    if (!activeId) { setActiveChat(null); return; }
    (async () => {
      try {
        const { data } = await api.get(`/chats/${activeId}`);
        setActiveChat(data);
      } catch (e) { toast.error(apiErrorMessage(e)); }
    })();
  }, [activeId]);

  // Phase A (2026-05-10) — scroll-pin lock with ResizeObserver.
  //
  // Symptoms before this rewrite:
  //   1. scrollIntoView({block:"end"}) fired per delta caused viewport
  //      jitter and "yank" when layout shifted (e.g. when a code block
  //      gained syntax highlighting).
  //   2. The 100 px threshold for "user has scrolled up" let small
  //      reading scrolls trigger auto-scroll later, yanking the user.
  //
  // Replacement:
  //   - `pinnedRef` is the single source of truth: when true, new
  //     content auto-pins to the bottom; when false (user scrolled up
  //     >64 px), we never yank.
  //   - User scroll events update `pinnedRef` synchronously.
  //   - A ResizeObserver on the inner messages list fires whenever
  //     content grows (token arrives, code block highlights, image
  //     loads, etc). If pinnedRef is true, we write
  //     `el.scrollTop = el.scrollHeight - el.clientHeight` — one DOM
  //     write per resize, no scrollIntoView, no smooth, no jitter.
  //   - "Jump to latest" pill appears only when pinnedRef is false
  //     AND new content has arrived since the user scrolled up.
  const scrollContainerRef = useRef(null);
  const messagesInnerRef = useRef(null);
  const pinnedRef = useRef(true);
  const [userScrolledUp, setUserScrolledUp] = useState(false);
  const PIN_THRESHOLD_PX = 64;

  const scrollToLatest = useCallback(() => {
    const el = scrollContainerRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight - el.clientHeight;
    pinnedRef.current = true;
    setUserScrolledUp(false);
  }, []);

  // User-scroll handler — the only thing that flips pinnedRef false.
  const onMessagesScroll = useCallback(() => {
    const el = scrollContainerRef.current;
    if (!el) return;
    const dist = el.scrollHeight - el.scrollTop - el.clientHeight;
    const pinned = dist <= PIN_THRESHOLD_PX;
    if (pinned !== pinnedRef.current) {
      pinnedRef.current = pinned;
      setUserScrolledUp(!pinned);
    }
  }, []);

  // ResizeObserver on the inner content node — fires once per layout
  // change, which is exactly when we want to consider re-pinning.
  // Replaces the per-delta useEffect chain that fired on every chunk.
  useEffect(() => {
    const inner = messagesInnerRef.current;
    const outer = scrollContainerRef.current;
    if (!inner || !outer || typeof ResizeObserver === "undefined") return undefined;
    const ro = new ResizeObserver(() => {
      if (pinnedRef.current) {
        outer.scrollTop = outer.scrollHeight - outer.clientHeight;
      }
    });
    ro.observe(inner);
    return () => ro.disconnect();
  }, [activeId]);

  // Re-pin when the conversation switches or a fresh send begins.
  useEffect(() => {
    pinnedRef.current = true;
    setUserScrolledUp(false);
    const el = scrollContainerRef.current;
    if (el) el.scrollTop = el.scrollHeight - el.clientHeight;
  }, [activeId, sending]);

  // Pre-fill the composer when arriving with ?prompt=… (e.g. from the
  // sandbox tutorial card or the "Continue in Chat" chip on a saved
  // brief). One-shot: we strip the param after consuming it. With
  // ?new=1 we also create a fresh conversation first so the seed
  // doesn't pollute whichever chat happened to be active.
  //
  // Phase C.3 — also support ?chat_id=<id>&attach=<doc_id> arriving
  // from "Continue in chat" buttons on Work Studio. The chat is
  // already created server-side; we just select it and push the
  // artefact's document onto the attachments state so the chip is
  // visible on first paint.
  useEffect(() => {
    const p = searchParams.get("prompt");
    const wantNew = searchParams.get("new") === "1";
    const seedTitle = searchParams.get("seed_title");
    const docId = searchParams.get("doc");
    const continueChatId = searchParams.get("chat_id");
    const continueAttachId = searchParams.get("attach");
    // Phase D.3 (2026-05-26) — generic linked-context entry. When the
    // URL carries `?ctx_type=...&ctx_id=...`, mint a new chat with
    // `linked_context: {ctx_type, ctx_id}` on the body. The backend
    // resolves the title + excerpt and persists it on the chat row;
    // the chip renders from `activeChat.linked_context` once the
    // chat is loaded. Document-typed ctx is routed through the
    // legacy `?doc=...` path (which also calls /chats/{id}/attach)
    // so the in-thread attachment chip flow keeps working — the
    // linked_context payload is set alongside.
    const ctxType = (searchParams.get("ctx_type") || "").trim();
    const ctxId   = (searchParams.get("ctx_id") || "").trim();
    if (!p && !seedTitle && !docId && !continueChatId && !continueAttachId
        && !(ctxType && ctxId)) return;
    // Iter57 — when the trigger is ?doc=<id>, we *must* wait for the
    // active context to hydrate before we can resolve the doc title and
    // mint a chat. Re-firing this effect when activeContext.id changes
    // closes the race that the testing pass surfaced.
    if ((docId || continueAttachId || (ctxType && ctxId)) && !activeContext?.id) return;
    let cancelled = false;
    (async () => {
      try {
        // C.3 — Continue-in-chat from Work Studio: chat already exists,
        // and we may also have an artefact doc to attach as a chip.
        if (continueChatId && activeContext?.id) {
          if (!cancelled) setActiveId(continueChatId);
          if (continueAttachId) {
            try {
              const { data: doc } = await api.get(
                `/contexts/${activeContext.id}/documents/${continueAttachId}`,
              );
              if (!cancelled && doc) {
                // Map the document shape to the same chip shape
                // /chats/{cid}/attach returns, so the existing render
                // path needs no change.
                const chip = {
                  document_id: doc.id || continueAttachId,
                  chat_id: continueChatId,
                  context_id: activeContext.id,
                  name: doc.name || doc.original_filename || "Artefact",
                  original_filename: doc.original_filename || doc.name,
                  mime_type: doc.mime_type || "application/octet-stream",
                  size_bytes: doc.size_bytes || 0,
                  char_len: doc.extracted_chars || 0,
                  sensitivity: {
                    score: doc.sensitivity_score || 0,
                    classification: (doc.sensitivity_band || "internal").toUpperCase(),
                    label: (doc.sensitivity_label || "INTERNAL"),
                    reasons: [],
                  },
                  storage_key: doc.storage_key || "",
                  created_at: doc.created_at || "",
                };
                setAttachments((prev) => {
                  if (prev.some((a) => a.document_id === chip.document_id)) return prev;
                  return [...prev, chip];
                });
              }
            } catch { /* best-effort — leave chip area empty if fetch fails */ }
          }
        } else if (docId && activeContext?.id) {
          // Iter57 — when user clicks "Continue in Chat" from a document,
          // we land here with ?doc=<id>. Spin up a fresh conversation
          // titled with the doc's name (resolved client-side) and
          // pre-fill the composer so they can ask their question.
          //
          // Phase D.3 (2026-05-26) — additionally CALL /chats/{cid}/attach
          // so the doc lands as a visible attachment chip AND its body
          // gets pulled into the first AI message's system context
          // (existing chat send pipeline already injects attachments).
          // Previously the prompt mentioned the doc by name only —
          // the AI had no access to the doc body.
          let docTitle = "this document";
          let docPayload = null;
          try {
            const { data } = await api.get(`/contexts/${activeContext.id}/documents/${docId}`);
            docTitle = data?.name || data?.original_filename || docTitle;
            docPayload = data;
          } catch { /* fall through with default title */ }
          // Workstream A.1 — pass context_id so the chat shows in the
          // active-context-filtered sidebar list and can accept attachments.
          const { data } = await api.post("/chats", {
            title: `Re: ${docTitle.slice(0, 80)}`,
            model_id: defaultModel,
            shielding_policy: "auto",
            context_id: activeContext.id,
          });
          if (!cancelled) {
            setChats((prev) => [data, ...prev]);
            setActiveId(data.id);
            setInput(p || `What's the most important thing for me to know from "${docTitle}"?`);
            // Phase D.3 — register the doc as a chat attachment so the
            // first AI message has access to its body. Best-effort: a
            // failure here still lands the user in the new chat with
            // the pre-filled prompt (graceful degradation, no toast).
            if (docPayload?.id) {
              try {
                const { data: attached } = await api.post(
                  `/chats/${data.id}/attach`,
                  { document_id: docPayload.id },
                );
                if (!cancelled && attached) {
                  const chip = {
                    document_id: docPayload.id,
                    chat_id: data.id,
                    context_id: activeContext.id,
                    name: docPayload.name || docPayload.original_filename || "Document",
                    original_filename: docPayload.original_filename || docPayload.name,
                    mime_type: docPayload.mime_type || "application/octet-stream",
                    size_bytes: docPayload.size_bytes || 0,
                    char_len: docPayload.extracted_chars || 0,
                    sensitivity: {
                      score: docPayload.sensitivity_score || 0,
                      classification: (docPayload.sensitivity_band || "internal").toUpperCase(),
                      label: (docPayload.sensitivity_label || "INTERNAL"),
                      reasons: [],
                    },
                    storage_key: docPayload.storage_key || "",
                    created_at: docPayload.created_at || "",
                    linked_context: true,
                  };
                  setAttachments((prev) => {
                    if (prev.some((a) => a.document_id === chip.document_id)) return prev;
                    return [...prev, chip];
                  });
                }
              } catch { /* best-effort — chat still works without the attached body */ }
            }
          }
        } else if (ctxType && ctxId && activeContext?.id) {
          // Phase D.3 (2026-05-26) — generic linked-context entry. The
          // backend resolves the title + excerpt + href and persists
          // `chat.linked_context` on the row. We then re-fetch the
          // chat so the "Reading: …" chip renders from the canonical
          // server-side payload (rather than client-side guesses
          // about title/href).
          try {
            const { data: created } = await api.post("/chats", {
              title: seedTitle || "New conversation",
              model_id: defaultModel,
              shielding_policy: "auto",
              context_id: activeContext.id,
              linked_context: { ctx_type: ctxType, ctx_id: ctxId },
            });
            if (cancelled) return;
            setChats((prev) => [created, ...prev]);
            setActiveId(created.id);
            if (p) setInput(p);
          } catch {
            // Resolution failed on the server side — fall back to a
            // bare chat so the user isn't stranded.
            try {
              const { data: bare } = await api.post("/chats", {
                title: seedTitle || "New conversation",
                model_id: defaultModel,
                shielding_policy: "auto",
                context_id: activeContext.id,
              });
              if (cancelled) return;
              setChats((prev) => [bare, ...prev]);
              setActiveId(bare.id);
              if (p) setInput(p);
            } catch { /* swallow */ }
          }
        } else if (wantNew) {
          if (!activeContext?.id) {
            toast.error("Pick a company first to continue from a brief.");
          } else {
            // Workstream A.1 — chats minted from "Continue from brief"
            // must be tethered to the active context.
            const { data } = await api.post("/chats", {
              title: seedTitle || "Continued from a brief",
              model_id: defaultModel,
              shielding_policy: "auto",
              context_id: activeContext.id,
            });
            if (cancelled) return;
            setChats((prev) => [data, ...prev]);
            setActiveId(data.id);
            if (p) setInput(p);
          }
        } else if (p) {
          setInput(p);
        }
      } catch { /* swallow — just leave the composer empty */ }
      const next = new URLSearchParams(searchParams);
      next.delete("prompt");
      next.delete("new");
      next.delete("seed_title");
      next.delete("doc");
      next.delete("chat_id");
      next.delete("attach");
      next.delete("ctx_type");
      next.delete("ctx_id");
      setSearchParams(next, { replace: true });
    })();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams.toString(), activeContext?.id]);

  const onNewChat = async () => {
    // Workstream A.1 — block when no active context is selected.
    // Without context_id, the chat lands as an orphan and gets
    // filtered out of the per-context list (the AC-01 root cause).
    if (!activeContext?.id) {
      toast.error("Pick a company first to start a chat.");
      return;
    }
    try {
      const { data } = await api.post("/chats", {
        title: "New conversation",
        model_id: defaultModel,
        shielding_policy: "auto",
        context_id: activeContext.id,
      });
      setChats((prev) => [data, ...prev]);
      setActiveId(data.id);
    } catch (e) { toast.error(apiErrorMessage(e)); }
  };

  // Phase D.3 (2026-05-26) — remove the linked source item from the
  // active chat. Persists `linked_context: null` via PATCH so the chip
  // doesn't reappear on resume. Subsequent turns won't inject the
  // item's summary into the system context.
  const onRemoveLinkedContext = async () => {
    if (!activeId) return;
    try {
      const { data } = await api.patch(`/chats/${activeId}`, {
        clear_linked_context: true,
      });
      setActiveChat((prev) => {
        const merged = { ...(prev || {}), ...data };
        if (Object.prototype.hasOwnProperty.call(merged, "linked_context")) {
          delete merged.linked_context;
        }
        return merged;
      });
      setChats((prev) => prev.map((c) => {
        if (c.id !== activeId) return c;
        const merged = { ...c, ...data };
        delete merged.linked_context;
        return merged;
      }));
    } catch (e) { toast.error(apiErrorMessage(e)); }
  };

  const onArchive = async (id) => {
    try {
      await api.delete(`/chats/${id}`);
      setChats((prev) => prev.filter((c) => c.id !== id));
      if (activeId === id) setActiveId(null);
      // Phase C (2026-05-13) — when a chat is archived, surface the
      // "View archived" affordance so users know where to retrieve
      // or permanently delete archived conversations.
      toast.success("Chat archived. You can restore it from your Archived Chats.", {
        action: {
          label: "View archived",
          onClick: () => { window.location.href = "/app/chats/archived"; },
        },
      });
    } catch (e) { toast.error(apiErrorMessage(e)); }
  };

  const onPatch = async (patch) => {
    if (!activeId) return;
    try {
      const { data } = await api.patch(`/chats/${activeId}`, patch);
      setActiveChat((prev) => ({ ...(prev || {}), ...data }));
      setChats((prev) => prev.map((c) => c.id === activeId ? { ...c, ...data } : c));
    } catch (e) { toast.error(apiErrorMessage(e)); }
  };

  const sendMessage = useCallback(async (text, acknowledge_unshielded = false) => {
    if (!activeId) return;
    setSending(true);
    // Phase B.2 — capture Think-harder toggle BEFORE we reset it. The
    // toggle is per-turn: reset to false on every send so the user has
    // to opt in each time they want visible reasoning.
    const turnThinkHarder = thinkHarder;
    setThinkHarder(false);
    // Optimistic user bubble + a streaming assistant placeholder we
    // will fill in as deltas arrive. The placeholder id is local-only
    // and gets replaced by the real message_id once the terminal
    // `message` event lands.
    const optimisticUser = {
      id: `tmp-u-${Date.now()}`, role: "user", content: text,
      created_at: new Date().toISOString(),
    };
    const streamingId = `tmp-a-${Date.now()}`;
    const streamingPlaceholder = {
      id: streamingId, role: "assistant", content: "", streaming: true,
      created_at: new Date().toISOString(),
    };
    setActiveChat((prev) => ({
      ...(prev || {}),
      messages: [
        ...((prev || {}).messages || []),
        optimisticUser, streamingPlaceholder,
      ],
    }));
    setInput("");

    // Phase B.2 — SSE consumer via fetch + ReadableStream.
    // We use fetch (not EventSource) because:
    //   1. EventSource is GET-only; we need POST + JSON body.
    //   2. We need to send auth cookies + Bearer header alongside the
    //      body, which EventSource also doesn't support cleanly.
    // The endpoint emits text/event-stream; we parse "data: <json>\n\n"
    // frames. Server sends `delta` events (shielded text), one terminal
    // `message` event with the rehydrated `assistant_text`, and a
    // final `done` event. On terminal, we swap the streamed text for
    // the rehydrated string so PII / citations resolve correctly.
    const BACKEND = process.env.REACT_APP_BACKEND_URL || "";
    const tok = localStorage.getItem("akki_access_token");
    const headers = {
      "Content-Type": "application/json", "Accept": "text/event-stream",
    };
    if (tok) headers.Authorization = `Bearer ${tok}`;

    const applyStreamUpdate = (updater) => {
      setActiveChat((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          messages: (prev.messages || []).map((m) =>
            m.id === streamingId ? updater(m) : m,
          ),
        };
      });
    };

    let acknowledgementErrorPayload = null;
    let streamFailed = false;

    // Phase B.1 — AbortController for cancel-mid-stream.
    const ctrl = new AbortController();
    abortRef.current = ctrl;

    // Snapshot attachments for this turn — clear the chip set
    // immediately so the user can stage new ones for the next turn
    // without confusing the backend on a retry.
    const turnAttachments = attachments;
    const attachedDocIds = turnAttachments.map((a) => a.document_id);
    setAttachments([]);

    try {
      // Patch 24B — raw fetch() is required here because we need
      // ReadableStream support for SSE-style streaming, which axios
      // doesn't expose cleanly. The bearer token + active-context
      // headers are injected manually above (lines 420-424, 461).
      // eslint-disable-next-line no-restricted-syntax -- streaming SSE; axios cannot
      const resp = await fetch(`${BACKEND}/api/chats/${activeId}/messages/stream`, {
        method: "POST",
        credentials: "include",
        headers: {
          ...headers,
          // Phase A — every authenticated SPA call carries the
          // active context; raw fetch() doesn't go through the
          // axios interceptor in lib/api.js, so attach manually.
          ...(activeContext?.id ? { "X-Active-Context": activeContext.id } : {}),
        },
        signal: ctrl.signal,
        body: JSON.stringify({
          content: text,
          acknowledge_unshielded,
          attached_document_ids: attachedDocIds,
          // Phase B.2 — Think-harder forces the canonical two-pass
          // method AND visible Pass 1. The backend also detects cue
          // phrases ("think harder", "show your reasoning") in the
          // text itself, so a user who types the cue gets the same
          // outcome without the toggle.
          ...(turnThinkHarder
            ? { force_class: "strategic_deliverable", show_pass_1: true }
            : {}),
        }),
      });
      if (resp.status === 409) {
        const body = await resp.json().catch(() => ({}));
        if (body?.detail?.code === "shielding_acknowledgement_required") {
          acknowledgementErrorPayload = { text, detected: body.detail.detected };
        } else {
          throw new Error(body?.detail?.message || "shielding gate failed");
        }
      } else if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}`);
      } else {
        const reader = resp.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let buffer = "";
        let finalEvent = null;
        // eslint-disable-next-line no-constant-condition
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          // Parse complete frames (separated by \n\n).
          let sep;
          while ((sep = buffer.indexOf("\n\n")) >= 0) {
            const frame = buffer.slice(0, sep);
            buffer = buffer.slice(sep + 2);
            if (!frame.startsWith("data:")) continue;
            const json = frame.slice(5).trim();
            let ev;
            try { ev = JSON.parse(json); } catch { continue; }
            if (ev.type === "delta") {
              // Patch 26E — first delta means model is "drafting".
              // Subsequent deltas keep the phase steady on `drafting`.
              applyStreamUpdate((m) => ({
                ...m,
                content: (m.content || "") + ev.text,
                _phase: m._phase === "drafting" ? "drafting" : "drafting",
              }));
            } else if (ev.type === "phase") {
              // Patch 26E — backend emits {type:"phase", phase:"reading_context"|...}
              // at real boundaries. Stash the phase on the streaming
              // bubble so the privacy-first caption renders.
              applyStreamUpdate((m) => ({ ...m, _phase: ev.phase }));
            } else if (ev.type === "chat_renamed") {
              // Workstream B.2 — server auto-named the chat from the
              // first user message. Update sidebar + active header.
              const newTitle = ev.title || "";
              const targetChatId = ev.chat_id || activeId;
              if (newTitle && targetChatId) {
                setChats((prev) => prev.map((c) =>
                  c.id === targetChatId ? { ...c, title: newTitle } : c,
                ));
                setActiveChat((prev) =>
                  prev && prev.id === targetChatId ? { ...prev, title: newTitle } : prev,
                );
              }
            } else if (ev.type === "message") {
              finalEvent = ev;
              applyStreamUpdate((m) => {
                // Workstream A (2026-05-10) — flicker fix.
                // Skip the canonical-text swap when the streamed
                // text already matches the canonical assistant_text
                // (the no-PII case). The swap was visible as a
                // flicker even when the strings were identical
                // because React still ran the diff. When the strings
                // differ (PII redacted), we still swap — that's
                // correct and acceptable.
                const sameText = (m.content || "") === (ev.assistant_text || "");
                return {
                  ...m,
                  id: ev.message_id,
                  content: sameText ? m.content : ev.assistant_text,
                  model_id: ev.model,
                  citations: ev.citations || [],
                  streaming: false,
                  // Phase B.2 — propagate the structured two-pass + four-
                  // check + refusal metadata to the message bubble.
                  turn_class: ev.turn_class,
                  four_check_label: ev.four_check_label,
                  refusal_reason: ev.refusal_reason,
                  pass_1: ev.pass_1,
                  pass_2: ev.pass_2,
                  show_pass_1: ev.show_pass_1,
                  voice_violation: ev.voice_violation,
                };
              });
            } else if (ev.type === "error") {
              streamFailed = true;
              throw new Error(ev.message || "stream error");
            }
          }
        }
        if (finalEvent) {
          // Swap the optimistic user bubble for the persisted message_id-bearing
          // record so the audit pill matches once we re-hydrate the chat from
          // db. Keep the message order stable.
          setActiveChat((prev) => ({
            ...(prev || {}),
            messages: ((prev || {}).messages || []).map((m) =>
              m.id === optimisticUser.id ? { ...m, id: `committed-${Date.now()}` } : m,
            ),
          }));
          setChats((prev) => prev.map((c) => c.id === activeId ? {
            ...c,
            last_message_preview: (finalEvent.assistant_text || "").slice(0, 200),
            last_message_at: new Date().toISOString(),
            message_count: (c.message_count || 0) + 2,
          } : c));
        }
      }
    } catch (e) {
      streamFailed = true;
      // Phase B.1 — AbortError is a user-initiated cancel, not an
      // error. The backend has already persisted whatever was
      // streamed plus a `cancelled: true` audit row. Keep the
      // partial assistant bubble visible (don't strip it) and toast
      // the user softly.
      const isAbort = e?.name === "AbortError";
      if (isAbort) {
        setActiveChat((prev) => ({
          ...(prev || {}),
          messages: ((prev || {}).messages || []).map((m) =>
            m.id === streamingId ? { ...m, streaming: false, cancelled: true } : m,
          ),
        }));
        toast("Cancelled. Partial reply kept.", { duration: 2000 });
      } else {
        // Remove the streaming placeholder; reuse the same toast contract
        // as before so existing UX expectations hold.
        setActiveChat((prev) => ({
          ...(prev || {}),
          messages: ((prev || {}).messages || []).filter(
            (m) => m.id !== streamingId && m.id !== optimisticUser.id,
          ),
        }));
        toast.error(apiErrorMessage(e));
      }
    } finally {
      abortRef.current = null;
      if (acknowledgementErrorPayload) {
        // Remove placeholders and prompt the bypass dialog.
        setActiveChat((prev) => ({
          ...(prev || {}),
          messages: ((prev || {}).messages || []).filter(
            (m) => m.id !== streamingId && m.id !== optimisticUser.id,
          ),
        }));
        setBypassDlg(acknowledgementErrorPayload);
      }
      // Failsafe: if the stream silently ended without a `message`
      // event, scrub the placeholder so the UI doesn't get stuck.
      if (!streamFailed && !acknowledgementErrorPayload) {
        setActiveChat((prev) => {
          if (!prev) return prev;
          return {
            ...prev,
            messages: (prev.messages || []).filter(
              (m) => !(m.id === streamingId && m.streaming),
            ),
          };
        });
      }
      setSending(false);
    }
  }, [activeId, activeContext?.id, attachments, thinkHarder]);

  const onSubmit = () => {
    const text = input.trim();
    if (!text || sending) return;
    sendMessage(text);
  };

  const onCancel = () => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
  };

  // Phase B.1 — Conversation search. Debounced 250 ms.
  useEffect(() => {
    const q = searchQ.trim();
    if (q.length < 2) {
      setSearchHits(null);
      setSearching(false);
      return undefined;
    }
    let dead = false;
    setSearching(true);
    const t = setTimeout(async () => {
      try {
        const { data } = await api.get(`/chats/search?q=${encodeURIComponent(q)}`);
        if (!dead) setSearchHits(data?.items || []);
      } catch {
        if (!dead) setSearchHits([]);
      } finally {
        if (!dead) setSearching(false);
      }
    }, 250);
    return () => { dead = true; clearTimeout(t); };
  }, [searchQ]);

  // Phase B.1 — wipe the visible chats list when the active context
  // changes (Phase A switcher). The Phase A interceptor already
  // attaches X-Active-Context to subsequent calls; we just need to
  // re-fetch and reset transient state.
  useEffect(() => {
    if (!activeContext?.id) return;
    setChats([]);
    setActiveId(null);
    setActiveChat(null);
    setSearchQ("");
    setSearchHits(null);
    setAttachments([]);
    let dead = false;
    (async () => {
      try {
        const { data } = await api.get("/chats");
        if (!dead) setChats(data || []);
      } catch { /* noop */ }
    })();
    return () => { dead = true; };
  }, [activeContext?.id]);

  // Workstream B.5 — archive view state. When archiveOpen=true, the
  // sidebar swaps to the archived-chat list (with Restore + Permanently
  // Delete affordances). Active and archived lists are kept in two
  // separate state slots so flipping back is instant — no re-fetch
  // unless one expired in between.
  const [archiveOpen, setArchiveOpen] = useState(false);
  const [archivedChats, setArchivedChats] = useState([]);
  const [archiveLoading, setArchiveLoading] = useState(false);

  const openArchive = async () => {
    setArchiveOpen(true);
    setArchiveLoading(true);
    try {
      const { data } = await api.get("/chats?include_archived=true");
      // The backend returns active+archived merged; filter to archived
      // only for this view.
      setArchivedChats((data || []).filter((c) => c.status === "archived"));
    } catch (e) {
      toast.error(apiErrorMessage(e));
    } finally {
      setArchiveLoading(false);
    }
  };

  const closeArchive = () => {
    setArchiveOpen(false);
    setArchivedChats([]);
  };

  const onRestoreChat = async (id) => {
    try {
      await api.post(`/chats/${id}/restore`);
      // Move the chat back to the active list (refresh both).
      setArchivedChats((prev) => prev.filter((c) => c.id !== id));
      const { data } = await api.get("/chats");
      setChats(data || []);
      toast.success("Restored to active conversations");
    } catch (e) {
      toast.error(apiErrorMessage(e));
    }
  };

  const onHardDeleteChat = async (id) => {
    if (!window.confirm("Permanently delete this conversation? The audit trail is preserved but the messages cannot be recovered.")) return;
    try {
      await api.delete(`/chats/${id}?hard=true`);
      setArchivedChats((prev) => prev.filter((c) => c.id !== id));
      toast.success("Permanently deleted");
    } catch (e) {
      toast.error(apiErrorMessage(e));
    }
  };

  const onAttachFile = async (file) => {
    if (!activeId || !file) return;
    try {
      const fd = new FormData();
      fd.append("file", file);
      // Workstream B.8 — let the browser set the Content-Type
      // (including the multipart boundary). The previous explicit
      // header stripped the boundary, breaking uploads in legacy
      // browsers.
      const { data } = await api.post(
        `/chats/${activeId}/attach`, fd,
      );
      setAttachments((prev) => [...prev, data]);
      toast.success(`Attached: ${data.name}`);
    } catch (e) {
      toast.error(apiErrorMessage(e));
    }
  };

  const onRemoveAttachment = (docId) => {
    setAttachments((prev) => prev.filter((a) => a.document_id !== docId));
  };

  const activeModel = useMemo(
    () => models.find((m) => m.id === activeChat?.model_id),
    [models, activeChat?.model_id],
  );

  return (
    <AppShell>
      <WorkspaceEntryGate workspace="chat">
      <div className="lg:h-[calc(100vh-8rem)] h-[calc(100vh-4rem)] akki-w-wide grid grid-cols-1 lg:grid-cols-[300px_1fr] lg:gap-12 overflow-x-hidden overflow-hidden" data-testid="chat-page">
        {/* Phase F (2026-05-21) — boundary-removal pass. The aside
            and the main pane now sit on a single warm parchment
            surface with no enclosing rectangles. Hierarchy comes
            from whitespace, two AppShell-level hairlines, and the
            active-conversation parchment-light fill + 2px oxblood
            left edge. */}
        <aside className="bg-[var(--paper)] flex flex-col min-h-0" data-testid="chat-sidebar">
          {/* H.3 side-fix (2026-05-26) — Header tightening: reduced
              padding (px-3 py-3), 32px search input, single-line
              subline, smaller gap to list. */}
          <div className="px-3 pt-3 pb-2">
            <div className="flex items-center justify-between mb-1.5">
              <p className="akki-overline flex items-center gap-1.5">
                <MessageCircle className="w-3 h-3 text-[var(--accent)]" /> AKKI Chat
              </p>
              <Button
                onClick={onNewChat}
                size="sm"
                className="h-7 text-[11px] bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white px-2.5 rounded-md shadow-none"
                data-testid="chat-new-btn"
              >
                <Plus className="w-3 h-3 mr-1" /> New
              </Button>
            </div>
            <p className="text-[10px] text-[var(--muted)] truncate mb-2.5">
              Synisense-shielded · multi-model · audited
            </p>
            {/* Phase B.1 — Conversation search across this context.
                Substring match on title OR turn content; results
                replace the chat list while non-empty. */}
            <div className="relative">
              <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[var(--muted)]" />
              <input
                value={searchQ}
                onChange={(e) => setSearchQ(e.target.value)}
                placeholder="Search conversations…"
                className="w-full pl-7 pr-7 h-8 text-[13px] border-0 border-b border-[rgba(184,182,175,0.4)] rounded-none bg-transparent focus:outline-none focus:border-[var(--accent)]/60"
                data-testid="chat-search-input"
              />
              {searchQ && (
                <button
                  onClick={() => { setSearchQ(""); setSearchHits(null); }}
                  className="absolute right-1.5 top-1/2 -translate-y-1/2 p-0.5 text-[var(--muted)] hover:text-[var(--ink)]"
                  data-testid="chat-search-clear"
                  aria-label="Clear search"
                >
                  <X className="w-3 h-3" />
                </button>
              )}
            </div>
          </div>
          <div className="flex-1 overflow-y-auto px-1.5 pb-2 space-y-0" data-testid="chat-list">
            {archiveOpen ? (
              /* Workstream B.5 — archive view. Replaces the active list. */
              <div data-testid="chat-archive-view">
                <button
                  onClick={closeArchive}
                  className="w-full flex items-center gap-1.5 px-2 py-1.5 mb-2 text-[11.5px] uppercase tracking-wider text-[var(--muted)] hover:text-[var(--ink)] rounded-sm"
                  data-testid="chat-archive-back-btn"
                >
                  <ArrowLeft className="w-3 h-3" /> Back to active chats
                </button>
                {archiveLoading ? (
                  <p className="p-4 text-[11px] text-[var(--muted)] text-center">Loading…</p>
                ) : archivedChats.length === 0 ? (
                  <p className="p-4 text-[11px] text-[var(--muted)] text-center italic" data-testid="chat-archive-empty">
                    No archived conversations.
                  </p>
                ) : (
                  archivedChats.map((c) => (
                    <div
                      key={c.id}
                      className="px-3 py-2 hover:bg-[var(--cream-deep)]/30 rounded-sm group"
                      data-testid={`chat-archive-item-${c.id}`}
                    >
                      <p className="font-sans text-[13.5px] font-medium leading-[1.35] truncate text-[var(--ink)]">
                        {c.title}
                      </p>
                      <div className="flex items-center gap-1 mt-1.5 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button
                          onClick={() => onRestoreChat(c.id)}
                          className="text-[10.5px] uppercase tracking-wider text-[var(--accent)] hover:text-[var(--ink)] inline-flex items-center gap-1 px-1.5 py-0.5 rounded-sm hover:bg-[var(--cream-deep)]/40"
                          data-testid={`chat-archive-restore-${c.id}`}
                          title="Restore to active conversations"
                        >
                          <ArchiveRestore className="w-3 h-3" /> Restore
                        </button>
                        <button
                          onClick={() => onHardDeleteChat(c.id)}
                          className="text-[10.5px] uppercase tracking-wider text-[var(--muted)] hover:text-red-600 inline-flex items-center gap-1 px-1.5 py-0.5 rounded-sm hover:bg-red-50"
                          data-testid={`chat-archive-purge-${c.id}`}
                          title="Permanently delete (audit chain preserved)"
                        >
                          <Trash className="w-3 h-3" /> Delete
                        </button>
                      </div>
                    </div>
                  ))
                )}
              </div>
            ) : loading ? (
              <p className="p-4 text-[11px] text-[var(--muted)] text-center">Loading…</p>
            ) : searching ? (
              <p className="p-4 text-[11px] text-[var(--muted)] text-center">Searching…</p>
            ) : searchHits !== null ? (
              searchHits.length === 0 ? (
                <p className="p-4 text-[11px] text-[var(--muted)] text-center italic" data-testid="chat-search-empty">
                  No matches in this context.
                </p>
              ) : (
                searchHits.map((hit) => {
                  const c = hit.chat;
                  const active = c.id === activeId;
                  return (
                    <button
                      key={`hit-${c.id}-${hit.matched_message_id || "title"}`}
                      onClick={() => { setActiveId(c.id); setSearchQ(""); setSearchHits(null); }}
                      className={`w-full text-left px-3 py-2 transition-colors rounded-sm ${
                        active
                          ? "bg-[var(--cream)] border-l-2 border-l-[var(--accent)] pl-2.5"
                          : "hover:bg-[var(--cream-deep)]/30"
                      }`}
                      data-testid={`chat-search-hit-${c.id}`}
                    >
                      <p className="font-sans text-[13.5px] font-medium leading-[1.35] truncate text-[var(--ink)]">
                        {c.title}
                      </p>
                      {/* Search-hit only — snippet retained because it's
                          the WHY of the match; non-search default rows
                          dropped this per the tightening spec. */}
                      <p className="text-[11px] text-[var(--muted)] mt-0.5">
                        {hit.match_in === "title" ? "Title match" : "Turn match"} · {hit.snippet || "(no snippet)"}
                      </p>
                    </button>
                  );
                })
              )
            ) : chats.length === 0 ? (
              <div className="p-6 text-center" data-testid="chat-empty">
                <p className="text-[12px] text-[var(--muted)] italic mb-3">
                  No conversations yet.
                </p>
                <Button
                  onClick={onNewChat}
                  size="sm"
                  className="text-[11.5px] bg-[var(--ink)] hover:bg-[var(--ink)]/90 text-white"
                  data-testid="chat-empty-new-btn"
                >
                  Start a conversation
                </Button>
              </div>
            ) : chats.map((c) => {
              const active = c.id === activeId;
              return (
                <div
                  key={c.id}
                  role="button"
                  tabIndex={0}
                  onClick={() => setActiveId(c.id)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      setActiveId(c.id);
                    }
                  }}
                  /* H.3 side-fix (2026-05-26) — Claude-style tightening:
                     single-line title (subtitle dropped), sans 13.5px /
                     weight 500, 8px vertical padding, no inter-row
                     margin, subtle hover bg, active state keeps the
                     2px oxblood accent bar. */
                  className={`group w-full text-left px-3 py-2 cursor-pointer transition-colors flex items-center gap-2 rounded-sm ${
                    active
                      ? "bg-[var(--cream)] border-l-2 border-l-[var(--accent)] pl-2.5"
                      : "hover:bg-[var(--cream-deep)]/30"
                  }`}
                  data-testid={`chat-item-${c.id}`}
                >
                  <div className="flex-1 min-w-0">
                    <p
                      className="font-sans text-[13.5px] font-medium leading-[1.35] truncate text-[var(--ink)]"
                      data-testid={`chat-item-title-${c.id}`}
                    >
                      {c.title}
                    </p>
                  </div>
                  {/* Phase C Chat cleanup (2026-05-26): three-dot
                      per-thread menu (Claude pattern). Visible on
                      hover on desktop; always-visible on touch
                      via the `group-hover:opacity-100` + base
                      `opacity-100 sm:opacity-0` toggle.
                      Initial menu ships with Delete only — soft-
                      archive (`onArchive`) is the existing
                      destructive op; the top-bar trash icon stays. */}
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <button
                        type="button"
                        onClick={(e) => e.stopPropagation()}
                        onKeyDown={(e) => e.stopPropagation()}
                        className="shrink-0 p-1 rounded-sm text-[var(--muted)] hover:text-[var(--ink)] hover:bg-[var(--cream-deep)]/40 opacity-100 sm:opacity-0 sm:group-hover:opacity-100 sm:focus-visible:opacity-100 sm:focus-within:opacity-100 transition-opacity"
                        aria-label="Thread options"
                        data-testid={`chat-thread-row-menu-${c.id}`}
                      >
                        <MoreVertical className="w-4 h-4" strokeWidth={1.8} />
                      </button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent
                      align="end"
                      onCloseAutoFocus={(e) => e.preventDefault()}
                      data-testid={`chat-thread-row-menu-content-${c.id}`}
                    >
                      <DropdownMenuItem
                        onClick={(e) => {
                          e.stopPropagation();
                          onArchive(c.id);
                        }}
                        className="text-[var(--ink)] focus:text-red-600"
                        data-testid={`chat-thread-row-delete-${c.id}`}
                      >
                        <Trash2 className="w-3.5 h-3.5 mr-2" />
                        Delete
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              );
            })}
          </div>
          {/* QA-2026-05-16-012 (2026-05-18) — Archive button now
              navigates to the dedicated `/app/chats/archived` page
              (Restore + Permanently Delete + confirmation prompt).
              Previously this opened an in-sidebar variant that on
              some viewport widths rendered as a blank panel; the
              dedicated page is the canonical destination per the
              QA spec. */}
          {!archiveOpen && (
            <div className="p-3">
              <button
                onClick={() => navigate("/app/chats/archived")}
                className="w-full flex items-center justify-center gap-1.5 px-2 py-1.5 text-[11px] uppercase tracking-wider text-[var(--muted)] hover:text-[var(--ink)] hover:bg-[var(--cream)]/60 rounded-sm"
                data-testid="chat-open-archive-btn"
              >
                <Trash2 className="w-3 h-3" /> Archive
              </button>
            </div>
          )}
        </aside>

        {/* Main */}
        <main className="flex flex-col min-h-0 min-w-0 bg-white" data-testid="chat-main">
          {!activeChat ? (
            <div className="flex-1 flex items-center justify-center text-center p-12">
              <div className="max-w-md">
                <Shield className="w-10 h-10 text-[var(--muted)]/40 mx-auto mb-5" strokeWidth={1.2} />
                <h2 className="akki-serif text-[22px] font-normal text-[var(--ink)] mb-2">
                  Your private AI workspace.
                </h2>
                <p className="text-[14px] text-[var(--muted)] leading-relaxed mb-6">
                  Ask anything you'd ask ChatGPT, Claude, or Gemini — without exposing
                  your company's internals to any of them. Synisense automatically
                  shields identifiers when it detects them, and every decision is
                  logged with bank-grade audit evidence.
                </p>
                <Button
                  onClick={onNewChat}
                  className="bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white"
                  data-testid="chat-splash-new-btn"
                >
                  <Plus className="w-3.5 h-3.5 mr-1.5" /> Start a conversation
                </Button>
              </div>
            </div>
          ) : (
            <>
              <ChatHeader
                chat={activeChat}
                models={models}
                activeModel={activeModel}
                activeContext={activeContext}
                onPatch={onPatch}
                onArchive={() => onArchive(activeChat.id)}
                onAudit={() => setAuditOpen(true)}
              />

              <div
                ref={scrollContainerRef}
                onScroll={onMessagesScroll}
                className="flex-1 overflow-y-auto overflow-x-hidden px-3 py-4 sm:px-6 sm:py-5 md:px-8 md:py-6 relative"
                data-testid="chat-messages"
              >
                {/* Patch 4A — chat horizontal-clipping fix: centred
                    max-width gutter so message bubbles, code blocks, and
                    tables stay inside ~1040px regardless of viewport. */}
                <div className="max-w-[1040px] mx-auto" data-testid="chat-messages-gutter">
                {/* Phase A (2026-05-10) — inner wrapper exists so a
                    ResizeObserver can fire when content grows
                    (token arrives, code block highlights, image
                    loads). The outer scroll container's size doesn't
                    change; only the inner does. */}
                <div ref={messagesInnerRef} className="space-y-5">
                {/* Phase C (2026-05-13) — per-conversation Synisense
                    aggregate KPI strip. Re-fetches after every assistant
                    turn (refresh nonce keyed on message count). */}
                {activeChat?.id && (
                  <AggregateStrip
                    chatId={activeChat.id}
                    refreshNonce={(activeChat.messages || []).length}
                  />
                )}
                {(activeChat.messages || []).length === 0 ? (
                  <p className="text-center text-[13px] text-[var(--muted)] italic mt-10">
                    Type your first message below.
                  </p>
                ) : (activeChat.messages || []).map((m) => (
                  <Message key={m.id} m={m} activeModel={activeModel} models={models}
                    synisense={messageSynisense.get(m.id)} chatId={activeChat?.id} />
                ))}
                {sending && (
                  <div className="flex items-center gap-2 text-[12.5px] text-[var(--muted)] italic">
                    <Loader2 className="w-3 h-3 animate-spin" /> {activeModel?.label || "AKKI"} is thinking…
                  </div>
                )}
                <div ref={messagesEndRef} />
                </div>
                </div>
                {/* Phase A (2026-05-10) — floating "↓ Jump to latest"
                    pill. Visible only when pinnedRef has gone false
                    (user scrolled up >64 px). Click re-pins. */}
                {userScrolledUp && (
                  <button
                    type="button"
                    onClick={scrollToLatest}
                    className="akki-chat-scroll-to-latest"
                    data-testid="chat-scroll-to-latest"
                  >
                    <ChevronDown className="w-3 h-3" /> Jump to latest
                  </button>
                )}
              </div>

              <Composer
                value={input}
                onChange={setInput}
                onSubmit={onSubmit}
                onCancel={onCancel}
                sending={sending}
                policy={activeChat.shielding_policy}
                attachments={attachments}
                onAttachFile={onAttachFile}
                onRemoveAttachment={onRemoveAttachment}
                thinkHarder={thinkHarder}
                onToggleThinkHarder={() => setThinkHarder((v) => !v)}
                linkedContext={activeChat.linked_context || null}
                onRemoveLinkedContext={onRemoveLinkedContext}
              />
            </>
          )}
        </main>
      </div>

      <BypassDialog
        info={bypassDlg}
        onClose={() => setBypassDlg(null)}
        onConfirm={(text) => {
          setBypassDlg(null);
          sendMessage(text, true);
        }}
      />
      <AuditDialog
        open={auditOpen}
        onClose={() => setAuditOpen(false)}
        chatId={activeChat?.id}
      />
      </WorkspaceEntryGate>
    </AppShell>
  );
}

function ChatHeader({ chat, models, activeModel, activeContext, onPatch, onArchive, onAudit }) {
  const [titleEdit, setTitleEdit] = useState(false);
  const [title, setTitle] = useState(chat.title);
  useEffect(() => { setTitle(chat.title); }, [chat.id, chat.title]);

  return (
    <div className="px-3 sm:px-6 py-4 flex flex-wrap items-center gap-6" data-testid="chat-header">
      <div className="flex-1 min-w-0">
        {titleEdit ? (
          <input
            value={title}
            autoFocus
            onChange={(e) => setTitle(e.target.value)}
            onBlur={() => { setTitleEdit(false); if (title !== chat.title) onPatch({ title }); }}
            onKeyDown={(e) => { if (e.key === "Enter") e.target.blur(); if (e.key === "Escape") { setTitle(chat.title); setTitleEdit(false); } }}
            className="akki-serif text-[22px] text-[var(--ink)] bg-transparent border-b border-[var(--accent)] focus:outline-none w-full"
            data-testid="chat-title-input"
          />
        ) : (
          <button
            onClick={() => setTitleEdit(true)}
            className="akki-serif text-[22px] text-[var(--ink)] hover:text-[var(--accent)] truncate text-left block w-full"
            data-testid="chat-title"
            title={chat.title /* full title in tooltip per Patch 26B */}
          >
            {/* Patch 26B — cap at 7 word-tokens. Full title is in the
                conversation list + tooltip. */}
            {truncateTitleWords(chat.title, 7)}
          </button>
        )}
        <p className="text-[14px] text-[var(--muted)] mt-1 truncate">
          {chat.message_count || 0} messages
          {/* Patch 26C — workspace name moves from the title row into
              the meta line so the title row stays clean. */}
          {activeContext?.name && (
            <>
              {" · "}
              <span data-testid="chat-header-active-context">
                in <span className="text-[var(--ink)]">{activeContext.name}</span>
              </span>
            </>
          )}
          {" · "}{POLICY_LABEL[chat.shielding_policy]}
          <SynisenseInlineBadge chatId={chat.id} />
        </p>
      </div>
      <ModelPicker
        models={models}
        value={chat.model_id}
        onChange={(model_id) => onPatch({ model_id })}
      />
      <PolicyPicker
        value={chat.shielding_policy}
        onChange={(shielding_policy) => onPatch({ shielding_policy })}
      />
      {/* Workstream B.4 — Auto-Shield (i) tooltip. CSS-only hover, no
          Radix dependency added; matches the muted-icon styling
          elsewhere in the header bar. */}
      <span
        className="relative inline-flex group cursor-help text-[var(--muted)]"
        tabIndex={0}
        aria-label="What is Auto-Shield?"
        data-testid="auto-shield-tooltip-trigger"
      >
        <Info className="w-3.5 h-3.5" aria-hidden="true" />
        <span
          role="tooltip"
          className="pointer-events-none absolute right-0 top-full mt-1 w-72 z-50 hidden group-hover:block group-focus-within:block bg-[var(--ink)] text-[var(--cream)] text-[11px] leading-snug px-3 py-2 rounded-sm shadow-lg"
        >
          Auto-Shield redacts names and numbers before any AI sees them.
          <span className="block mt-1"><b>Auto</b> — redact when sensitivity is detected.</span>
          <span className="block"><b>Always</b> — redact every message.</span>
          <span className="block"><b>Off</b> — send raw (use sparingly).</span>
        </span>
      </span>
      <button
        onClick={onAudit}
        className="text-[var(--muted)] hover:text-[var(--ink)] text-[11.5px] uppercase tracking-wider inline-flex items-center gap-1 px-2 py-1 rounded-sm hover:bg-[var(--cream-deep)]/40"
        data-testid="chat-audit-btn"
        title="View audit log"
      >
        <Eye className="w-3 h-3" /> Audit
      </button>
      <button
        onClick={onArchive}
        className="text-[var(--muted)] hover:text-red-600 p-1.5 rounded-sm"
        data-testid="chat-archive-btn"
        title="Archive conversation"
      >
        <Trash2 className="w-3.5 h-3.5" />
      </button>
    </div>
  );
}

function ModelPicker({ models, value, onChange }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useEffect(() => {
    const onDoc = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);
  const active = models.find((m) => m.id === value);
  return (
    <div className="relative" ref={ref} data-testid="chat-model-picker">
      <button
        onClick={() => setOpen((o) => !o)}
        className={`h-8 inline-flex items-center gap-1.5 px-2 text-[12px] bg-transparent transition-colors ${
          open
            ? "border-0 border-b border-[var(--accent)] rounded-none"
            : "border-0 rounded-sm hover:bg-[var(--cream)]"
        }`}
        data-testid="chat-model-trigger"
      >
        <ModelAvatar model={active} size="xs" />
        <span className="text-[var(--ink)] truncate max-w-[140px]">{active?.label || value}</span>
        <ChevronDown className={`w-3 h-3 text-[var(--muted)] transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div className="absolute right-0 top-full mt-1 z-30 min-w-[280px] bg-white border border-[var(--rule)] rounded-sm shadow-lg py-1" data-testid="chat-model-menu">
          {models.map((m) => (
            <button
              key={m.id}
              onClick={() => { onChange(m.id); setOpen(false); }}
              className={`w-full text-left px-3 py-2 text-[13px] hover:bg-[var(--cream-deep)]/40 flex items-center gap-2.5 ${m.id === value ? "bg-[var(--cream-deep)]/30" : ""}`}
              data-testid={`chat-model-opt-${m.id}`}
            >
              <ModelAvatar model={m} size="sm" />
              <div className="flex-1 min-w-0">
                <p className="text-[var(--ink)]">{m.label}</p>
                <p className="text-[11px] text-[var(--muted)] italic">{m.tone}</p>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function PolicyPicker({ value, onChange }) {
  // Phase F (2026-05-21) — boundary-removal. Native <select> is hard
  // to style per-state for "no border at rest, hairline on focus",
  // but `appearance-none + hover bg + focus border-b` approximates
  // the contract closely. The browser-native open dropdown is
  // unavoidable; that's a visual-quality tradeoff we accept rather
  // than re-implement a custom dropdown.
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="h-8 text-[11.5px] border-0 rounded-sm bg-transparent px-2 hover:bg-[var(--cream)] focus:outline-none focus:bg-transparent focus:border-b focus:border-[var(--accent)] focus:rounded-none"
      data-testid="chat-policy-picker"
      title="Synisense shielding policy for this conversation"
    >
      <option value="auto">Auto-shield</option>
      <option value="always">Always shield</option>
      <option value="off">Off</option>
    </select>
  );
}

function Message({ m, activeModel, models, synisense, chatId }) {
  const isUser = m.role === "user";
  const shielded = m.shielded;
  const detected = (m.shielding?.identifiers_masked || 0) > 0;
  const cats = m.shielding?.by_category || {};
  const catSummary = Object.entries(cats).map(([k, n]) => `${n} ${k}${n === 1 ? "" : "s"}`).join(" · ");
  // Resolve the model that produced this assistant message — fall back to
  // activeModel for messages persisted before model_id was tracked.
  const msgModel = !isUser
    ? (models?.find?.((x) => x.id === m.model_id) || activeModel)
    : null;

  return (
    <div className={`flex gap-3 ${isUser ? "flex-row-reverse" : ""}`} data-testid={`chat-msg-${m.role}`}>
      {isUser ? (
        <div className="w-7 h-7 rounded-full shrink-0 flex items-center justify-center text-[10px] font-mono bg-[var(--ink)] text-white">
          YOU
        </div>
      ) : (
        <ModelAvatar model={msgModel} size="md" className="rounded-full" />
      )}
      <div className={`flex-1 min-w-0 ${isUser ? "text-right" : ""}`}>
        {isUser && detected && (
          <div className={`inline-flex items-center gap-1 text-[10px] uppercase tracking-wider mb-1 px-1.5 py-0.5 rounded-sm ${
            shielded
              ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
              : "bg-amber-50 text-amber-800 border border-amber-200"
          }`} title={catSummary}>
            {shielded ? <FileLock2 className="w-2.5 h-2.5" /> : <ShieldOff className="w-2.5 h-2.5" />}
            {shielded ? `Shielded · ${catSummary}` : `Sent unshielded · ${catSummary} · acknowledged`}
          </div>
        )}
        {!isUser && (m.model_label || msgModel?.label) && (
          <div className="mb-1 flex flex-wrap items-center gap-x-3 gap-y-1" data-testid={`chat-msg-meta-${m.id}`}>
            <p className="text-[10px] uppercase tracking-wider text-[var(--graphite)] m-0">
              {m.model_label || msgModel?.label}
              {m.latency_ms ? ` · ${(m.latency_ms / 1000).toFixed(1)}s` : ""}
            </p>
            {/* CHAT sprint (2026-05-12) — per-message Synisense badge.
                Always renders; "—" when count is zero. Hover tooltip
                shows the three-layer breakdown. */}
            <PerMessageSynisenseBadge runs={synisense} testId={`chat-msg-synisense-${m.id}`} />
            {/* CHAT sprint — provider transparency line. Italic when
                fallback_triggered=true. Tooltip resolves the chain. */}
            <ProviderLine
              providerUsed={m.provider_used}
              fallbackTriggered={m.fallback_triggered}
              testId={`chat-msg-provider-${m.id}`}
            />
          </div>
        )}
        {/* Phase B.2 — collapsible Pass 1 reasoning panel. Renders only
            when the backend included a `pass_1` AND the visibility flag
            (set either by the "Think harder" toggle or by an explicit
            cue in the user's text) is true. Default collapsed. */}
        {!isUser && m.show_pass_1 && m.pass_1 && (
          <Pass1Panel pass1={m.pass_1} />
        )}
        {/* Phase B.2 — small four-check label badge. Surfaces ONLY when
            the model emitted a labelled finding at the top of the
            reply (TENSION / CONTRADICTION / ASSUMPTION / FRAMING
            LIMITATION). Otherwise nothing — the silent four-check
            stays silent (memo Item 8 §"never as a performance of
            process"). */}
        {!isUser && m.four_check_label && (
          <div
            className="inline-flex items-center gap-1 text-[10px] uppercase tracking-wider mb-1 px-1.5 py-0.5 rounded-sm bg-amber-50 text-amber-800 border border-amber-200"
            data-testid="chat-four-check-label"
            title="Material finding from the silent four-check (tension / contradiction / load-bearing assumption / framing limitation)."
          >
            {m.four_check_label}
          </div>
        )}
        <div className={`inline-block max-w-full akki-serif text-[14.5px] leading-[1.65] break-words ${
          isUser
            ? "bg-[var(--cream-deep)]/50 border border-[var(--rule)] rounded-sm px-3 py-2 text-[var(--ink)] whitespace-pre-wrap break-words"
            : "text-[var(--ink)]"
        }`}>
          {/* Phase B.1 / Workstream B.1 — markdown rendering for
              assistant bubbles that have no citations. Citation-bearing
              replies keep the existing inline-pill renderer because
              that returns React nodes that don't mix with markdown's
              string parser. User bubbles always plain-text (memo +
              voice rule: never render user-supplied markdown as HTML).
              Workstream B.1 (2026-05-10) extracted the renderer into
              `MarkdownMessage` so the blinking-cursor and the styles
              live in one place. */}
          {isUser ? (
            m.content
          ) : Array.isArray(m.citations) && m.citations.length > 0 ? (
            <span className="whitespace-pre-wrap">
              {renderInlineCitations(m.content, m.citations)}
            </span>
          ) : (
            <>
              {/* Patch 26E — privacy-first phase caption above the
                  streaming reply. Only renders while the assistant
                  bubble is still streaming AND a phase has been
                  emitted by the backend. Falls back to silence on
                  surfaces that don't emit phase events. */}
              {m.streaming && m._phase && m._phase !== "complete" && (
                <ChatPhaseCaption phase={m._phase} />
              )}
              <MarkdownMessage content={m.content} streaming={!!m.streaming} />
              {m.cancelled && (
                <p className="mt-2 text-[11px] text-[var(--muted)] italic">
                  Cancelled. Partial reply kept.
                </p>
              )}
            </>
          )}
        </div>
        {/* Phase 11 ITEM C — citation chips travel as a structured array
            beneath the assistant reply, click-through into the Reading
            Viewer at the cited paragraph anchor. We dropped any
            hallucinated marker server-side, so every chip rendered here
            resolves to a real paragraph. */}
        {!isUser && Array.isArray(m.citations) && m.citations.length > 0 && (
          <ul
            className="mt-2 flex flex-wrap gap-1.5"
            data-testid="chat-citations"
          >
            {m.citations.map((c) => (
              <li key={c.n}>
                <a
                  href={`/app/documents/${c.doc_id}#p=${c.anchor_id}`}
                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded-sm border border-[var(--rule)] bg-[var(--cream-deep)]/50 hover:bg-[var(--accent)] hover:text-white hover:border-[var(--accent)] text-[11px] text-[var(--deep)] transition-colors"
                  title={`${c.doc_name || "Document"} · p.${c.page ?? "?"}¶${c.paragraph_number ?? "?"}\n\n${c.snippet || ""}`}
                  data-testid={`chat-citation-${c.n}`}
                >
                  <span className="font-mono tabular-nums text-[10px] text-[var(--accent)]">[{c.n}]</span>
                  <span className="truncate max-w-[280px]">
                    {c.doc_name || "Document"}
                    {c.page ? ` · p.${c.page}` : ""}
                    {c.paragraph_number ? `¶${c.paragraph_number}` : ""}
                  </span>
                </a>
              </li>
            ))}
          </ul>
        )}
        {/* Phase 12.2 ITEM A — Synisense screening icon. Renders only on
            assistant messages whose synisense_stats reports > 0
            redacted spans. Tooltip shows entity-type breakdown. NEVER
            shows original text or replacement tokens. Keyboard
            accessible: button with aria-label + title.  */}
        {!isUser && m.synisense_stats?.spans_redacted > 0 && (
          <div
            className="mt-2 inline-flex items-center gap-1 text-[10.5px] text-[var(--muted)]"
            data-testid="chat-synisense-icon"
          >
            <button
              type="button"
              className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-sm border border-[var(--rule)] bg-[var(--cream-deep)]/40 hover:border-[var(--accent)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)] cursor-help"
              aria-label={`Content screened. ${m.synisense_stats.spans_redacted} ${m.synisense_stats.spans_redacted === 1 ? "span" : "spans"} redacted. ${formatSyniBreakdown(m.synisense_stats.by_type)}`}
              title={`Content screened. ${m.synisense_stats.spans_redacted} ${m.synisense_stats.spans_redacted === 1 ? "span" : "spans"} redacted.\n\n${formatSyniBreakdown(m.synisense_stats.by_type)}`}
            >
              <FileLock2 className="w-3 h-3 text-[var(--accent)]" aria-hidden="true" />
              <span>Content screened · {m.synisense_stats.spans_redacted}</span>
            </button>
          </div>
        )}
        {/* Phase C (2026-05-13) — per-message Synisense audit panel.
            Collapsed by default; expanding fetches the natural-
            language audit data from /api/chats/{cid}/audit-panel
            and renders the executive-readable sections. */}
        {!isUser && m.id && !m.streaming && (
          <AuditPanel chatId={chatId} messageId={m.id} />
        )}
        {/* Phase C — protective layer intervention card (Mode A
            hypothesis-test framing or Mode C Solva handoff offer).
            Mode B annotations are inline footnotes; rendered above
            when `m.protective_event.intervention_type === "annotation"`. */}
        {!isUser && m.protective_event && (
          <ProtectiveInterventionCard
            event={m.protective_event}
            onSolvaContinue={() => {
              window.location.href = "/app/solva";
            }}
          />
        )}
      </div>
    </div>
  );
}

/**
 * Render the Synisense entity-type breakdown for a tooltip. Counts only —
 * the original text and replacement tokens never reach the client.
 */
function formatSyniBreakdown(byType) {
  if (!byType || typeof byType !== "object") return "";
  const parts = Object.entries(byType)
    .filter(([, n]) => n > 0)
    .sort((a, b) => b[1] - a[1])
    .map(([t, n]) => `${t} ×${n}`);
  return parts.join(", ");
}

/**
 * Render an assistant message's text with inline `[n]` markers replaced
 * by superscript pills that link to the nth citation. Server-side has
 * already validated and dropped hallucinated markers, so we trust the
 * `[n]` numbering matches `citations[n-1]`.
 */
function renderInlineCitations(text, citations) {
  if (!text) return text;
  const byN = new Map(citations.map((c) => [c.n, c]));
  // Match `[1]`, `[12]` etc — non-greedy 1-2 digit, surrounded by brackets.
  const parts = text.split(/(\[\d{1,2}\])/g);
  return parts.map((seg, idx) => {
    const m = seg.match(/^\[(\d{1,2})\]$/);
    if (!m) return <React.Fragment key={idx}>{seg}</React.Fragment>;
    const n = Number(m[1]);
    const c = byN.get(n);
    if (!c) return <React.Fragment key={idx}>{seg}</React.Fragment>;
    return (
      <a
        key={idx}
        href={`/app/documents/${c.doc_id}#p=${c.anchor_id}`}
        className="align-super text-[10px] font-mono text-[var(--accent)] hover:underline mx-0.5"
        title={`${c.doc_name || "Document"} · p.${c.page ?? "?"}¶${c.paragraph_number ?? "?"}`}
        data-testid={`chat-citation-inline-${n}`}
      >
        [{n}]
      </a>
    );
  });
}

function Composer({ value, onChange, onSubmit, sending, policy, onCancel, attachments, onAttachFile, onRemoveAttachment, thinkHarder, onToggleThinkHarder, linkedContext, onRemoveLinkedContext }) {
  const ta = useRef(null);
  const fileInputRef = useRef(null);
  return (
    /* T1.1 (2026-05-24) — sticky bottom-0 + z-10 anchors the composer
       to the bottom of the chat pane regardless of message length or
       viewport size. The parent `<main>` is `flex flex-col min-h-0`
       so the scroll container above takes `flex-1` and the composer
       sits below it. `sticky bottom-0` is the belt-and-braces guard
       in case a deeper flex child breaks the layout contract on
       narrow viewports. */
    <div className="sticky bottom-0 z-10 border-t border-[var(--rule)] p-3 bg-white" data-testid="chat-composer">
      {/* Phase D.3 (2026-05-26) — linked-context chip. Renders above
          the composer when the active chat is tied to a source item
          (document / cycle / work_studio artefact). Click the title
          to navigate back to the source; click ✕ to remove the link
          (persists `linked_context: null` on the chat row). Excerpt
          is NOT shown in the chip — only the title + type — so the
          chip stays compact next to the composer. */}
      {linkedContext && (
        <LinkedContextChip
          linked={linkedContext}
          onRemove={onRemoveLinkedContext}
        />
      )}
      {/* Phase B.1 — attached-file chips. Each chip shows name + size +
          sensitivity band; click X to remove. The chips travel with
          the next send and are cleared on success/cancel. */}
      {attachments && attachments.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-2" data-testid="chat-attachment-chips">
          {attachments.map((a) => (
            <span
              key={a.document_id}
              className={`inline-flex items-center gap-1.5 px-2 py-1 rounded-sm border text-[11px] ${BAND_COLOR[a.sensitivity?.classification?.toLowerCase?.() || "public"] || BAND_COLOR.public}`}
              data-testid={`chat-attachment-chip-${a.document_id}`}
              title={`${a.name} · ${_humanBytes(a.size_bytes)} · ${a.char_len || 0} chars · sensitivity ${a.sensitivity?.classification || "PUBLIC"}`}
            >
              <FileText className="w-3 h-3" />
              <span className="max-w-[180px] truncate">{a.name}</span>
              <span className="text-[10px] opacity-70">· {_humanBytes(a.size_bytes)} · {a.sensitivity?.classification || "PUBLIC"}</span>
              <button
                onClick={() => onRemoveAttachment(a.document_id)}
                className="ml-1 hover:text-red-700"
                aria-label={`Remove ${a.name}`}
                data-testid={`chat-attachment-remove-${a.document_id}`}
              >
                <X className="w-2.5 h-2.5" />
              </button>
            </span>
          ))}
        </div>
      )}
      <div className="flex items-end gap-2">
        <div className="flex-1 bg-[var(--cream)] border border-[var(--rule)] rounded-md p-2 focus-within:border-[var(--accent)]">
          <textarea
            ref={ta}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) { e.preventDefault(); onSubmit(); }
            }}
            placeholder="Type a question, attach a document, or paste text. ⌘/Ctrl+Enter to send."
            disabled={sending}
            rows={2}
            className="w-full bg-transparent text-[14px] resize-none focus:outline-none akki-serif leading-relaxed"
            data-testid="chat-input"
          />
          <div className="flex items-center justify-between pt-1.5 border-t border-[var(--rule)]/60 mt-1">
            <div className="flex items-center gap-2.5">
              <div className="flex items-center gap-1 text-[10px] text-[var(--muted)]">
                <Shield className="w-2.5 h-2.5 text-[var(--accent)]" />
                <span className="uppercase tracking-wider">{POLICY_LABEL[policy]}</span>
              </div>
              {/* Phase B.1 — file attach button */}
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={sending}
                className="inline-flex items-center gap-1 text-[10.5px] text-[var(--muted)] hover:text-[var(--accent)] disabled:opacity-50"
                data-testid="chat-attach-btn"
                title="Attach a document (PDF, DOCX, TXT, or image)"
              >
                <Paperclip className="w-3 h-3" /> Attach
              </button>
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.docx,.doc,.txt,.md,.png,.jpg,.jpeg,.webp"
                className="hidden"
                onChange={async (e) => {
                  const f = e.target.files?.[0];
                  if (f) await onAttachFile(f);
                  e.target.value = "";
                }}
                data-testid="chat-attach-input"
              />
              {/* Phase B.2 — Think harder toggle. Per-turn opt-in to
                  the canonical two-pass method with visible Pass 1.
                  Resets after every send. */}
              <button
                type="button"
                onClick={onToggleThinkHarder}
                disabled={sending}
                aria-pressed={thinkHarder ? "true" : "false"}
                className={`inline-flex items-center gap-1 text-[10.5px] disabled:opacity-50 px-1.5 py-0.5 rounded-sm border transition-colors ${
                  thinkHarder
                    ? "bg-[var(--accent)] text-white border-[var(--accent)]"
                    : "text-[var(--muted)] hover:text-[var(--accent)] border-transparent hover:border-[var(--rule)]"
                }`}
                data-testid="chat-think-harder-btn"
                title={
                  thinkHarder
                    ? "Think harder is ON — the next reply will show Pass 1 reasoning above the deliverable."
                    : "Think harder — surface Pass 1 reasoning before the deliverable for this turn."
                }
              >
                <Brain className="w-3 h-3" />
                <span>Think harder{thinkHarder ? " · ON" : ""}</span>
              </button>
            </div>
            <span className="text-[10px] text-[var(--muted)]">
              {value.length} / 20,000
            </span>
          </div>
        </div>
        {sending ? (
          <Button
            onClick={onCancel}
            className="bg-[var(--ink)]/80 hover:bg-[var(--ink)] text-white h-10 w-12 p-0"
            data-testid="chat-cancel-btn"
            aria-label="Cancel"
            title="Cancel this turn"
          >
            <StopCircle className="w-4 h-4" />
          </Button>
        ) : (
          <Button
            onClick={onSubmit}
            disabled={!value.trim()}
            className="bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white h-10 w-12 p-0"
            data-testid="chat-send-btn"
            aria-label="Send"
          >
            <Send className="w-4 h-4" />
          </Button>
        )}
      </div>
    </div>
  );
}
function Pass1Panel({ pass1 }) {
  // Phase B.2 — Collapsible "Pass 1 — reasoning" block. Default
  // collapsed. Click the header to toggle. Pass 1 is the canonical
  // four-layer reasoning trail (candidate generation, triangulation,
  // probability weighting, reflection); we render it as plain
  // markdown so tables and code blocks land correctly.
  const [open, setOpen] = useState(false);
  return (
    <div
      className="mb-2 border border-[var(--rule)] bg-[var(--cream-deep)]/30 rounded-sm"
      data-testid="chat-pass-1-panel"
    >
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open ? "true" : "false"}
        className="w-full flex items-center gap-1.5 px-2.5 py-1.5 text-[11px] uppercase tracking-wider text-[var(--muted)] hover:bg-[var(--cream-deep)]/60"
        data-testid="chat-pass-1-toggle"
      >
        <ChevronRight
          className={`w-3 h-3 transition-transform ${open ? "rotate-90" : ""}`}
          aria-hidden="true"
        />
        <span>Pass 1 — reasoning</span>
      </button>
      {open && (
        <div
          className="px-3 py-2 border-t border-[var(--rule)] akki-serif text-[13px] leading-[1.6] text-[var(--deep)]"
          data-testid="chat-pass-1-body"
        >
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            disallowedElements={["script", "iframe", "style", "form"]}
            unwrapDisallowed
          >
            {pass1}
          </ReactMarkdown>
        </div>
      )}
    </div>
  );
}


// ─────────────────────────────────────────────────────────────────────
// Phase D.3 (2026-05-26) — Linked context chip
//
// Renders above the composer when the active chat carries a
// `linked_context: { ctx_type, ctx_id, title, href, excerpt, attached_at }`.
// The chip is intentionally compact (one line) and matches the existing
// attachment-chip aesthetic — so users perceive the linked item as the
// "topic" of the conversation, not a heavy interactive surface.
//
// Behaviour:
//   • Title links to `linked.href` (source surface deep-link).
//   • "✕ Remove" button calls onRemove, which PATCHes
//     `clear_linked_context: true` on the chat row.
//   • When excerpt is empty (item deleted server-side OR access lost),
//     the chip renders in a muted state with "Item no longer
//     available". The backend already drops the prompt injection in
//     that case — the chip is purely display.
// ─────────────────────────────────────────────────────────────────────
function LinkedContextChip({ linked, onRemove }) {
  const title = linked?.title || linked?.ctx_id || "Linked item";
  const href  = linked?.href || "#";
  const kind  = (linked?.ctx_type || "").replace(/_/g, " ");
  const gone  = !linked?.excerpt;
  return (
    <div
      className={`mb-2 flex items-center gap-2 text-[12px] rounded-sm border px-2.5 py-1.5 ${
        gone
          ? "border-[var(--rule)] bg-[var(--cream-deep)]/30 text-[var(--muted)]"
          : "border-[var(--accent)]/30 bg-[var(--cream-deep)]/50 text-[var(--ink)]"
      }`}
      data-testid="chat-linked-context-chip"
      data-ctx-type={linked?.ctx_type || ""}
      data-ctx-id={linked?.ctx_id || ""}
    >
      <FileText className={`w-3.5 h-3.5 ${gone ? "text-[var(--muted)]" : "text-[var(--accent)]"}`} />
      <span className="text-[10px] uppercase tracking-wider text-[var(--muted)] font-mono">
        Reading
      </span>
      {gone ? (
        <span
          className="truncate max-w-[420px] italic"
          data-testid="chat-linked-context-title-unavailable"
          title="Item no longer available"
        >
          {title} · item no longer available
        </span>
      ) : (
        <a
          href={href}
          className="truncate max-w-[420px] underline-offset-2 hover:underline hover:text-[var(--accent)]"
          data-testid="chat-linked-context-title"
          title={title}
        >
          {title}
        </a>
      )}
      <span className="text-[10px] text-[var(--muted)] uppercase tracking-wider">
        · {kind}
      </span>
      <button
        type="button"
        onClick={onRemove}
        className="ml-auto inline-flex items-center text-[var(--muted)] hover:text-[var(--accent)]"
        aria-label="Remove linked item"
        data-testid="chat-linked-context-remove"
      >
        <X className="w-3 h-3" />
      </button>
    </div>
  );
}


function BypassDialog({ info, onClose, onConfirm }) {
  if (!info) return null;
  const cats = info.detected?.by_category || {};
  const summary = Object.entries(cats).map(([k, n]) => `${n} ${k}${n === 1 ? "" : "s"}`).join(", ") || "identifiers";
  return (
    <Dialog open={!!info} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="bg-[var(--cream)] border-[var(--rule)] max-w-md" data-testid="chat-bypass-dialog">
        <DialogHeader>
          <DialogTitle className="akki-serif font-normal flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-600" /> Sensitive content detected
          </DialogTitle>
          <DialogDescription className="text-[13px] text-[var(--deep)] leading-relaxed pt-2">
            AKKI noticed <strong>{summary}</strong> in your message. Shielding is set
            to <strong>Off</strong> for this chat, so the message would be sent
            to the model in the clear. Confirm and we'll log the bypass with full
            audit provenance — or cancel and turn shielding back on.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter className="gap-2">
          <Button variant="outline" onClick={onClose} className="rounded-sm" data-testid="chat-bypass-cancel">
            Cancel
          </Button>
          <Button
            onClick={() => onConfirm(info.text)}
            className="bg-amber-700 hover:bg-amber-800 text-white rounded-sm"
            data-testid="chat-bypass-confirm"
          >
            Send unshielded · log it
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function AuditDialog({ open, onClose, chatId }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  // Phase J — Synisense audit metrics strip + storyline (everyday-people numbers).
  const [metrics, setMetrics] = useState(null);
  useEffect(() => {
    if (!open || !chatId) return;
    setLoading(true);
    api.get(`/chats/${chatId}/audit`)
      .then(({ data }) => setRows(data?.rows || []))
      .catch(() => setRows([]))
      .finally(() => setLoading(false));
    // Fetch the human-readable Synisense metrics in parallel — never blocks render.
    api.get(`/chats/${chatId}/synisense-metrics`)
      .then(({ data }) => setMetrics(data))
      .catch(() => setMetrics(null));
  }, [open, chatId]);

  const onDownload = async () => {
    if (!chatId) return;
    try {
      const res = await api.get(`/chats/${chatId}/audit/export.zip`, {
        responseType: "blob",
      });
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const a = window.document.createElement("a");
      a.href = url;
      a.download = `akki-chat-audit-${chatId.slice(0, 8)}.zip`;
      window.document.body.appendChild(a);
      a.click();
      window.document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
      toast.success("Audit pack downloaded.");
    } catch (e) { toast.error(apiErrorMessage(e)); }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="bg-[var(--cream)] border-[var(--rule)] max-w-3xl max-h-[80vh] overflow-y-auto" data-testid="chat-audit-dialog">
        <DialogHeader>
          <div className="flex items-center justify-between gap-3">
            <DialogTitle className="akki-serif font-normal">Audit trail</DialogTitle>
            <Button
              size="sm"
              onClick={onDownload}
              disabled={loading || rows.length === 0}
              className="bg-[var(--ink)] hover:bg-[var(--ink)]/90 text-white text-[11.5px] h-8"
              data-testid="chat-audit-export-btn"
            >
              <Download className="w-3 h-3 mr-1.5" /> Export audit pack
            </Button>
          </div>
          <DialogDescription className="text-[12.5px] text-[var(--muted)]">
            Append-only, hash-chained. Auditors can verify the chain by recomputing each
            row's SHA256 against the canonical JSON of (prev_hash, id, at, account_id,
            chat_id, action, payload, ip, ua_sha). The export bundles a stdlib-only
            <code className="font-mono text-[11px] px-1">verify.py</code> for one-shot validation.
          </DialogDescription>
        </DialogHeader>
        {/* Phase J — Synisense audit metrics strip + editorial storyline. */}
        {metrics && (
          <div className="border border-[var(--rule)] bg-[var(--cream)]/40 rounded-sm p-3 mb-3" data-testid="chat-audit-synisense-metrics">
            <div className="flex flex-wrap gap-x-6 gap-y-2 items-baseline">
              <div>
                <span className="block text-[10px] uppercase tracking-[0.18em] text-[var(--muted)]">Identifiers redacted</span>
                <span className="akki-serif text-[24px] text-[var(--accent)]" data-testid="metric-identifiers">{metrics.identifiers_redacted}</span>
                <span className="text-[11px] text-[var(--muted)] ml-1">in this conversation</span>
              </div>
              <div>
                <span className="block text-[10px] uppercase tracking-[0.18em] text-[var(--muted)]">Model calls</span>
                <span className="akki-serif text-[24px] text-[var(--accent)]" data-testid="metric-modelcalls">{metrics.model_calls}</span>
                <span className="text-[11px] text-[var(--muted)] ml-1">through Synisense Shield</span>
              </div>
              {/* Phase C Chat cleanup (2026-05-26): removed the
                  "Layers won" column entirely per brief item #4. The
                  metrics.layer_breakdown payload is still emitted by
                  the backend (no schema change) — it's just not
                  surfaced in this modal. Identifiers Redacted +
                  Model Calls re-flow side-by-side naturally via
                  the existing flex-wrap parent. */}
            </div>
            <p className="akki-serif text-[14px] text-[var(--ink)] italic mt-3 leading-relaxed" data-testid="metric-storyline">
              {metrics.storyline}
            </p>
            {/* CHAT sprint (2026-05-12) — Trust Panel cross-link.
                Tertiary v7 button: no border, graphite text, oxblood
                arrow on hover. Right-aligned. Opens the global Trust
                Panel mounted in AppShell via the
                `akki:open-trust-panel` event bus. */}
            <div className="flex justify-end mt-3">
              <button
                type="button"
                onClick={() => {
                  onClose();
                  window.dispatchEvent(new Event("akki:open-trust-panel"));
                }}
                className="group inline-flex items-center gap-2 text-[13px] font-medium text-[var(--graphite)] hover:text-[var(--ink)] transition-colors"
                data-testid="chat-audit-trust-panel-link"
              >
                View full Trust Panel
                <span className="inline-flex items-center transition-all text-[var(--graphite)] group-hover:text-[var(--oxblood)] group-hover:ml-1">→</span>
              </button>
            </div>
          </div>
        )}
        {loading ? (
          <p className="text-[12px] text-[var(--muted)] italic text-center py-8">Loading…</p>
        ) : rows.length === 0 ? (
          <p className="text-[12px] text-[var(--muted)] italic text-center py-8">No audit rows yet.</p>
        ) : (
          <div className="font-mono text-[11px] space-y-2" data-testid="chat-audit-rows">
            {rows.map((r) => (
              <div key={r.id} className="bg-white border border-[var(--rule)] rounded-sm p-2.5">
                <div className="flex items-center justify-between gap-2 flex-wrap">
                  <span className="text-[var(--accent)] uppercase">{r.action}</span>
                  <span className="text-[var(--muted)] text-[10px]">{r.at}</span>
                </div>
                <p className="text-[10px] text-[var(--muted)] mt-1 break-all">
                  hash <span className="text-[var(--ink)]">{r.row_hash.slice(0, 16)}…</span>{" "}
                  · prev <span className="text-[var(--muted)]">{r.prev_hash.slice(0, 16)}…</span>{" "}
                  · ip {r.ip || "—"}
                </p>
                {Object.keys(r.payload || {}).length > 0 && (
                  <pre className="text-[10.5px] text-[var(--deep)] bg-[var(--cream)]/60 p-2 mt-1.5 rounded-sm whitespace-pre-wrap break-all">
                    {JSON.stringify(r.payload, null, 2)}
                  </pre>
                )}
              </div>
            ))}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

function SynisenseInlineBadge({ chatId }) {
  // Phase J — lightweight live counter shown beside the chat title.
  // Polls every 30s so the number ticks up as redactions accumulate.
  // Tooltip surfaces the per-layer breakdown.
  const [m, setM] = useState(null);
  useEffect(() => {
    if (!chatId) return;
    let alive = true;
    const fetchOnce = () => {
      api.get(`/chats/${chatId}/synisense-metrics`)
        .then(({ data }) => { if (alive) setM(data); })
        .catch(() => {});
    };
    fetchOnce();
    const id = setInterval(fetchOnce, 30000);
    return () => { alive = false; clearInterval(id); };
  }, [chatId]);
  if (!m || (m.identifiers_redacted || 0) === 0) return null;
  const lb = m.layer_breakdown || {};
  const layersUsed = ["regex", "presidio", "llm"].filter((k) => (lb[k] || 0) > 0).length;
  return (
    <span
      className="ml-2 inline-block px-1.5 py-[1px] border border-[var(--rule)] rounded-sm text-[10px] text-[var(--accent)] align-baseline"
      title={`Layer breakdown — regex: ${lb.regex || 0} · Presidio: ${lb.presidio || 0} · LLM-fallback: ${lb.llm || 0}`}
      data-testid="chat-synisense-inline-badge"
    >
      {m.identifiers_redacted} redacted · {layersUsed}-layer Shield
    </span>
  );
}
