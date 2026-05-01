/**
 * DepthOfferCard — the single offer surfaced at the top of Home v2 when
 * the user crosses the corpus threshold. Matches sector → lens mapping
 * from `GET /api/me/depth-status`.
 *
 * Shown only when:
 *   status.eligible === true
 *   status.offer_dismissed === false
 *   status.suggested_offer !== null
 *
 * Interactions:
 *   "Run {{lens_label}} →"  primary CTA.
 *     - Pro plan: navigates to /app/lens?lens={lens_id}
 *     - Free plan: intercepts + opens UpgradeModal
 *   "Not now"                tertiary text link.
 *     - Calls POST /depth-status/dismiss, hides the card, invalidates cache.
 */
import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { openUpgradeModal } from "@/components/depth/UpgradeModal";
import ProPill from "@/components/depth/ProPill";
import { invalidateDepthStatus } from "@/hooks/useDepthStatus";
import { ArrowRight } from "lucide-react";

export default function DepthOfferCard({ status, onDismiss }) {
  const { account } = useAuth();
  const navigate = useNavigate();
  const [dismissing, setDismissing] = useState(false);
  if (!status?.eligible || status?.offer_dismissed || !status?.suggested_offer) {
    return null;
  }
  const offer = status.suggested_offer;
  const isFree = (account?.plan || "free") === "free";
  const featureIsPro = (status.pro_features || []).includes(offer.feature);
  const shouldGate = isFree && featureIsPro;

  const onRun = (e) => {
    if (shouldGate) {
      e?.preventDefault?.();
      openUpgradeModal(`home-offer-${offer.feature}`);
      return;
    }
    navigate(`/app/lens?lens=${encodeURIComponent(offer.lens_id)}`);
  };

  const onDismissClick = async () => {
    if (dismissing) return;
    setDismissing(true);
    try {
      await api.post("/me/depth-status/dismiss");
      invalidateDepthStatus();
      onDismiss?.();
    } catch {
      /* noop — best-effort */
    } finally {
      setDismissing(false);
    }
  };

  return (
    <div
      className="bg-white border border-[var(--border,#e2d9cf)] p-5 md:p-6 mb-4"
      data-testid="depth-offer-card"
    >
      <p className="akki-overline text-[10px] tracking-[0.22em] text-[var(--muted)] mb-2">
        DEPTH
      </p>
      <h3
        className="akki-serif text-[18px] md:text-[20px] text-[var(--ink)] font-normal leading-snug mb-1"
        data-testid="depth-offer-title"
      >
        AKKI now has enough material to run a {offer.lens_label} on your
        board.
      </h3>
      <p className="text-[13px] text-[var(--muted)] mb-4">
        Try one — it&apos;ll take about 90 seconds.
      </p>
      <div className="flex flex-col md:flex-row md:items-center gap-3 md:gap-5">
        <button
          type="button"
          onClick={onRun}
          className="akki-overline tracking-[0.16em] text-[11px] text-white bg-[var(--accent)] hover:bg-[var(--accent)]/90 px-4 py-2.5 inline-flex items-center gap-2 w-full md:w-auto justify-center"
          data-testid="depth-offer-run"
        >
          RUN {offer.lens_label.toUpperCase()}
          {shouldGate ? <ProPill className="bg-white/20 text-white" /> : null}
          <ArrowRight size={12} />
        </button>
        <button
          type="button"
          onClick={onDismissClick}
          disabled={dismissing}
          className="text-[12px] text-[var(--muted)] hover:text-[var(--ink)] underline-offset-2 hover:underline text-center md:text-left disabled:opacity-50"
          data-testid="depth-offer-dismiss"
        >
          {dismissing ? "Dismissing…" : "Not now"}
        </button>
      </div>
    </div>
  );
}
