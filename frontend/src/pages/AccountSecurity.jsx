import React, { useState } from "react";
import AppShell from "@/components/layout/AppShell";
import { useAuth } from "@/contexts/AuthContext";
import { api, apiErrorMessage } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from "@/components/ui/dialog";
import { toast } from "sonner";
import { ShieldCheck, Lock, AlertTriangle, Trash2 } from "lucide-react";

export default function AccountSecurity() {
  const { account, bootstrap, logout } = useAuth();
  const [setup, setSetup] = useState(null);
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);

  // Phase X (2026-02 fork-resume) — self-service account deletion.
  const [dangerOpen, setDangerOpen] = useState(false);
  const [confirmEmail, setConfirmEmail] = useState("");
  const [deletionBusy, setDeletionBusy] = useState(false);

  const requestDeletion = async () => {
    setDeletionBusy(true);
    try {
      const { data } = await api.post("/me/delete-account", { confirm: confirmEmail });
      toast.success(
        `Account scheduled for deletion. You have until ${new Date(data.deletion_scheduled_for).toLocaleDateString()} to cancel.`
      );
      setDangerOpen(false);
      setConfirmEmail("");
      await bootstrap();
    } catch (e) {
      toast.error(apiErrorMessage(e));
    } finally {
      setDeletionBusy(false);
    }
  };

  const cancelDeletion = async () => {
    setDeletionBusy(true);
    try {
      await api.post("/me/delete-account/cancel");
      toast.success("Account deletion cancelled.");
      await bootstrap();
    } catch (e) {
      toast.error(apiErrorMessage(e));
    } finally {
      setDeletionBusy(false);
    }
  };

  const startSetup = async () => {
    setBusy(true);
    try {
      const { data } = await api.post("/auth/mfa/setup");
      setSetup(data);
    } catch (e) {
      toast.error(apiErrorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const verify = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await api.post("/auth/mfa/verify", { code });
      await bootstrap();
      setSetup(null);
      setCode("");
      toast.success("MFA enabled");
    } catch (err) {
      toast.error(apiErrorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const disable = async () => {
    setBusy(true);
    try {
      await api.post("/auth/mfa/disable");
      await bootstrap();
      toast.success("MFA disabled");
    } catch (e) {
      toast.error(apiErrorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <AppShell>
      <div className="p-8 akki-w-narrow">
        <div className="mb-8">
          <p className="akki-overline mb-2">Account</p>
          <h1 className="text-3xl font-light tracking-tight text-[var(--ink)]">Security</h1>
          <p className="text-sm text-slate-500 mt-2">
            Protect your account with two-factor authentication.
          </p>
        </div>

        <section className="bg-white border border-[#E1E6ED] rounded-sm">
          <div className="px-6 py-4 border-b border-[#E1E6ED] flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-[var(--ink)] flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-[var(--accent)]" /> Two-factor authentication (TOTP)
              </p>
              <p className="text-xs text-slate-500 mt-1">
                Recommended for context admins. Use any authenticator app (1Password, Authy, Google Authenticator).
              </p>
            </div>
            <span className={`text-[10px] uppercase tracking-wider px-2 py-1 rounded-sm ${account?.mfa_enabled ? "bg-emerald-50 text-emerald-700 border border-emerald-200" : "bg-[var(--ned-purple)]/10 text-[var(--ned-purple)] border border-[var(--ned-purple)]/20"}`}>
              {account?.mfa_enabled ? "Enabled" : "Off"}
            </span>
          </div>
          <div className="p-6 space-y-5">
            {account?.mfa_enabled ? (
              <div className="space-y-3">
                <p className="text-sm text-[var(--ink)] flex items-center gap-2">
                  <Lock className="w-4 h-4 text-emerald-600" /> MFA is active on your account.
                </p>
                <Button
                  variant="outline" className="border-red-500 text-red-600 hover:bg-red-50 rounded-sm h-9"
                  onClick={disable} disabled={busy}
                  data-testid="disable-mfa-btn"
                >
                  {busy ? "Working…" : "Disable MFA"}
                </Button>
              </div>
            ) : !setup ? (
              <Button
                onClick={startSetup} disabled={busy}
                className="bg-[var(--ink)] hover:bg-[#0E2958] rounded-sm h-9"
                data-testid="start-mfa-btn"
              >
                {busy ? "Preparing…" : "Enable MFA"}
              </Button>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-[auto_1fr] gap-6">
                <div className="border border-[#E1E6ED] p-4 bg-white rounded-sm">
                  <img src={setup.qr_data_url} alt="Scan QR" className="w-44 h-44" data-testid="mfa-qr" />
                </div>
                <div className="space-y-4">
                  <div>
                    <p className="text-xs uppercase tracking-wider text-slate-500 font-semibold mb-1">
                      Or enter this secret manually
                    </p>
                    <code className="block text-xs font-mono bg-slate-50 border border-[#E1E6ED] p-2 rounded-sm text-[var(--ink)]" data-testid="mfa-secret">
                      {setup.secret}
                    </code>
                  </div>
                  <form onSubmit={verify} className="space-y-3">
                    <div className="space-y-2">
                      <Label className="text-xs uppercase tracking-wider text-slate-500 font-semibold">
                        6-digit code from your app
                      </Label>
                      <Input
                        inputMode="numeric" pattern="[0-9]{6}" maxLength={6}
                        required value={code}
                        onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
                        className="rounded-sm h-10 font-mono tracking-widest"
                        placeholder="123456"
                        data-testid="mfa-code-input"
                      />
                    </div>
                    <div className="flex gap-2">
                      <Button type="submit" disabled={busy || code.length !== 6} className="bg-[var(--ink)] hover:bg-[#0E2958] rounded-sm h-9" data-testid="verify-mfa-btn">
                        {busy ? "Verifying…" : "Verify & enable"}
                      </Button>
                      <Button type="button" variant="ghost" className="rounded-sm h-9" onClick={() => setSetup(null)} data-testid="cancel-mfa-btn">
                        Cancel
                      </Button>
                    </div>
                  </form>
                </div>
              </div>
            )}
          </div>
        </section>

        {/* Phase X (2026-02 fork-resume) — Danger Zone */}
        <section className="bg-white border border-red-200 rounded-sm mt-8" data-testid="account-danger-zone">
          <div className="px-6 py-4 border-b border-red-100 flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-red-700 flex items-center gap-2">
                <AlertTriangle className="w-4 h-4" /> Danger zone
              </p>
              <p className="text-xs text-slate-500 mt-1">
                Delete your account and all linked data. There is a 30-day cancellation window.
              </p>
            </div>
            {account?.status === "pending_deletion" && (
              <span className="text-[10px] uppercase tracking-wider px-2 py-1 rounded-sm bg-red-50 text-red-700 border border-red-200" data-testid="account-pending-deletion-badge">
                Scheduled
              </span>
            )}
          </div>
          <div className="p-6 space-y-4">
            {account?.status === "pending_deletion" ? (
              <div className="space-y-3" data-testid="account-pending-deletion-state">
                <p className="text-sm text-[var(--ink)]">
                  Your account is scheduled for permanent deletion on{" "}
                  <strong data-testid="account-deletion-scheduled-for">
                    {account.deletion_scheduled_for
                      ? new Date(account.deletion_scheduled_for).toLocaleDateString()
                      : "—"}
                  </strong>.
                </p>
                <p className="text-xs text-slate-500">
                  Cancel anytime before that date. After it, all data is irrecoverable.
                </p>
                <Button
                  variant="outline"
                  className="border-[var(--ink)] text-[var(--ink)] hover:bg-slate-50 rounded-sm h-9"
                  onClick={cancelDeletion}
                  disabled={deletionBusy}
                  data-testid="cancel-account-deletion-btn"
                >
                  {deletionBusy ? "Working…" : "Cancel deletion"}
                </Button>
              </div>
            ) : (
              <Button
                variant="outline"
                className="border-red-500 text-red-600 hover:bg-red-50 rounded-sm h-9"
                onClick={() => setDangerOpen(true)}
                data-testid="open-delete-account-btn"
              >
                <Trash2 className="w-3.5 h-3.5 mr-1.5" />
                Delete my account
              </Button>
            )}
          </div>
        </section>

        {/* Delete confirm dialog */}
        <Dialog open={dangerOpen} onOpenChange={(o) => !o && setDangerOpen(false)}>
          <DialogContent data-testid="delete-account-dialog">
            <DialogHeader>
              <DialogTitle>Delete your account</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 text-sm">
              <p className="text-[var(--ink)]">
                This schedules permanent deletion of your account and every linked
                context, document, task, and signal. You have <strong>30 days</strong> to
                cancel before the data is irrecoverable.
              </p>
              <div className="space-y-2">
                <Label className="text-xs uppercase tracking-wider text-slate-500 font-semibold">
                  Type your email to confirm
                </Label>
                <Input
                  value={confirmEmail}
                  onChange={(e) => setConfirmEmail(e.target.value)}
                  placeholder={account?.email}
                  className="rounded-sm h-10"
                  data-testid="delete-account-confirm-input"
                />
              </div>
            </div>
            <DialogFooter>
              <Button variant="ghost" onClick={() => setDangerOpen(false)} disabled={deletionBusy} data-testid="delete-account-cancel-btn">
                Cancel
              </Button>
              <Button
                variant="destructive"
                onClick={requestDeletion}
                disabled={deletionBusy || (confirmEmail || "").trim().toLowerCase() !== (account?.email || "").trim().toLowerCase()}
                data-testid="delete-account-confirm-btn"
              >
                {deletionBusy ? "Scheduling…" : "Schedule deletion"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </AppShell>
  );
}
