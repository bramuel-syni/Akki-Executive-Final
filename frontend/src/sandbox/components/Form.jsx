import React, { useState } from "react";
import { createSandboxSession } from "../api";

const ROLES = ["CEO", "NED", "CFO", "COO", "CRO", "Company Secretary", "Permanent Secretary", "Cabinet Secretary/Minister", "Other"];
const ORG_TYPES = ["Bank", "Healthcare", "Logistics", "Technology", "Government", "Regulator", "Manufacturing", "Other"];
const ORG_SIZES = ["<100", "100-1k", "1k-10k", ">10k"];
const EMPHASIS_OPTIONS = [
  "Structured thinking",
  "Cross-cutting insight",
  "Document drafted",
  "Visibility across cycle",
  "Understand refusal",
  "Something else",
];

/**
 * SandboxForm — paginated 4-screen form covering 7 questions. Progress
 * indicator at top. Submit lives on the final screen.
 */
export default function SandboxForm({ onSubmit }) {
  const [page, setPage] = useState(0);
  const [form, setForm] = useState({
    name: "", role: "", role_other: "",
    org_type: "", org_type_other: "", org_size: "",
    situation: "", emphasis: [], email: "",
  });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));
  const toggleEmphasis = (opt) => {
    setForm((f) => {
      const has = f.emphasis.includes(opt);
      if (has) return { ...f, emphasis: f.emphasis.filter((x) => x !== opt) };
      if (f.emphasis.length >= 3) return f;
      return { ...f, emphasis: [...f.emphasis, opt] };
    });
  };

  const canAdvance = () => {
    if (page === 0) return form.name.trim().length > 0 && form.role;
    if (page === 1) return form.org_type && form.org_size;
    if (page === 2) return true; // situation is optional
    return form.emphasis.length > 0;
  };

  const onSubmitForm = async (e) => {
    e?.preventDefault?.();
    if (busy) return;
    setErr(""); setBusy(true);
    try {
      const out = await createSandboxSession(form);
      onSubmit(out.session_id);
    } catch (ex) {
      setErr(String(ex.message || ex));
      setBusy(false);
    }
  };

  return (
    <form className="sb-shell" onSubmit={onSubmitForm} data-testid="sandbox-form">
      <span className="sb-label">Step {page + 1} of 4</span>
      <div className="sb-progress">
        {[0, 1, 2, 3].map((i) => (
          <span
            key={i}
            className={
              "sb-progress-pill " +
              (i < page ? "sb-progress-pill--done" : i === page ? "sb-progress-pill--active" : "")
            }
          />
        ))}
      </div>

      {page === 0 && (
        <div data-testid="sandbox-form-page-0">
          <h1 style={{ fontSize: 32 }}>Who are you?</h1>
          <div className="sb-field">
            <label className="sb-field-label" htmlFor="sb-name">Name</label>
            <input id="sb-name" className="sb-input" value={form.name}
              onChange={(e) => set("name", e.target.value)} maxLength={80}
              data-testid="sandbox-form-name" />
          </div>
          <div className="sb-field">
            <label className="sb-field-label">Role</label>
            <div className="sb-pick-list">
              {ROLES.map((r) => (
                <button type="button" key={r} className="sb-pick-button"
                  aria-pressed={form.role === r}
                  onClick={() => set("role", r)}
                  data-testid={`sandbox-form-role-${r.replace(/\s+/g, "-").replace(/\//g, "-")}`}>{r}</button>
              ))}
            </div>
            {form.role === "Other" && (
              <input className="sb-input" style={{ marginTop: 10 }}
                placeholder="Briefly describe your role"
                value={form.role_other} onChange={(e) => set("role_other", e.target.value)} maxLength={120} />
            )}
          </div>
        </div>
      )}

      {page === 1 && (
        <div data-testid="sandbox-form-page-1">
          <h1 style={{ fontSize: 32 }}>Where do you work?</h1>
          <div className="sb-field">
            <label className="sb-field-label">Organisation type</label>
            <div className="sb-pick-list">
              {ORG_TYPES.map((t) => (
                <button type="button" key={t} className="sb-pick-button"
                  aria-pressed={form.org_type === t}
                  onClick={() => set("org_type", t)}
                  data-testid={`sandbox-form-orgtype-${t.replace(/\s+/g, "-")}`}>{t}</button>
              ))}
            </div>
            {form.org_type === "Other" && (
              <input className="sb-input" style={{ marginTop: 10 }}
                placeholder="Briefly describe the organisation type"
                value={form.org_type_other} onChange={(e) => set("org_type_other", e.target.value)} maxLength={120} />
            )}
          </div>
          <div className="sb-field">
            <label className="sb-field-label">Organisation size</label>
            <div className="sb-pick-list">
              {ORG_SIZES.map((s) => (
                <button type="button" key={s} className="sb-pick-button"
                  aria-pressed={form.org_size === s}
                  onClick={() => set("org_size", s)}
                  data-testid={`sandbox-form-size-${s.replace(/[<>]/g, "")}`}>{s}</button>
              ))}
            </div>
          </div>
        </div>
      )}

      {page === 2 && (
        <div data-testid="sandbox-form-page-2">
          <h1 style={{ fontSize: 32 }}>The situation you would bring.</h1>
          <p style={{ color: "var(--sb-muted)" }}>
            Encouraged but not required. A real fragment of work helps Akki
            compose a session that feels like yours.
          </p>
          <div className="sb-field">
            <label className="sb-field-label" htmlFor="sb-situation">Brief description</label>
            <textarea id="sb-situation" className="sb-textarea" value={form.situation}
              onChange={(e) => set("situation", e.target.value)} maxLength={1500}
              placeholder="A regulatory consultation, a senior departure, an inconsistency in the pack …"
              data-testid="sandbox-form-situation" />
          </div>
        </div>
      )}

      {page === 3 && (
        <div data-testid="sandbox-form-page-3">
          <h1 style={{ fontSize: 32 }}>What would make this useful?</h1>
          <p style={{ color: "var(--sb-muted)" }}>Pick up to three. We use this to reorder the session.</p>
          <div className="sb-field">
            <div className="sb-pick-list">
              {EMPHASIS_OPTIONS.map((o) => (
                <button type="button" key={o} className="sb-pick-button"
                  aria-pressed={form.emphasis.includes(o)}
                  onClick={() => toggleEmphasis(o)}
                  data-testid={`sandbox-form-emphasis-${o.replace(/\s+/g, "-")}`}>{o}</button>
              ))}
            </div>
          </div>
          <div className="sb-field">
            <label className="sb-field-label" htmlFor="sb-email">Email (optional)</label>
            <input id="sb-email" className="sb-input" type="email" value={form.email}
              onChange={(e) => set("email", e.target.value)} maxLength={200}
              data-testid="sandbox-form-email" />
            <div className="sb-field-help">
              If you want a copy of what your session produced, leave your email.
              Otherwise the session lives only in this browser.
            </div>
          </div>
          {err && <p className="sb-error" data-testid="sandbox-form-error">{err}</p>}
        </div>
      )}

      <div style={{ display: "flex", justifyContent: "space-between", marginTop: 36 }}>
        {page > 0 ? (
          <button type="button" className="sb-cta-secondary"
            onClick={() => setPage((p) => p - 1)} data-testid="sandbox-form-back">Back</button>
        ) : <span />}
        {page < 3 ? (
          <button type="button" className="sb-cta-primary"
            disabled={!canAdvance()}
            onClick={() => setPage((p) => p + 1)} data-testid="sandbox-form-next">Continue</button>
        ) : (
          <button type="submit" className="sb-cta-primary"
            disabled={!canAdvance() || busy} data-testid="sandbox-form-submit">
            {busy ? "Composing your session…" : "Compose my session"}
          </button>
        )}
      </div>
    </form>
  );
}
