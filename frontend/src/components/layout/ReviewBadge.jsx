/**
 * ReviewBadge — top-bar Daily Review notification.
 *
 * Phase F.5 redesign: was a standalone oxblood pill ("N awaiting
 * review") that dominated the top bar; now renders as a conventional
 * bell-icon button with a small numeric badge dot, matching the
 * pattern most users expect for inbox/queue counts.
 *
 * Polls /api/me/review-queue/counts every 60s and on tab focus.
 * Hidden when total === 0 or when on /app/review (the page already
 * shows the count internally).
 *
 * Click target unchanged: /app/review.
 */
import React from "react";
import { Link, useLocation } from "react-router-dom";
import { Bell } from "lucide-react";
import useReviewCounts from "@/hooks/useReviewCounts";
import { useAuth } from "@/contexts/AuthContext";

export default function ReviewBadge() {
  const location = useLocation();
  const { account } = useAuth();
  const onReviewPage = location.pathname.startsWith("/app/review");
  const enabled = Boolean(account) && !onReviewPage;
  const { total } = useReviewCounts({ enabled });

  if (!enabled) return null;
  if (!total || total <= 0) return null;

  // Numeric badge uses the small-pill pattern: ≥99 collapses to "99+"
  // so the badge stays inside the dot at the bell's top-right corner.
  const display = total > 99 ? "99+" : String(total);

  return (
    <Link
      to="/app/review"
      className="relative inline-flex items-center justify-center w-8 h-8 text-[var(--muted)] hover:text-[var(--ink)] hover:bg-[var(--cream-deep)] rounded-md transition-colors"
      data-testid="review-badge"
      title={`${total} awaiting review`}
      aria-label={`Daily Review · ${total} awaiting review`}
    >
      <Bell className="w-4 h-4" strokeWidth={1.7} />
      <span
        className="absolute -top-0.5 -right-0.5 min-w-[16px] h-[16px] px-1 inline-flex items-center justify-center rounded-full bg-[var(--accent)] text-white text-[10px] font-mono leading-none tracking-tight"
        data-testid="review-badge-count"
      >
        {display}
      </span>
    </Link>
  );
}
