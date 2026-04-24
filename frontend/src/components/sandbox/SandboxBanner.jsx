/**
 * SandboxBanner — persistent, quiet chrome that sits above the top bar.
 * Shows days-remaining and a gentle conversion link. Only renders when the
 * active context is type='sandbox'.
 */
import React, { useMemo } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { Sparkles, ArrowRight } from "lucide-react";

function daysUntil(isoString) {
  if (!isoString) return null;
  const target = new Date(isoString).getTime();
  if (!Number.isFinite(target)) return null;
  const diffMs = target - Date.now();
  if (diffMs <= 0) return 0;
  return Math.ceil(diffMs / (1000 * 60 * 60 * 24));
}

export default function SandboxBanner() {
  const { activeContext } = useAuth();
  const meta = activeContext?.sandbox_metadata || null;
  const isSandbox = activeContext?.type === "sandbox";

  const days = useMemo(() => daysUntil(meta?.expires_at), [meta?.expires_at]);
  const readOnlyDays = useMemo(() => daysUntil(meta?.read_only_until), [meta?.read_only_until]);
  const isReadOnly = days === 0 && readOnlyDays && readOnlyDays > 0;

  if (!isSandbox) return null;

  return (
    <div
      className="bg-[var(--cream-deep)] border-b border-[var(--rule)] px-6 py-2 flex items-center justify-center gap-3 text-[12.5px]"
      data-testid="sandbox-banner"
    >
      <Sparkles className="w-3 h-3 text-[var(--accent)]" strokeWidth={2} />
      <span className="text-[var(--muted)]">
        {isReadOnly ? (
          <>Sandbox expired — read-only for {readOnlyDays} more day{readOnlyDays === 1 ? "" : "s"}. </>
        ) : days !== null ? (
          <>
            Sandbox — you are exploring fictional data for{" "}
            <span className="text-[var(--ink)] font-medium">{activeContext?.name}</span>.{" "}
            <span className="text-[var(--accent)] font-medium" data-testid="sandbox-banner-days">
              {days} {days === 1 ? "day" : "days"} remaining
            </span>.{" "}
          </>
        ) : (
          <>Sandbox — you are exploring fictional data. </>
        )}
        <span>Ready to use AKKI on your real data?</span>
      </span>
      <Link
        to={`/signup?from_sandbox=${encodeURIComponent(activeContext?.id || "")}`}
        className="inline-flex items-center gap-1 text-[var(--accent)] hover:text-[var(--accent)]/80 font-medium transition-colors"
        data-testid="sandbox-banner-convert"
      >
        Set up your account <ArrowRight className="w-3 h-3" />
      </Link>
    </div>
  );
}
