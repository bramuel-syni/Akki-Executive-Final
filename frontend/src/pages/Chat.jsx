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
import { useSearchParams } from "react-router-dom";
import AppShell from "@/components/layout/AppShell";
import { api, apiErrorMessage } from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Plus, Send, Loader2, Shield, ShieldOff, Trash2, MessageCircle,
  ChevronDown, FileLock2, Eye, AlertTriangle, Download,
} from "lucide-react";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";

const POLICY_LABEL = {
  auto: "Auto-shield",
  always: "Always shield",
  off: "Off (acknowledge per send)",
};

export default function Chat() {
  const [searchParams, setSearchParams] = useSearchParams();
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

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [activeChat?.messages?.length, sending]);

  // Pre-fill the composer when arriving with ?prompt=… (e.g. from the
  // sandbox tutorial card). One-shot: we strip the param after consuming it.
  useEffect(() => {
    const p = searchParams.get("prompt");
    if (p) {
      setInput(p);
      const next = new URLSearchParams(searchParams);
      next.delete("prompt");
      setSearchParams(next, { replace: true });
    }
  }, [searchParams, setSearchParams]);

  const onNewChat = async () => {
    try {
      const { data } = await api.post("/chats", {
        title: "New conversation",
        model_id: defaultModel,
        shielding_policy: "auto",
      });
      setChats((prev) => [data, ...prev]);
      setActiveId(data.id);
    } catch (e) { toast.error(apiErrorMessage(e)); }
  };

  const onArchive = async (id) => {
    try {
      await api.delete(`/chats/${id}`);
      setChats((prev) => prev.filter((c) => c.id !== id));
      if (activeId === id) setActiveId(null);
      toast.success("Archived");
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
    // Optimistic user bubble
    const optimistic = {
      id: `tmp-${Date.now()}`, role: "user", content: text,
      created_at: new Date().toISOString(),
    };
    setActiveChat((prev) => ({
      ...(prev || {}), messages: [...((prev || {}).messages || []), optimistic],
    }));
    setInput("");
    try {
      const { data } = await api.post(
        `/chats/${activeId}/messages`,
        { content: text, acknowledge_unshielded },
        { timeout: 120000 },
      );
      setActiveChat((prev) => ({
        ...(prev || {}),
        messages: [
          ...((prev || {}).messages || []).filter((m) => m.id !== optimistic.id),
          data.user_message, data.assistant_message,
        ],
      }));
      // Refresh sidebar preview
      setChats((prev) => prev.map((c) => c.id === activeId ? {
        ...c,
        last_message_preview: data.assistant_message.content?.slice(0, 200) || "",
        last_message_at: data.assistant_message.created_at,
        message_count: (c.message_count || 0) + 2,
      } : c));
    } catch (e) {
      // 409 = sensitive content + policy=off + no acknowledgement → confirm dialog
      if (e?.response?.status === 409 && e?.response?.data?.detail?.code === "shielding_acknowledgement_required") {
        setActiveChat((prev) => ({
          ...(prev || {}),
          messages: ((prev || {}).messages || []).filter((m) => m.id !== optimistic.id),
        }));
        setBypassDlg({ text, detected: e.response.data.detail.detected });
        return;
      }
      toast.error(apiErrorMessage(e));
      setActiveChat((prev) => ({
        ...(prev || {}),
        messages: ((prev || {}).messages || []).filter((m) => m.id !== optimistic.id),
      }));
    } finally { setSending(false); }
  }, [activeId]);

  const onSubmit = () => {
    const text = input.trim();
    if (!text || sending) return;
    sendMessage(text);
  };

  const activeModel = useMemo(
    () => models.find((m) => m.id === activeChat?.model_id),
    [models, activeChat?.model_id],
  );

  return (
    <AppShell>
      <div className="h-[calc(100vh-4rem)] max-w-[1400px] mx-auto grid grid-cols-1 lg:grid-cols-[300px_1fr] overflow-hidden" data-testid="chat-page">
        {/* Sidebar */}
        <aside className="border-r border-[var(--rule)] bg-[var(--cream)] flex flex-col min-h-0" data-testid="chat-sidebar">
          <div className="p-4 border-b border-[var(--rule)] bg-white">
            <div className="flex items-center justify-between mb-2">
              <p className="akki-overline flex items-center gap-1.5">
                <MessageCircle className="w-3 h-3 text-[var(--accent)]" /> AKKI Chat
              </p>
              <Button
                onClick={onNewChat}
                size="sm"
                className="h-7 text-[11px] bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white px-2.5"
                data-testid="chat-new-btn"
              >
                <Plus className="w-3 h-3 mr-1" /> New
              </Button>
            </div>
            <p className="text-[10.5px] text-[var(--muted)] leading-relaxed">
              Synisense-shielded · multi-model · audited
            </p>
          </div>
          <div className="flex-1 overflow-y-auto p-2" data-testid="chat-list">
            {loading ? (
              <p className="p-4 text-[11px] text-[var(--muted)] text-center">Loading…</p>
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
                <button
                  key={c.id}
                  onClick={() => setActiveId(c.id)}
                  className={`w-full text-left px-3 py-2.5 rounded-sm mb-1 transition-colors border ${
                    active ? "bg-white border-[var(--accent)]/60" : "border-transparent hover:bg-white"
                  }`}
                  data-testid={`chat-item-${c.id}`}
                >
                  <p className="text-[12.5px] font-medium leading-snug line-clamp-1 text-[var(--ink)]">
                    {c.title}
                  </p>
                  <p className="text-[11px] text-[var(--muted)] line-clamp-1 mt-0.5">
                    {c.last_message_preview || "(no messages yet)"}
                  </p>
                </button>
              );
            })}
          </div>
        </aside>

        {/* Main */}
        <main className="flex flex-col min-h-0 bg-white" data-testid="chat-main">
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
                onPatch={onPatch}
                onArchive={() => onArchive(activeChat.id)}
                onAudit={() => setAuditOpen(true)}
              />

              <div className="flex-1 overflow-y-auto px-8 py-6 space-y-5" data-testid="chat-messages">
                {(activeChat.messages || []).length === 0 ? (
                  <p className="text-center text-[13px] text-[var(--muted)] italic mt-10">
                    Type your first message below.
                  </p>
                ) : (activeChat.messages || []).map((m) => (
                  <Message key={m.id} m={m} activeModel={activeModel} />
                ))}
                {sending && (
                  <div className="flex items-center gap-2 text-[12.5px] text-[var(--muted)] italic">
                    <Loader2 className="w-3 h-3 animate-spin" /> {activeModel?.label || "AKKI"} is thinking…
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>

              <Composer
                value={input}
                onChange={setInput}
                onSubmit={onSubmit}
                sending={sending}
                policy={activeChat.shielding_policy}
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
    </AppShell>
  );
}

function ChatHeader({ chat, models, activeModel, onPatch, onArchive, onAudit }) {
  const [titleEdit, setTitleEdit] = useState(false);
  const [title, setTitle] = useState(chat.title);
  useEffect(() => { setTitle(chat.title); }, [chat.id, chat.title]);

  return (
    <div className="border-b border-[var(--rule)] px-6 py-3 bg-white flex items-center gap-3" data-testid="chat-header">
      <div className="flex-1 min-w-0">
        {titleEdit ? (
          <input
            value={title}
            autoFocus
            onChange={(e) => setTitle(e.target.value)}
            onBlur={() => { setTitleEdit(false); if (title !== chat.title) onPatch({ title }); }}
            onKeyDown={(e) => { if (e.key === "Enter") e.target.blur(); if (e.key === "Escape") { setTitle(chat.title); setTitleEdit(false); } }}
            className="akki-serif text-[16px] text-[var(--ink)] bg-transparent border-b border-[var(--accent)] focus:outline-none w-full"
            data-testid="chat-title-input"
          />
        ) : (
          <button
            onClick={() => setTitleEdit(true)}
            className="akki-serif text-[16px] text-[var(--ink)] hover:text-[var(--accent)] truncate text-left"
            data-testid="chat-title"
          >
            {chat.title}
          </button>
        )}
        <p className="text-[10.5px] text-[var(--muted)] mt-0.5">
          {chat.message_count || 0} messages · {POLICY_LABEL[chat.shielding_policy]}
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
        className="h-8 inline-flex items-center gap-1.5 px-2.5 text-[12px] border border-[var(--rule)] rounded-sm bg-white hover:border-[var(--accent)]/40"
        data-testid="chat-model-trigger"
      >
        <span className="text-[var(--ink)] truncate max-w-[140px]">{active?.label || value}</span>
        <ChevronDown className={`w-3 h-3 text-[var(--muted)] transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div className="absolute right-0 top-full mt-1 z-30 min-w-[260px] bg-white border border-[var(--rule)] rounded-sm shadow-lg py-1" data-testid="chat-model-menu">
          {models.map((m) => (
            <button
              key={m.id}
              onClick={() => { onChange(m.id); setOpen(false); }}
              className={`w-full text-left px-3 py-2 text-[13px] hover:bg-[var(--cream-deep)]/40 ${m.id === value ? "bg-[var(--cream-deep)]/30" : ""}`}
              data-testid={`chat-model-opt-${m.id}`}
            >
              <p className="text-[var(--ink)]">{m.label}</p>
              <p className="text-[11px] text-[var(--muted)] italic">{m.tone}</p>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function PolicyPicker({ value, onChange }) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="h-8 text-[11.5px] border border-[var(--rule)] rounded-sm bg-white px-2 focus:outline-none focus:border-[var(--accent)]"
      data-testid="chat-policy-picker"
      title="Synisense shielding policy for this conversation"
    >
      <option value="auto">Auto-shield</option>
      <option value="always">Always shield</option>
      <option value="off">Off</option>
    </select>
  );
}

function Message({ m, activeModel }) {
  const isUser = m.role === "user";
  const shielded = m.shielded;
  const detected = (m.shielding?.identifiers_masked || 0) > 0;
  const cats = m.shielding?.by_category || {};
  const catSummary = Object.entries(cats).map(([k, n]) => `${n} ${k}${n === 1 ? "" : "s"}`).join(" · ");

  return (
    <div className={`flex gap-3 ${isUser ? "flex-row-reverse" : ""}`} data-testid={`chat-msg-${m.role}`}>
      <div className={`w-7 h-7 rounded-full shrink-0 flex items-center justify-center text-[10px] font-mono ${
        isUser ? "bg-[var(--ink)] text-white" : "bg-[var(--accent-soft)] text-[var(--accent)]"
      }`}>
        {isUser ? "YOU" : "A"}
      </div>
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
        {!isUser && m.model_label && (
          <p className="text-[10px] uppercase tracking-wider text-[var(--muted)] mb-1">
            {m.model_label || activeModel?.label} · {m.latency_ms ? `${(m.latency_ms / 1000).toFixed(1)}s` : ""}
          </p>
        )}
        <div className={`inline-block max-w-full akki-serif text-[14.5px] leading-[1.65] whitespace-pre-wrap ${
          isUser
            ? "bg-[var(--cream-deep)]/50 border border-[var(--rule)] rounded-sm px-3 py-2 text-[var(--ink)]"
            : "text-[var(--ink)]"
        }`}>
          {m.content}
        </div>
      </div>
    </div>
  );
}

function Composer({ value, onChange, onSubmit, sending, policy }) {
  const ta = useRef(null);
  return (
    <div className="border-t border-[var(--rule)] p-3 bg-white" data-testid="chat-composer">
      <div className="flex items-end gap-2">
        <div className="flex-1 bg-[var(--cream)] border border-[var(--rule)] rounded-md p-2 focus-within:border-[var(--accent)]">
          <textarea
            ref={ta}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) { e.preventDefault(); onSubmit(); }
            }}
            placeholder="Message AKKI… (⌘/Ctrl+Enter to send)"
            disabled={sending}
            rows={2}
            className="w-full bg-transparent text-[14px] resize-none focus:outline-none akki-serif leading-relaxed"
            data-testid="chat-input"
          />
          <div className="flex items-center justify-between pt-1.5 border-t border-[var(--rule)]/60 mt-1">
            <div className="flex items-center gap-1 text-[10px] text-[var(--muted)]">
              <Shield className="w-2.5 h-2.5 text-[var(--accent)]" />
              <span className="uppercase tracking-wider">{POLICY_LABEL[policy]}</span>
            </div>
            <span className="text-[10px] text-[var(--muted)]">
              {value.length} / 20,000
            </span>
          </div>
        </div>
        <Button
          onClick={onSubmit}
          disabled={sending || !value.trim()}
          className="bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white h-10 w-12 p-0"
          data-testid="chat-send-btn"
          aria-label="Send"
        >
          {sending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
        </Button>
      </div>
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
  useEffect(() => {
    if (!open || !chatId) return;
    setLoading(true);
    api.get(`/chats/${chatId}/audit`)
      .then(({ data }) => setRows(data?.rows || []))
      .catch(() => setRows([]))
      .finally(() => setLoading(false));
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
