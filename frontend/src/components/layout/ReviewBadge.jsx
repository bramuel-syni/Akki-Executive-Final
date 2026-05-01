/**
 * ReviewBadge — top-bar Daily Review pill (Phase 3, Advisory 4).
 *
 * Polls /api/me/review-queue/counts every 60s and on tab focus.
 * Hidden when total === 0 or when on /app/review (the page already
 * shows the count internally).
 */
import React from "react";
import { Link, useLocation } from "react-router-dom";
import { Inbox } from "lucide-react";
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

  return (
    <Link
      to="/app/review"
      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-sm bg-[var(--accent)] text-white akki-overline tracking-[0.16em] text-[10px] hover:opacity-90"
      data-testid="review-badge"
      title="Open Daily Review"
    >
      <Inbox className="w-3 h-3" />
      {total} awaiting review
    </Link>
  );
}
