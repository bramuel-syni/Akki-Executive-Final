/**
 * Website v7 — shared page primitives.
 * Hero with lift word + inverted CTA reused across most pages.
 */
import React from "react";
import { Link } from "react-router-dom";

export function HeroWithLift({ kicker, headline, lift, dek, primaryCta, secondaryCta, image, imageAlt, testId }) {
  // Inject one-word oxblood lift; case-sensitive single replace.
  let head = headline;
  const liftIdx = lift ? headline.indexOf(lift) : -1;
  const before = liftIdx >= 0 ? headline.slice(0, liftIdx) : headline;
  const after  = liftIdx >= 0 ? headline.slice(liftIdx + (lift || "").length) : "";

  return (
    <section className="hero" aria-labelledby={`${testId}-h1`} data-testid={testId || "page-hero"}>
      <div className="hero-grid" style={image ? undefined : { gridTemplateColumns: "1fr" }}>
        <div className="hero-text">
          {kicker && <p className="kicker reveal-1">{kicker}</p>}
          <h1 id={`${testId}-h1`} className="hero reveal-2">
            {liftIdx >= 0 ? (
              <>{before}<em className="lift">{lift}</em>{after}</>
            ) : head}
          </h1>
          {dek && <p className="dek reveal-3">{dek}</p>}
          {(primaryCta || secondaryCta) && (
            <div className="hero-actions reveal-4">
              {primaryCta && (
                <Link to={primaryCta.href} className="btn-primary btn-hero" data-testid={`${testId}-cta-primary`}>
                  {primaryCta.label}
                </Link>
              )}
              {secondaryCta && (
                <Link to={secondaryCta.href} className="btn-tertiary" data-testid={`${testId}-cta-secondary`}>
                  {secondaryCta.label} →
                </Link>
              )}
            </div>
          )}
        </div>
        {image && (
          <div className="hero-image-wrap reveal-4">
            <img
              src={image}
              alt={imageAlt || ""}
              width="800" height="1000"
              loading="lazy"
            />
          </div>
        )}
      </div>
    </section>
  );
}

export function CitationPills({ pills }) {
  if (!pills || pills.length === 0) return null;
  return (
    <p style={{ marginTop: 8 }}>
      {pills.map((p, i) => (
        <span key={i} className="citation-pill" style={{ marginRight: 8 }} data-testid={`citation-pill-${i}`}>{p}</span>
      ))}
    </p>
  );
}

export function InvertedCtaSection({ kicker, headline, body, ctaLabel, ctaHref, meta, testId }) {
  return (
    <section className="inverted-cta section-reveal" data-testid={testId || "inverted-cta"}>
      <div className="inverted-cta-inner">
        <div>
          {kicker && <p className="kicker">{kicker}</p>}
          <h2>{headline}</h2>
          {body && <p className="dek">{body}</p>}
        </div>
        <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-start", gap: 12 }}>
          <Link to={ctaHref} className="btn-cta-section" data-testid={`${testId || "inverted-cta"}-button`}>
            {ctaLabel} →
          </Link>
          {meta && <p className="inverted-cta-meta">{meta}</p>}
        </div>
      </div>
    </section>
  );
}
