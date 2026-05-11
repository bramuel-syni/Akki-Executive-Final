import React, { useState } from "react";
import WebsiteShell from "../WebsiteShell";
import "../style.css";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || "";

export default function ContactPage() {
  const [form, setForm] = useState({
    name: "", work_email: "", company: "", message: "",
  });
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(null);
  const [err, setErr] = useState(null);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true); setErr(null);
    try {
      const r = await fetch(`${BACKEND_URL}/api/website/contact`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      const data = await r.json();
      if (!r.ok) setErr(data?.detail?.message || "Could not submit.");
      else setDone(data.submission_id || "received");
    } catch {
      setErr("Network error.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <WebsiteShell
      title="Contact — Akki"
      description="Get in touch with the Akki team."
      pathname="/contact"
    >
      <section className="website-section website-section--narrow">
        <span className="website-label">Contact</span>
        <h1>Get in touch.</h1>
        <span className="website-rule" />
        <p style={{ fontSize: 18, color: "#6B6B6B", marginBottom: 28 }}>
          For partnerships, press, or product feedback. We read everything that comes in.
        </p>
        {done ? (
          <div data-testid="contact-form-done" style={{ padding: 24, background: "#FAF7F2", border: "1px solid #D5C9B6" }}>
            <h3>Message received.</h3>
            <p>We'll reply to your work email. Reference: {String(done).slice(0, 8)}</p>
          </div>
        ) : (
          <form onSubmit={submit} data-testid="contact-form">
            <div className="website-form-row">
              <div>
                <label className="website-label-block">Name *</label>
                <input className="website-input" required value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })} data-testid="contact-name" />
              </div>
              <div>
                <label className="website-label-block">Email *</label>
                <input className="website-input" type="email" required value={form.work_email}
                  onChange={(e) => setForm({ ...form, work_email: e.target.value })} data-testid="contact-email" />
              </div>
            </div>
            <div style={{ marginBottom: 16 }}>
              <label className="website-label-block">Company</label>
              <input className="website-input" value={form.company}
                onChange={(e) => setForm({ ...form, company: e.target.value })} data-testid="contact-company" />
            </div>
            <div style={{ marginBottom: 24 }}>
              <label className="website-label-block">Message *</label>
              <textarea className="website-textarea" required rows={6} value={form.message}
                onChange={(e) => setForm({ ...form, message: e.target.value })} data-testid="contact-message" />
            </div>
            {err && <p style={{ color: "#8B2E2B", fontSize: 14, marginBottom: 16 }}>{err}</p>}
            <button type="submit" disabled={busy} className="website-cta-primary"
              style={{ border: "none", cursor: busy ? "wait" : "pointer", opacity: busy ? 0.6 : 1 }}
              data-testid="contact-submit">
              {busy ? "Sending…" : "Send"}
            </button>
          </form>
        )}
      </section>
    </WebsiteShell>
  );
}
