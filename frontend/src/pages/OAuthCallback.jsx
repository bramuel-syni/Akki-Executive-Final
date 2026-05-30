/**
 * Phase U (2026-05-27) — OAuth callback page.
 *
 * Mounted at `/oauth/callback`. Reads the `session_id` from the URL
 * hash fragment (per Emergent Auth playbook — the hash is purely
 * client-side and never reaches the server log), POSTs it to the
 * backend, then stores the returned JWT + redirects to the
 * `next_url` (either `/app/` or `/app/first-session` for new
 * accounts).
 *
 * Race-condition guard: `useRef` (NOT useState) is the processed
 * flag — `useState` re-renders run the effect twice under React
 * StrictMode, which would consume the session_id twice. The ref
 * pattern is documented as the canonical fix in the playbook.
 */
import React, { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { api, apiErrorMessage } from "@/lib/api";
import Logo from "@/components/brand/Logo";

export default function OAuthCallback() {
  const [status, setStatus] = useState("processing"); // "processing" | "error"
  const [errorMsg, setErrorMsg] = useState("");
  const hasProcessed = useRef(false);
  const { afterAuth } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (hasProcessed.current) return;
    hasProcessed.current = true;

    // Read session_id from the URL hash fragment. Per the playbook
    // we MUST process this synchronously here — the hash is the
    // ONLY place the value lives (Emergent Auth puts it there to
    // avoid leaking into server logs / query string history).
    const hash = window.location.hash || "";
    const match = hash.match(/session_id=([^&]+)/);
    const sessionId = match ? decodeURIComponent(match[1]) : null;

    if (!sessionId) {
      setStatus("error");
      setErrorMsg("No sign-in session present. Please try again.");
      return;
    }

    (async () => {
      try {
        // Phase P5.3 (2026-02) — if /welcome/{token} stashed a
        // pending magic-link token in sessionStorage before kicking
        // off the Google OAuth flow, retrieve + forward it so the
        // backend can consume the cohort invite in the same call.
        // Wipe the key immediately so a back-button replay can't
        // try to consume an already-used token.
        let pendingMagicLinkToken = null;
        try {
          pendingMagicLinkToken = window.sessionStorage.getItem(
            "akki.pending_magic_link_token",
          );
          window.sessionStorage.removeItem("akki.pending_magic_link_token");
        } catch (_e) { /* quota / private-mode noop */ }

        const payload = { session_id: sessionId };
        if (pendingMagicLinkToken) payload.magic_link_token = pendingMagicLinkToken;
        const { data } = await api.post("/auth/oauth/google/finish", payload);
        // Reuse the existing AuthContext.afterAuth() path so the
        // app state matches the email/password sign-in flow exactly.
        // The bootstrap on next mount will pull the full account
        // record + memberships via /api/me — we just need the token
        // + a stub account object to seed the initial render.
        await afterAuth({
          access_token: data.token,
          account: { id: data.account_id, email: data.email },
        });
        // Wipe the session_id from the URL so a refresh doesn't try to
        // consume it again.
        window.history.replaceState(null, "", "/oauth/callback");
        navigate(data?.next_url || "/app", { replace: true });
      } catch (err) {
        // eslint-disable-next-line no-console
        console.warn("OAuth finish failed:", err?.response?.data || err);
        setStatus("error");
        setErrorMsg(apiErrorMessage(err, "Could not complete sign-in."));
      }
    })();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div
      className="min-h-screen bg-[var(--cream)] flex items-center justify-center px-6"
      data-testid="oauth-callback-page"
    >
      <div className="w-full max-w-md text-center space-y-6">
        <div className="flex justify-center">
          <Logo size="lg" />
        </div>
        {status === "processing" && (
          <>
            <div
              className="mx-auto w-7 h-7 border-2 border-[var(--ink)] border-t-transparent rounded-full animate-spin"
              role="status"
              aria-label="Signing you in"
              data-testid="oauth-callback-spinner"
            />
            <p
              className="text-[13px] text-[var(--muted)] tracking-wide"
              data-testid="oauth-callback-status"
            >
              Signing you in…
            </p>
          </>
        )}
        {status === "error" && (
          <div
            className="space-y-3"
            data-testid="oauth-callback-error"
          >
            <p className="font-georgia text-[18px] text-[var(--ink)]">
              We hit a snag.
            </p>
            <p className="text-[13px] text-[var(--muted)] leading-relaxed">
              {errorMsg}
            </p>
            <button
              type="button"
              onClick={() => navigate("/signin", { replace: true })}
              className="text-[12px] tracking-wide text-[var(--accent)] hover:text-[var(--ink)] underline-offset-4 hover:underline"
              data-testid="oauth-callback-back-to-signin"
            >
              Back to sign in
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
