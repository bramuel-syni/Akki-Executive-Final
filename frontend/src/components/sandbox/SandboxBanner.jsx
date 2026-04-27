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
      className="bg-[var(--chrome)] text-white/90 px-6 py-2 flex items-center justify-center gap-3 text-[12.5px] border-b border-[var(--chrome)]"
      data-testid="sandbox-banner"
    >
      <Sparkles className="w-3 h-3 text-white/70" strokeWidth={2} />
      <span className="text-white/80">
        {isReadOnly ? (
          <>Sandbox expired — read-only for {readOnlyDays} more day{readOnlyDays === 1 ? "" : "s"}. </>
        ) : days !== null ? (
          <>
            Sandbox — you are exploring fictional data for{" "}
            <span className="text-white font-medium">{activeContext?.name}</span>.{" "}
            <span className="text-white font-medium" data-testid="sandbox-banner-days">
              {days} {days === 1 ? "day" : "days"} remaining
            </span>.{" "}
          </>
        ) : (
          <>Sandbox — you are exploring fictional data. </>
        )}
        <span>When you're ready, AKKI will read your real pack the same way.</span>
      </span>
      <Link
        to={`/signup?from_sandbox=${encodeURIComponent(activeContext?.id || "")}`}
        className="inline-flex items-center gap-1 text-white hover:text-white/80 font-medium transition-colors underline underline-offset-2 decoration-white/30 hover:decoration-white"
        data-testid="sandbox-banner-convert"
      >
        Set up your account <ArrowRight className="w-3 h-3" />
      </Link>
    </div>
  );
}
