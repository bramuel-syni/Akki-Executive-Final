import React, { useState } from "react";
import WebsiteShell from "../WebsiteShell";
import { COHORT } from "../copy";
import "../style.css";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || "";

const ROLE_TYPES = ["Executive", "NED", "Dual", "Operating Executive", "Investor", "Other"];

export default function CohortPage() {
  const [form, setForm] = useState({
    first_name: "", last_name: "", work_email: "",
    company: "", role_title: "", role_type: "",
    linkedin_url: "", valuable_text: "",
    cohort_understood: false,
  });
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(null);
  const [err, setErr] = useState(null);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true); setErr(null);
    try {
      const r = await fetch(`${BACKEND_URL}/api/website/early-access`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      const data = await r.json();
      if (!r.ok) {
        setErr(data?.detail?.message || "Could not submit. Please try again.");
      } else {
        setDone(data.submission_id || "received");
      }
    } catch {
      setErr("Network error. Please try again.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <WebsiteShell
      title="Founding cohort — Akki"
      description="Apply to join the Akki founding cohort. Honest feedback in exchange for early-access pricing locked for life."
      pathname="/cohort"
    >
      <section className="website-section website-section--narrow">
        <span className="website-label">Founding cohort</span>
        <h1>{COHORT.headline}</h1>
        <span className="website-rule" />
        <p>{COHORT.body}</p>
        {done ? (
          <div data-testid="cohort-form-done" style={{ marginTop: 32, padding: 24, background: "#EDE7D6", border: "1px solid #D8D2C5" }}>
            <h3>Application received.</h3>
            <p>Thank you. We've sent a confirmation to your work email and someone from the founding team will be in touch within a few business days.</p>
            <p style={{ fontSize: 13, color: "#6B7480" }}>Reference: {String(done).slice(0, 8)}</p>
          </div>
        ) : (
          <form onSubmit={submit} style={{ marginTop: 32 }} data-testid="cohort-form">
            <p style={{ fontSize: 16, color: "#6B7480", marginBottom: 28 }}>{COHORT.formIntro}</p>
            <div className="website-form-row">
              <div>
                <label className="website-label-block">First name *</label>
                <input className="website-input" required value={form.first_name}
                  onChange={(e) => setForm({ ...form, first_name: e.target.value })} data-testid="cohort-first-name" />
              </div>
              <div>
                <label className="website-label-block">Last name *</label>
                <input className="website-input" required value={form.last_name}
                  onChange={(e) => setForm({ ...form, last_name: e.target.value })} data-testid="cohort-last-name" />
              </div>
            </div>
            <div className="website-form-row">
              <div>
                <label className="website-label-block">Work email *</label>
                <input className="website-input" type="email" required value={form.work_email}
                  onChange={(e) => setForm({ ...form, work_email: e.target.value })} data-testid="cohort-email" />
              </div>
              <div>
                <label className="website-label-block">Company *</label>
                <input className="website-input" required value={form.company}
                  onChange={(e) => setForm({ ...form, company: e.target.value })} data-testid="cohort-company" />
              </div>
            </div>
            <div className="website-form-row">
              <div>
                <label className="website-label-block">Role / title *</label>
                <input className="website-input" required value={form.role_title}
                  onChange={(e) => setForm({ ...form, role_title: e.target.value })} data-testid="cohort-role-title" />
              </div>
              <div>
                <label className="website-label-block">Role type *</label>
                <select className="website-select" required value={form.role_type}
                  onChange={(e) => setForm({ ...form, role_type: e.target.value })} data-testid="cohort-role-type">
                  <option value="">Select…</option>
                  {ROLE_TYPES.map((r) => <option key={r} value={r}>{r}</option>)}
                </select>
              </div>
            </div>
            <div style={{ marginBottom: 16 }}>
              <label className="website-label-block">LinkedIn URL (optional)</label>
              <input className="website-input" type="url" value={form.linkedin_url}
                onChange={(e) => setForm({ ...form, linkedin_url: e.target.value })} data-testid="cohort-linkedin" />
            </div>
            <div style={{ marginBottom: 16 }}>
              <label className="website-label-block">What would Akki need to do for you to call it valuable? (optional)</label>
              <textarea className="website-textarea" rows={4} value={form.valuable_text}
                onChange={(e) => setForm({ ...form, valuable_text: e.target.value })} data-testid="cohort-valuable" />
            </div>
            <label style={{ display: "flex", alignItems: "flex-start", gap: 10, marginBottom: 24, fontSize: 14, color: "#0F1419" }}>
              <input type="checkbox" required style={{ marginTop: 4 }}
                checked={form.cohort_understood}
                onChange={(e) => setForm({ ...form, cohort_understood: e.target.checked })}
                data-testid="cohort-consent" />
              <span>I understand the founding cohort is a small group providing feedback in exchange for early-access pricing.</span>
            </label>
            {err && <p style={{ color: "#8B2E2E", fontSize: 14, marginBottom: 16 }} data-testid="cohort-form-error">{err}</p>}
            <button type="submit" disabled={busy} className="website-cta-primary"
              style={{ border: "none", cursor: busy ? "wait" : "pointer", opacity: busy ? 0.6 : 1 }}
              data-testid="cohort-submit">
              {busy ? "Submitting…" : "Submit application"}
            </button>
          </form>
        )}
      </section>
    </WebsiteShell>
  );
}
