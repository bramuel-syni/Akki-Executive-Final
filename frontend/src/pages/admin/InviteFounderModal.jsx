/**
 * Phase R.1.followup (2026-02 fork-resume) — Invite Founder modal.
 *
 * Renders the "Invite founder" CTA + a modal that POSTs to
 * /api/admin/cohort/invites. Used by CohortConsole top-right.
 *
 * Backend route is already wired (see backend/routers/admin_cohort.py
 * `issue_invite`). This component only handles the UI.
 *
 * Props:
 *   open               (bool)   — controlled open state
 *   onOpenChange       (fn)     — controlled open setter
 *   existingCohortTags ([str])  — autocomplete list (deduped from the
 *                                 console's invite rows)
 *   onInvited          (fn)     — invoked after a successful invite so
 *                                 the parent can refresh the table
 */
import React, { useEffect, useState } from "react";
import { api, apiErrorMessage } from "@/lib/api";
import { toast } from "sonner";
import { UserPlus, Loader2, AlertCircle } from "lucide-react";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function InviteFounderModal({
  open,
  onOpenChange,
  existingCohortTags = [],
  onInvited,
}) {
  const [email, setEmail] = useState("");
  const [firstName, setFirstName] = useState("");
  const [cohortTag, setCohortTag] = useState("");
  const [newTagMode, setNewTagMode] = useState(false);
  const [trialDays, setTrialDays] = useState(14);
  const [busy, setBusy] = useState(false);
  const [emailErr, setEmailErr] = useState("");

  // Reset on open
  useEffect(() => {
    if (open) {
      setEmail(""); setFirstName(""); setCohortTag("");
      setNewTagMode(false); setTrialDays(14);
      setEmailErr(""); setBusy(false);
    }
  }, [open]);

  const validate = () => {
    if (!email.trim()) { setEmailErr("Email is required."); return false; }
    if (!EMAIL_RE.test(email.trim())) { setEmailErr("Invalid email."); return false; }
    if (!cohortTag.trim()) { setEmailErr("Cohort tag is required."); return false; }
    if (trialDays < 7 || trialDays > 30) { setEmailErr("Trial days must be 7–30."); return false; }
    setEmailErr("");
    return true;
  };

  const submit = async () => {
    if (!validate()) return;
    setBusy(true);
    try {
      const payload = {
        email:               email.trim().toLowerCase(),
        cohort_tag:          cohortTag.trim(),
        trial_length_days:   trialDays,
        first_name:          firstName.trim() || undefined,
      };
      const { data } = await api.post("/admin/cohort/invites", payload);

      if (data?.welcome_email_dispatched) {
        toast.success(`Invite sent to ${payload.email}.`);
      } else {
        toast.warning(`Invite created for ${payload.email} but the welcome email did not dispatch. Retry from the row.`);
      }
      onOpenChange(false);
      if (typeof onInvited === "function") onInvited(data);
    } catch (e) {
      const msg = apiErrorMessage(e);
      // Inline-surface common errors.
      if (/already/i.test(msg) || e?.response?.status === 409) {
        setEmailErr(msg || "This email has already been invited.");
      } else if (e?.response?.status === 400 || e?.response?.status === 422) {
        setEmailErr(msg);
      } else {
        toast.error(msg);
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg" data-testid="invite-founder-modal">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <UserPlus className="w-4 h-4 text-[var(--ned-purple)]" /> Invite founder
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label className="text-[11px] uppercase tracking-[0.14em] text-[var(--muted)]">Email</Label>
            <Input
              value={email}
              onChange={(e) => { setEmail(e.target.value); setEmailErr(""); }}
              placeholder="founder@example.com"
              type="email"
              className="rounded-sm h-10"
              data-testid="invite-founder-email-input"
              autoFocus
            />
            {emailErr && (
              <p className="text-[11px] text-rose-600 flex items-center gap-1" data-testid="invite-founder-inline-error">
                <AlertCircle className="w-3 h-3" /> {emailErr}
              </p>
            )}
          </div>

          <div className="space-y-1.5">
            <Label className="text-[11px] uppercase tracking-[0.14em] text-[var(--muted)]">
              Display name <span className="lowercase text-[10px]">(optional)</span>
            </Label>
            <Input
              value={firstName}
              onChange={(e) => setFirstName(e.target.value)}
              placeholder="First name"
              className="rounded-sm h-10"
              data-testid="invite-founder-firstname-input"
            />
          </div>

          <div className="space-y-1.5">
            <Label className="text-[11px] uppercase tracking-[0.14em] text-[var(--muted)]">Cohort tag</Label>
            {newTagMode ? (
              <div className="flex gap-2">
                <Input
                  value={cohortTag}
                  onChange={(e) => setCohortTag(e.target.value)}
                  placeholder="e.g. spring-2026"
                  className="rounded-sm h-10"
                  data-testid="invite-founder-new-tag-input"
                />
                <Button
                  variant="ghost"
                  className="h-10 px-3 text-[11px]"
                  onClick={() => { setNewTagMode(false); setCohortTag(""); }}
                  type="button"
                  data-testid="invite-founder-cancel-new-tag"
                >
                  ← back
                </Button>
              </div>
            ) : (
              <select
                value={cohortTag}
                onChange={(e) => {
                  if (e.target.value === "__new__") {
                    setNewTagMode(true);
                    setCohortTag("");
                  } else {
                    setCohortTag(e.target.value);
                  }
                }}
                className="w-full h-10 px-3 text-[13px] bg-white border border-[var(--line)] rounded-sm focus:outline-none focus:ring-1 focus:ring-[var(--accent)]"
                data-testid="invite-founder-tag-select"
              >
                <option value="">Select tag…</option>
                {existingCohortTags.map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
                <option value="__new__">+ New tag…</option>
              </select>
            )}
          </div>

          <div className="space-y-1.5">
            <Label className="text-[11px] uppercase tracking-[0.14em] text-[var(--muted)]">
              Trial length (days)
            </Label>
            <Input
              type="number"
              min={7}
              max={30}
              value={trialDays}
              onChange={(e) => setTrialDays(parseInt(e.target.value || "14", 10))}
              className="rounded-sm h-10 w-32"
              data-testid="invite-founder-trial-days-input"
            />
            <p className="text-[10.5px] text-[var(--muted)]">Range 7–30. Default 14.</p>
          </div>
        </div>

        <DialogFooter>
          <Button
            variant="ghost"
            onClick={() => onOpenChange(false)}
            disabled={busy}
            data-testid="invite-founder-cancel-btn"
          >
            Cancel
          </Button>
          <Button
            onClick={submit}
            disabled={busy}
            className="bg-[var(--ned-purple)] text-white hover:bg-[var(--ned-purple)]/90"
            data-testid="invite-founder-submit-btn"
          >
            {busy
              ? (<><Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" /> Sending…</>)
              : "Send invite"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
