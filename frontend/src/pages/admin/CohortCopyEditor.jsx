/**
 * Phase R.5.b (2026-05-27) — Founder copy editor.
 *
 * Superadmin-gated page that surfaces all 5 founder-fillable copy
 * slots in one place. The founder edits each slot, saves, and the
 * existing R.2 / R.4 / R.5.a consumers consult the override
 * automatically on next render / send.
 *
 * Slot schema is delivered by the backend GET /api/admin/cohort/copy
 * so adding fields later requires zero frontend change.
 *
 * Save guard: server returns 422 with the locked
 * `founder_placeholder_present` code + per-field `dirty_fields[]`
 * windows. We render the dirty fields inline as a banner above the
 * affected slot. The editor mirrors the validation client-side too
 * so the save button disables BEFORE the founder hits 422.
 */
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { api, apiErrorMessage } from "@/lib/api";
import { toast } from "sonner";
import { Save, AlertCircle, CheckCircle2, Loader2 } from "lucide-react";

const SLOT_TITLES = {
  welcome_email:       "Welcome email (R.2)",
  feedback_thanks:     "Feedback auto-thanks (R.4)",
  day_16_banner:       "Day-16 soft-warning banner",
  early_access_opt_in: "Day-22 early-access page",
  special_ask:         "Special-ask (referral / case-study / testimonial)",
};

const SLOT_DESCRIPTIONS = {
  welcome_email:
    "Sent on cohort invite. Fill in your voice — the [FOUNDER:] guard blocks real sends until you do.",
  feedback_thanks:
    "Sent automatically after a user submits feedback. Acknowledge warmly + mention you read every reply.",
  day_16_banner:
    "Renders in-app on day 16-21. Soft warning before the day-22 hard cutoff.",
  early_access_opt_in:
    "The hard-cutoff page (day 22+). Only route a locked user can reach.",
  special_ask:
    "Day-14 trigger — referral / case study / testimonial ask. Shown in-app + emailed.",
};

const FIELD_LABELS = {
  subject:        "Subject line",
  html:           "Email body (HTML)",
  text:           "Email body (plaintext fallback)",
  heading:        "Heading",
  body:           "Body",
  thanks_body:    "Thanks-state body (after submit)",
  signoff:        "Sign-off line",
  modal_heading:  "Modal heading",
  modal_body:     "Modal body",
  email_subject:  "Email subject",
  email_body:     "Email body",
};

const FOUNDER_PLACEHOLDER_PREFIX = "[FOUNDER:";

function containsPlaceholder(s) {
  return typeof s === "string" && s.includes(FOUNDER_PLACEHOLDER_PREFIX);
}

function SlotEditor({ slot, fields, initialValues, updatedAt, onSaved }) {
  const [values, setValues] = useState(() =>
    Object.fromEntries(fields.map((f) => [f, initialValues?.[f] || ""])),
  );
  const [saving, setSaving] = useState(false);
  const [serverErrors, setServerErrors] = useState(null);

  // Local validation mirrors the server's 422 guard.
  const dirtyFields = useMemo(() =>
    fields.filter((f) => containsPlaceholder(values[f])),
  [fields, values]);

  const handleSave = useCallback(async () => {
    if (dirtyFields.length > 0 || saving) return;
    setSaving(true);
    setServerErrors(null);
    try {
      const res = await api.put(`/admin/cohort/copy/${slot}`, { fields: values });
      toast.success(`${SLOT_TITLES[slot]} saved.`);
      onSaved?.(slot, res.data);
    } catch (err) {
      const detail = err?.response?.data?.detail;
      if (detail?.code === "founder_placeholder_present") {
        setServerErrors(detail.dirty_fields || []);
        toast.error("Server rejected: still has [FOUNDER:] placeholders.");
      } else {
        toast.error(apiErrorMessage(err) || "Save failed.");
      }
    } finally {
      setSaving(false);
    }
  }, [dirtyFields.length, saving, slot, values, onSaved]);

  return (
    <section
      data-testid={`copy-editor-slot-${slot}`}
      className="border border-[var(--line)] bg-white p-5 rounded-sm mb-5"
    >
      <header className="flex items-baseline justify-between gap-3 mb-1">
        <h2 className="akki-serif text-[20px] text-[var(--ink)]">
          {SLOT_TITLES[slot] || slot}
        </h2>
        {updatedAt && (
          <p className="font-mono text-[10.5px] text-[var(--muted)]">
            updated {new Date(updatedAt).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" })}
          </p>
        )}
      </header>
      <p className="text-[12.5px] text-[var(--muted)] mb-4">{SLOT_DESCRIPTIONS[slot]}</p>

      <div className="flex flex-col gap-3">
        {fields.map((field) => {
          const value = values[field] || "";
          const dirty = containsPlaceholder(value);
          const serverDirty = serverErrors?.find((e) => e.field === field);
          return (
            <div key={field} className="flex flex-col gap-1.5">
              <label
                className="text-[12px] font-medium text-[var(--deep)]"
                htmlFor={`copy-${slot}-${field}`}
              >
                {FIELD_LABELS[field] || field}
              </label>
              <textarea
                id={`copy-${slot}-${field}`}
                data-testid={`copy-editor-field-${slot}-${field}`}
                value={value}
                onChange={(e) => setValues((v) => ({ ...v, [field]: e.target.value }))}
                rows={field === "subject" || field === "heading" || field === "modal_heading" ? 1 : 6}
                className={`w-full text-[12.5px] text-[var(--ink)] border rounded-sm p-2 font-mono focus:outline-none focus:ring-1 focus:ring-[var(--accent)] ${
                  dirty || serverDirty ? "border-[#7A2F2F]" : "border-[var(--line)]"
                }`}
              />
              {(dirty || serverDirty) && (
                <p
                  data-testid={`copy-editor-error-${slot}-${field}`}
                  className="text-[11px] text-[#7A2F2F] inline-flex items-center gap-1"
                >
                  <AlertCircle className="w-3 h-3" aria-hidden />
                  {serverDirty
                    ? `Server: [FOUNDER:] still here — ${serverDirty.window.slice(0, 50)}…`
                    : "Contains [FOUNDER:] — can’t save while present"}
                </p>
              )}
            </div>
          );
        })}
      </div>

      <div className="flex items-center justify-end gap-3 mt-4">
        {dirtyFields.length > 0 && (
          <span className="text-[11px] text-[var(--muted)]">
            {dirtyFields.length} field{dirtyFields.length === 1 ? "" : "s"} need editing
          </span>
        )}
        <button
          type="button"
          data-testid={`copy-editor-save-${slot}`}
          onClick={handleSave}
          disabled={dirtyFields.length > 0 || saving}
          className="inline-flex items-center gap-2 px-4 py-1.5 text-[12px] font-medium rounded-sm bg-[var(--ink)] text-[var(--cream)] disabled:opacity-40 disabled:cursor-not-allowed hover:opacity-90 transition-opacity"
        >
          {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
          {saving ? "Saving…" : "Save"}
        </button>
      </div>
    </section>
  );
}

export default function CohortCopyEditor() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get("/admin/cohort/copy");
      setData(res?.data || null);
    } catch (err) {
      toast.error(apiErrorMessage(err) || "Could not load copy slots.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleSaved = useCallback((slot, payload) => {
    setData((d) => {
      if (!d) return d;
      return {
        ...d,
        slots: {
          ...d.slots,
          [slot]: {
            ...d.slots[slot],
            values:     payload?.fields || d.slots[slot].values,
            updated_at: payload?.updated_at || d.slots[slot].updated_at,
          },
        },
      };
    });
  }, []);

  const knownSlots = data?.known_slots || [];

  return (
    <div data-testid="cohort-copy-editor-page" className="min-h-screen bg-[var(--cream)] px-6 py-8">
      <div className="max-w-3xl mx-auto">
        <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-[var(--muted)] mb-2">
          Superadmin · founding cohort · copy editor
        </p>
        <h1 className="akki-serif text-[36px] leading-tight text-[var(--ink)] mb-2">
          Edit the founder-voice copy.
        </h1>
        <p
          className="akki-serif italic text-[14px] text-[var(--deep)] mb-8"
          data-testid="page-subtext"
        >
          Replace every <code className="font-mono text-[12px] text-[#7A2F2F]">[FOUNDER:&nbsp;…]</code> placeholder with your own words. The trial can't run until these are clean.
        </p>

        {loading && !data && (
          <p className="text-[13px] text-[var(--muted)] inline-flex items-center gap-2">
            <Loader2 className="w-4 h-4 animate-spin" /> Loading…
          </p>
        )}

        {data && knownSlots.map((slot) => {
          const info = data.slots[slot];
          if (!info) return null;
          return (
            <SlotEditor
              key={slot}
              slot={slot}
              fields={info.fields}
              initialValues={info.values}
              updatedAt={info.updated_at}
              onSaved={handleSaved}
            />
          );
        })}

        <p className="text-[11px] text-[var(--muted)] mt-6 font-mono">
          5 slots · changes go live immediately · no review queue
        </p>
      </div>
    </div>
  );
}
