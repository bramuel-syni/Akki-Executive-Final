/**
 * ReadingBody — the document body column.
 *
 * Renders one <p data-anchor-id> per paragraph and inserts page-break
 * separators between pages. Paragraphs are clickable; clicking fires the
 * onParagraphClick handler so the rail can highlight matching items.
 *
 * If `paragraphs` is empty (e.g. document still extracting, or scanned
 * PDF with no usable text), falls back to whatever is in `fallbackText`
 * rendered as a flat block, with a small inline note. This is the
 * "Paragraph anchors aren’t available…" branch from the brief’s state
 * matrix.
 */
import React from "react";

export default function ReadingBody({
  bodyRef,
  paragraphs,
  fallbackText,
  paragraphsUnavailable,
  onParagraphClick,
}) {
  const grouped = [];
  let currentPage = null;
  let pageBuf = [];
  paragraphs.forEach((p) => {
    if (p.page !== currentPage) {
      if (pageBuf.length) grouped.push({ page: currentPage, items: pageBuf });
      currentPage = p.page;
      pageBuf = [];
    }
    pageBuf.push(p);
  });
  if (pageBuf.length) grouped.push({ page: currentPage, items: pageBuf });

  return (
    <div
      ref={bodyRef}
      className="overflow-y-auto bg-[var(--cream)]"
      data-testid="reading-body"
    >
      <article className="max-w-[720px] mx-auto px-6 md:px-8 py-10 md:py-14">
        {paragraphs.length === 0 && paragraphsUnavailable ? (
          <div className="mb-8 px-4 py-3 border border-[var(--rule)] bg-white rounded-sm">
            <p className="text-[12px] text-[var(--muted)] italic">
              Paragraph anchors aren’t available for this document. Citations
              will be page-level only.
            </p>
          </div>
        ) : null}

        {paragraphs.length === 0 && fallbackText ? (
          <div
            className="akki-serif text-[16px] leading-[1.75] text-[var(--ink)] whitespace-pre-wrap"
            data-testid="reading-body-fallback"
          >
            {fallbackText}
          </div>
        ) : null}

        {grouped.map(({ page, items }, pageIdx) => (
          <section key={`page-${page}-${pageIdx}`} className="mb-12">
            {grouped.length > 1 ? (
              <div
                className="flex items-center gap-3 mb-6"
                aria-hidden="true"
                data-testid={`reading-page-break-${page}​`}
              >
                <span className="akki-overline text-[10px] tracking-[0.22em] text-[var(--muted)]">
                  Page {page}
                </span>
                <div className="flex-1 h-px bg-[var(--rule)]" />
              </div>
            ) : null}
            {items.map((p) => (
              <p
                key={p.id}
                data-anchor-id={p.id}
                data-page={p.page}
                data-paragraph-number={p.paragraph_number}
                data-testid={`reading-paragraph-${p.id}`}
                onClick={() => onParagraphClick && onParagraphClick(p.id)}
                className="akki-serif text-[16px] md:text-[17px] leading-[1.75] text-[var(--ink)] mb-5 cursor-pointer scroll-mt-24 transition-colors data-[flash=true]:bg-[var(--accent)]/10 data-[flash=true]:ring-2 data-[flash=true]:ring-[var(--accent)] data-[flash=true]:ring-offset-2 rounded-[2px] px-1"
              >
                {p.text}
              </p>
            ))}
          </section>
        ))}
      </article>
    </div>
  );
}
