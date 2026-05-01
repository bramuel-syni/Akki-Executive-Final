/**
 * ReviewItemCard — the single large card that renders the current
 * Daily Review item. Two flavours, switched by `item.kind`.
 */
import React from "react";
import { FileText, Mail, Paperclip } from "lucide-react";

const KIND_LABEL = {
  inbound_doc: "Inbound document",
  briefing: "Briefing draft",
};

export default function ReviewItemCard({ item }) {
  if (!item) return null;
  const kindLabel = KIND_LABEL[item.kind] || item.kind;
  const p = item.payload || {};

  return (
    <article
      className="bg-white border border-[var(--rule)] rounded-sm p-6 md:p-8"
      data-testid={`review-item-card-${item.kind}`}
      data-item-id={item.id}
    >
      <header className="mb-5 flex items-start gap-3">
        <span className="inline-flex items-center justify-center w-8 h-8 rounded-sm bg-[var(--cream)] text-[var(--accent)] shrink-0">
          {item.kind === "briefing" ? <FileText className="w-4 h-4" /> : <Mail className="w-4 h-4" />}
        </span>
        <div className="flex-1 min-w-0">
          <p className="akki-overline text-[10px] tracking-[0.22em] text-[var(--muted)] mb-1">
            {kindLabel} · {item.context_name}
          </p>
          <h2 className="akki-serif text-[20px] md:text-[22px] leading-[1.25] text-[var(--ink)] font-normal">
            {item.kind === "briefing" ? p.title : p.subject}
          </h2>
          {item.kind === "inbound_doc" ? (
            <p className="text-[12.5px] text-[var(--muted)] mt-1.5">
              From <span className="text-[var(--ink)]">{p.from_name || p.from}</span>{" "}
              {p.review_reason ? (
                <span className="italic">· {p.review_reason}</span>
              ) : null}
            </p>
          ) : null}
          {item.kind === "briefing" && p.doc_title ? (
            <p className="text-[12.5px] text-[var(--muted)] mt-1.5">
              Drafted from <span className="text-[var(--ink)] italic">{p.doc_title}</span>
            </p>
          ) : null}
        </div>
      </header>

      <div className="akki-serif text-[15px] leading-[1.7] text-[var(--ink)] whitespace-pre-wrap">
        {item.kind === "inbound_doc" ? (p.snippet || "(no preview available)") : (p.opening_paragraph || "(no preview available)")}
      </div>

      <footer className="mt-6 pt-4 border-t border-[var(--rule)] flex flex-wrap items-center gap-3 text-[11px] text-[var(--muted)]">
        {item.kind === "inbound_doc" && p.attachments > 0 ? (
          <span className="inline-flex items-center gap-1">
            <Paperclip className="w-3 h-3" /> {p.attachments} attachment{p.attachments === 1 ? "" : "s"}
          </span>
        ) : null}
        {item.kind === "inbound_doc" && p.suggested_action ? (
          <span className="italic">
            Suggested: file in <span className="text-[var(--ink)] not-italic">{item.context_name}</span>
          </span>
        ) : null}
        {item.kind === "briefing" ? (
          <>
            {p.word_count ? <span>{p.word_count} words</span> : null}
            {p.items_count ? <span>{p.items_count} signal-anchored item{p.items_count === 1 ? "" : "s"}</span> : null}
            {p.validator_score != null ? (
              <span>Validator score: {p.validator_score}</span>
            ) : null}
          </>
        ) : null}
      </footer>
    </article>
  );
}
