/**
 * Phase P3.4 (2026-02) — Idle warning + re-auth + session-expired surfaces.
 *
 * Mounted once at the AppShell level. Listens for two signals:
 *
 *   1. Idle countdown — tracked client-side, fires a toast at 28-min
 *      mark warning "Re-auth in 2 min". Activity = any axios request
 *      we make (so the same definition as the backend `last_activity_at`).
 *   2. `akki:session-event` — dispatched by `lib/api.js` when the
 *      backend returns `session_idle_timeout` (open re-auth modal) or
 *      `session_absolute_timeout` (open expired surface; full sign-out).
 *
 * Voice-clean copy. Tested via DOM trace at /tmp/p3_trace_session_timeout.py.
 */
import React, { useEffect, useState, useCallback, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from "@/components/ui/dialog";
import { api, apiErrorMessage } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { toast } from "sonner";
import { Clock } from "lucide-react";

const IDLE_WARN_MS = 28 * 60 * 1000;   // 28 min — warn 2 min before backend cutoff
const IDLE_CUTOFF_MS = 30 * 60 * 1000; // 30 min — backend will reject after this

export default function SessionTimeoutGuard() {
  const { account, logout } = useAuth();
  const [reauthOpen, setReauthOpen] = useState(false);
  const [expiredOpen, setExpiredOpen] = useState(false);
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const warningShownRef = useRef(false);
  const lastActivityRef = useRef(Date.now());

  // Track activity client-side so we can warn BEFORE the backend
  // cuts us off. Bumped on every axios request via interceptor below.
  const bumpActivity = useCallback(() => {
    lastActivityRef.current = Date.now();
    warningShownRef.current = false;
  }, []);

  useEffect(() => {
    // Wire the axios bump.
    const reqId = api.interceptors.request.use((config) => {
      bumpActivity();
      return config;
    });
    return () => { api.interceptors.request.eject(reqId); };
  }, [bumpActivity]);

  useEffect(() => {
    // Listen for backend-driven session events.
    const handler = (e) => {
      const code = e?.detail?.code;
      if (code === "session_idle_timeout") setReauthOpen(true);
      if (code === "session_absolute_timeout") setExpiredOpen(true);
    };
    window.addEventListener("akki:session-event", handler);
    return () => window.removeEventListener("akki:session-event", handler);
  }, []);

  useEffect(() => {
    if (!account) return undefined;
    // Poll every 30s for the warning threshold.
    const id = setInterval(() => {
      const idle = Date.now() - lastActivityRef.current;
      if (idle >= IDLE_WARN_MS && idle < IDLE_CUTOFF_MS && !warningShownRef.current) {
        warningShownRef.current = true;
        toast.warning("Re-auth in 2 min", {
          description: "Inactive — re-enter your password to keep this session active.",
          duration: 60_000,
          id: "session-idle-warning",
        });
      }
    }, 30_000);
    return () => clearInterval(id);
  }, [account]);

  const submitReauth = async (e) => {
    e.preventDefault();
    if (!password) return;
    setBusy(true);
    try {
      // Re-auth = a fresh login on the same email. The login endpoint
      // mints a fresh access_token with a new iat → resets the
      // absolute window AND refreshes last_activity_at server-side.
      //
      // Phase P5.5 (2026-02) — sync the new access_token to
      // localStorage so the api.js Bearer interceptor stops carrying
      // the STALE token on subsequent requests (the HttpOnly cookie
      // is also updated by the server but the SPA may still send the
      // old Bearer header alongside it and the backend prefers the
      // Bearer source).
      const { data } = await api.post("/auth/login", { email: account.email, password });
      if (data?.access_token) {
        try { window.localStorage.setItem("akki_access_token", data.access_token); }
        catch { /* quota/private-mode noop */ }
      }
      bumpActivity();
      setReauthOpen(false);
      setPassword("");
      toast.success("Session refreshed.");
    } catch (err) {
      toast.error(apiErrorMessage(err));
    } finally { setBusy(false); }
  };

  const onForcedSignout = async () => {
    try { await logout(); } catch (_e) { /* best effort */ }
    setExpiredOpen(false);
    if (typeof window !== "undefined") window.location.href = "/signin";
  };

  return (
    <>
      {/* Idle re-auth modal (server says session_idle_timeout) */}
      <Dialog open={reauthOpen} onOpenChange={setReauthOpen}>
        <DialogContent className="bg-white rounded-sm border max-w-md" data-testid="session-reauth-modal">
          <DialogHeader>
            <DialogTitle className="text-xl font-semibold text-[var(--ink)] flex items-center gap-2">
              <Clock className="w-5 h-5 text-[var(--accent)]" /> Re-enter your password
            </DialogTitle>
          </DialogHeader>
          <form onSubmit={submitReauth} className="space-y-4">
            <p className="text-sm text-slate-600">
              Inactive for 30 minutes. Re-enter your password to
              continue this session. Your work in progress is intact.
            </p>
            <div className="space-y-2">
              <Label htmlFor="reauth_password" className="text-xs uppercase tracking-wider text-slate-500 font-semibold">
                Password
              </Label>
              <Input
                id="reauth_password"
                type="password"
                autoComplete="current-password"
                autoFocus
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="h-9 text-sm rounded-sm"
                data-testid="session-reauth-input"
              />
            </div>
            <DialogFooter>
              <Button
                type="button" variant="ghost"
                onClick={onForcedSignout}
                data-testid="session-reauth-signout-btn"
              >
                Sign out instead
              </Button>
              <Button
                type="submit"
                disabled={busy || !password}
                className="bg-[var(--ink)] hover:bg-[#0E2958] rounded-sm h-9"
                data-testid="session-reauth-submit-btn"
              >
                {busy ? "Verifying…" : "Continue"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Absolute-timeout expired surface */}
      <Dialog open={expiredOpen} onOpenChange={setExpiredOpen}>
        <DialogContent className="bg-white rounded-sm border max-w-md" data-testid="session-expired-modal">
          <DialogHeader>
            <DialogTitle className="text-xl font-semibold text-[var(--ink)]">
              Session expired
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <p className="text-sm text-slate-600">
              For your safety, sessions end after 12 hours. Sign in
              again to continue.
            </p>
          </div>
          <DialogFooter>
            <Button
              onClick={onForcedSignout}
              className="bg-[var(--ink)] hover:bg-[#0E2958] rounded-sm h-9"
              data-testid="session-expired-signout-btn"
            >
              Sign in
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
