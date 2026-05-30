/**
 * Z3 (2026-02) — Claude-style chat-bubble actions.
 *
 * Renders inline actions on user bubbles (Edit · Copy) and on
 * assistant bubbles (Regenerate · Copy). Hover-revealed via a
 * `group-hover:opacity-100` parent contract (caller wraps each
 * bubble in a `group` div). Keyboard-accessible: each action is a
 * `<button>` with explicit `aria-label`. Clipboard write uses
 * `navigator.clipboard.writeText` with a graceful textarea-fallback
 * for older surfaces.
 */
import React, { useState } from "react";
import { Copy, Edit3, RotateCcw, Check } from "lucide-react";


async function _copy(text) {
  try {
    await navigator.clipboard.writeText(text || "");
    return true;
  } catch {
    // Fallback: hidden textarea + document.execCommand. Works on
    // older WebViews / non-HTTPS local-dev surfaces.
    try {
      const ta = document.createElement("textarea");
      ta.value = text || "";
      ta.style.position = "fixed"; ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      const ok = document.execCommand("copy");
      document.body.removeChild(ta);
      return !!ok;
    } catch {
      return false;
    }
  }
}


function ActionBtn({ onClick, label, icon: Icon, testid, just_copied }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      title={label}
      className="inline-flex items-center gap-1 px-1.5 py-1 rounded-sm text-[10.5px] uppercase tracking-[0.06em] font-mono text-[var(--muted)] hover:text-[var(--ink)] hover:bg-[var(--parchment)]/70 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]/50"
      data-testid={testid}
    >
      {just_copied ? <Check className="w-3 h-3" /> : <Icon className="w-3 h-3" />}
      <span>{just_copied ? "Copied" : label}</span>
    </button>
  );
}


export default function MessageActions({ messageId, role, content, onEdit, onRegenerate }) {
  const [copied, setCopied] = useState(false);
  const onCopy = async () => {
    const ok = await _copy(content);
    if (ok) {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    }
  };
  const isUser = role === "user";
  return (
    <div
      className={`message-actions opacity-0 group-hover:opacity-100 focus-within:opacity-100 transition-opacity mt-1 inline-flex gap-1 ${isUser ? "justify-end" : "justify-start"}`}
      data-testid={`chat-message-actions-${role}`}
      data-message-id={messageId || ""}
    >
      {isUser ? (
        <>
          <ActionBtn onClick={() => onEdit && onEdit(content)} label="Edit" icon={Edit3}
            testid={`chat-action-edit-${messageId || "draft"}`} />
          <ActionBtn onClick={onCopy} label="Copy" icon={Copy}
            testid={`chat-action-copy-${messageId || "draft"}`} just_copied={copied} />
        </>
      ) : (
        <>
          <ActionBtn onClick={() => onRegenerate && onRegenerate(messageId)} label="Regenerate" icon={RotateCcw}
            testid={`chat-action-regenerate-${messageId || "draft"}`} />
          <ActionBtn onClick={onCopy} label="Copy" icon={Copy}
            testid={`chat-action-copy-${messageId || "draft"}`} just_copied={copied} />
        </>
      )}
    </div>
  );
}
