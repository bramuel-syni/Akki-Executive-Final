/**
 * Phase U (2026-05-27) — OAuth sign-in buttons.
 *
 * Two CTAs — "Continue with Google" + "Continue with Microsoft" —
 * rendered side-by-side below the email/password form on /signin.
 *
 * Google: full flow wired via Emergent Auth (zero config).
 * Microsoft: button disabled with "Coming soon" badge until creds
 *   arrive in backend/.env. The backend route returns 503 with the
 *   locked `{error: "microsoft_oauth_not_configured", needs:...}`
 *   payload — we surface a friendly toast on click rather than the
 *   raw error so the UX is consistent with the disabled state.
 *
 * REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT
 * URLS — THIS BREAKS THE AUTH. The redirect URL is derived from
 * window.location.origin at click time.
 */
import React, { useEffect, useState } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";

// Inline SVG icons (no external dependency — these are the standard
// brand glyphs from Google + Microsoft press kits, distilled to a 24×24
// monochrome-ish form for editorial coherence with the rest of the
// sign-in surface).
function GoogleIcon({ className = "w-4 h-4" }) {
  return (
    <svg className={className} viewBox="0 0 24 24" aria-hidden="true">
      <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
      <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.99.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
      <path fill="#FBBC05" d="M5.84 14.1c-.22-.66-.35-1.36-.35-2.1s.13-1.44.35-2.1V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.83z"/>
      <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.83C6.71 7.31 9.14 5.38 12 5.38z"/>
    </svg>
  );
}

function MicrosoftIcon({ className = "w-4 h-4" }) {
  return (
    <svg className={className} viewBox="0 0 21 21" aria-hidden="true">
      <rect x="1" y="1" width="9" height="9" fill="#F25022"/>
      <rect x="11" y="1" width="9" height="9" fill="#7FBA00"/>
      <rect x="1" y="11" width="9" height="9" fill="#00A4EF"/>
      <rect x="11" y="11" width="9" height="9" fill="#FFB900"/>
    </svg>
  );
}

export default function OAuthButtons() {
  const [busy, setBusy] = useState(null); // "google" | "microsoft" | null
  const [microsoftAvailable, setMicrosoftAvailable] = useState(false);

  // Phase U.2 (2026-02) — Microsoft OAuth probe. Backend
  // `/api/auth/oauth/microsoft/start` is now live (auth_oauth.py).
  // We probe with `?probe=1` (HEAD-equivalent in this codebase) so we
  // don't burn a real PKCE/state pair on page load. If unavailable
  // (503 or network), gracefully degrade.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        await api.get("/auth/oauth/microsoft/start?probe=1");
        if (!cancelled) setMicrosoftAvailable(true);
      } catch (err) {
        const status = err?.response?.status;
        // 503 → backend declares Microsoft locked; anything else also
        // disables the button.
        if (!cancelled) setMicrosoftAvailable(status !== 503);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const onGoogle = async () => {
    setBusy("google");
    try {
      // Resolve the auth base URL from the backend (lets us pivot the
      // provider config without a frontend redeploy).
      const { data } = await api.get("/auth/oauth/google/start");
      // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR
      // REDIRECT URLS — THIS BREAKS THE AUTH. Use window.location.origin.
      const redirectUrl = window.location.origin + (data?.callback_path || "/oauth/callback");
      const authUrl = `${data?.auth_base_url}?redirect=${encodeURIComponent(redirectUrl)}`;
      window.location.href = authUrl;
    } catch (err) {
      // eslint-disable-next-line no-console
      console.warn("OAuth start failed:", err);
      toast.error("Could not start Google sign-in. Please try again.");
      setBusy(null);
    }
  };

  const onMicrosoft = async () => {
    // Phase U.2 (2026-02) — wire the real backend flow.
    // The backend `/api/auth/oauth/microsoft/start` returns
    // `{ authorize_url, ... }`; the SPA redirects the browser to
    // `authorize_url` and the rest of the flow happens on the backend.
    setBusy("microsoft");
    try {
      const { data } = await api.get("/auth/oauth/microsoft/start");
      const authorizeUrl = data?.authorize_url;
      if (!authorizeUrl) {
        throw new Error("Backend did not return authorize_url");
      }
      // Full-page navigation — backend manages PKCE + state + cookie
      // shape from here; SPA hands off cleanly.
      window.location.href = authorizeUrl;
    } catch (err) {
      // eslint-disable-next-line no-console
      console.warn("Microsoft OAuth start failed:", err);
      toast.error("Could not start Microsoft sign-in. Please try again.");
      setBusy(null);
    }
  };

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3" data-testid="oauth-buttons">
      <Button
        type="button"
        variant="outline"
        onClick={onGoogle}
        disabled={busy === "google"}
        className="h-11 bg-white border-[var(--rule)] text-[var(--ink)] hover:bg-[var(--cream)] hover:border-[var(--ink)] rounded-sm text-[13px] font-medium tracking-wide transition-colors flex items-center justify-center gap-2.5"
        data-testid="oauth-google-btn"
      >
        <GoogleIcon className="w-4 h-4" />
        <span>{busy === "google" ? "Opening Google…" : "Continue with Google"}</span>
      </Button>
      <Button
        type="button"
        variant="outline"
        onClick={onMicrosoft}
        disabled={!microsoftAvailable || busy === "microsoft"}
        className="h-11 bg-white border-[var(--rule)] text-[var(--ink)] hover:bg-[var(--cream)] hover:border-[var(--ink)] rounded-sm text-[13px] font-medium tracking-wide transition-colors flex items-center justify-center gap-2.5 disabled:opacity-60"
        data-testid="oauth-microsoft-btn"
        title={microsoftAvailable ? "Continue with Microsoft" : "Coming soon"}
      >
        <MicrosoftIcon className="w-4 h-4" />
        <span>{busy === "microsoft"
          ? "Opening Microsoft…"
          : (microsoftAvailable ? "Continue with Microsoft" : "Microsoft (soon)")}</span>
      </Button>
    </div>
  );
}
