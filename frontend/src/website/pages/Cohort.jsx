/**
 * Website v7 — /cohort  (held 2026-02 dispatch 11).
 *
 * Page intent: pricing copy is removed pending product-packaging
 * decisions; the on-page form keeps lead capture live so we don't
 * lose applications during the holding window.
 *
 * Form submits to POST /api/cohort/applications (M.0c scaffold,
 * multi-recipient founder notify wired dispatch 10).
 */
import React, { useState } from "react";
import axios from "axios";
import WebsiteShell from "../WebsiteShell";
import { HeroWithLift, InvertedCtaSection } from "../components/PagePrimitives";
import { COHORT, INVERTED_CTA } from "../copy";

const API = process.env.REACT_APP_BACKEND_URL || "";
const FIELDS = [
  { id: "name",            label: "Name",                        required: true,  type: "text",     placeholder: "Full name" },
  { id: "email",           label: "Email",                       required: true,  type: "email",    placeholder: "you@organisation" },
  { id: "organisation",    label: "Organisation",                required: true,  type: "text",     placeholder: "Where you work" },
  { id: "role",            label: "Role",                        required: true,  type: "text",     placeholder: "CFO · NED · Chief of Staff" },
  { id: "use_case",        label: "Use case",                    required: true,  type: "textarea", placeholder: "How would you put Akki to work in the first month?" },
  { id: "referral_source", label: "Referral source (optional)",  required: false, type: "text",     placeholder: "Who pointed you here" },
];

export default function Cohort() {
  const [values, setValues] = useState(
    () => Object.fromEntries(FIELDS.map((f) => [f.id, ""])),
  );
  const [status, setStatus] = useState("idle"); // idle · submitting · sent · error
  const [error, setError] = useState(null);

  function set(field, v) {
    setValues((cur) => ({ ...cur, [field]: v }));
  }

  async function onSubmit(e) {
    e.preventDefault();
    setStatus("submitting");
    setError(null);
    try {
      const payload = Object.fromEntries(
        FIELDS.map((f) => [f.id, (values[f.id] || "").trim()]),
      );
      if (!payload.referral_source) payload.referral_source = null;
      const r = await axios.post(`${API}/api/cohort/applications`, payload);
      if (r.data?.deduplicated) {
        setStatus("sent");
        return;
      }
      setStatus("sent");
    } catch (err) {
      setError(
        err?.response?.data?.detail
          ? "Some fields need adjustment. Please check your entries and try again."
          : "Something interrupted the submission. Please try again in a moment.",
      );
      setStatus("error");
    }
  }

  return (
    <WebsiteShell
      title="Founding cohort — Akki"
      description="A small admitted cohort using Akki first. Register your interest while founding cohort pricing is being finalised."
      pathname="/cohort"
    >
      <HeroWithLift
        kicker={COHORT.kicker}
        headline={COHORT.headline}
        lift={COHORT.lift}
        dek={COHORT.dek}
        testId="cohort-page"
      />
      <section className="website-section--narrow section-reveal" data-testid="cohort-body">
        <p style={{ maxWidth: 70 + "ch", lineHeight: 1.7, color: "var(--graphite)" }}>{COHORT.body}</p>

        <p
          data-testid="cohort-holding-line"
          style={{
            maxWidth: 70 + "ch",
            marginTop: 24,
            paddingTop: 16,
            borderTop: "1px solid var(--cream-deep, #e3dccf)",
            color: "var(--ink)",
            fontStyle: "italic",
          }}
        >
          {COHORT.holding}
        </p>

        {status !== "sent" ? (
          <form
            onSubmit={onSubmit}
            data-testid="cohort-application-form"
            style={{ display: "grid", gap: 16, maxWidth: 560, marginTop: 24 }}
          >
            {FIELDS.map((f) => (
              <label key={f.id} style={{ display: "grid", gap: 6 }}>
                <span style={{ fontSize: 13, color: "var(--graphite)" }}>{f.label}</span>
                {f.type === "textarea" ? (
                  <textarea
                    data-testid={`cohort-field-${f.id}`}
                    required={f.required}
                    value={values[f.id]}
                    onChange={(e) => set(f.id, e.target.value)}
                    placeholder={f.placeholder}
                    rows={4}
                    style={{
                      padding: "10px 12px",
                      border: "1px solid var(--cream-deep, #d8d2c3)",
                      borderRadius: 4,
                      fontFamily: "inherit",
                      fontSize: 14,
                      background: "var(--cream, #f5efe0)",
                      resize: "vertical",
                    }}
                  />
                ) : (
                  <input
                    data-testid={`cohort-field-${f.id}`}
                    required={f.required}
                    type={f.type}
                    value={values[f.id]}
                    onChange={(e) => set(f.id, e.target.value)}
                    placeholder={f.placeholder}
                    style={{
                      padding: "10px 12px",
                      border: "1px solid var(--cream-deep, #d8d2c3)",
                      borderRadius: 4,
                      fontFamily: "inherit",
                      fontSize: 14,
                      background: "var(--cream, #f5efe0)",
                    }}
                  />
                )}
              </label>
            ))}
            <button
              type="submit"
              data-testid="cohort-submit"
              disabled={status === "submitting"}
              className="btn-primary btn-hero"
              style={{ width: "fit-content" }}
            >
              {status === "submitting" ? "Submitting…" : "Register interest"}
            </button>
            {error && (
              <p
                data-testid="cohort-error"
                style={{ color: "var(--oxblood, #6f2a2a)", fontSize: 13 }}
                role="alert"
              >
                {error}
              </p>
            )}
          </form>
        ) : (
          <p
            data-testid="cohort-success"
            style={{
              maxWidth: 70 + "ch",
              marginTop: 24,
              padding: 16,
              background: "var(--cream, #f5efe0)",
              borderLeft: "3px solid var(--ned-purple, #5a3a82)",
              color: "var(--ink)",
            }}
          >
            Thank you. We have your interest on file. We will share the
            offer with members before launch.
          </p>
        )}
      </section>
      <InvertedCtaSection
        kicker={INVERTED_CTA.kicker}
        headline="Try Akki before you apply."
        body="The sandbox shows the workspace in motion. No data is retained."
        ctaLabel="Begin sandbox" ctaHref="/sandbox" meta={INVERTED_CTA.meta}
        testId="cohort-inverted-cta"
      />
    </WebsiteShell>
  );
}
