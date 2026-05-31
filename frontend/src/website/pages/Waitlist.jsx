/**
 * Phase P5.7.6 (2026-02) — Waitlist door-back page.
 *
 * /waitlist — public, single email field. Voice-clean copy.
 * Posts to POST /api/cohort/waitlist with CSRF token. The endpoint
 * is idempotent on email_lc, so re-submitting the same address is
 * treated as success ("you're on the list").
 *
 * The decline email body (also P5.7.6) carries the canonical URL
 * https://akki.syni.ai/waitlist?from={application_id}; the
 * `from` query param is forwarded as `source_application_id` for
 * analytics correlation.
 */
import React, { useState, useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import axios from "axios";
import WebsiteShell from "../WebsiteShell";
import { api, resolveApiUrl } from "@/lib/api";

export default function Waitlist() {
  const [params] = useSearchParams();
  const sourceApplicationId = useMemo(
    () => (params.get("from") || "").slice(0, 64) || null,
    [params],
  );
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    if (!email.trim() || busy) return;
    setBusy(true);
    setError("");
    try {
      // Mint a CSRF token first (idempotent — the /api/csrf endpoint
      // returns the existing one if the cookie is already present).
      const csrfRes = await axios.get(resolveApiUrl("/csrf"), {
        withCredentials: true,
      });
      const csrf = csrfRes?.data?.csrf_token;
      await api.post(
        "/cohort/waitlist",
        {
          email: email.trim(),
          source_application_id: sourceApplicationId,
        },
        { headers: csrf ? { "X-CSRF-Token": csrf } : {} },
      );
      setSubmitted(true);
    } catch (err) {
      const code = err?.response?.data?.detail?.code;
      const msg = err?.response?.data?.detail?.message;
      if (code === "rate_limit_ip") {
        setError(msg || "Too many signups from this network. Try again in an hour.");
      } else if (code === "email_invalid") {
        setError(msg || "That email looks malformed.");
      } else {
        setError("Something went wrong. Try again in a moment.");
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <WebsiteShell
      title="Waitlist — Akki for Executives"
      description="Drop your email and we'll write the moment we can take a fresh round of readers."
      pathname="/waitlist"
    >
      <section className="waitlist-page" data-testid="waitlist-page">
        <div className="waitlist-container">
          <h1 className="waitlist-heading" data-testid="waitlist-heading">
            The list, not a launch.
          </h1>
          <p className="waitlist-dek" data-testid="waitlist-dek">
            Akki opens new seats every few months. Drop your email and we'll
            write the moment we can take a fresh round of readers. No marketing,
            no list churn — just one personal note when the door opens.
          </p>
          {submitted ? (
            <div
              className="waitlist-success"
              role="status"
              data-testid="waitlist-success"
            >
              <p className="waitlist-success-line">You're on the list.</p>
              <p className="waitlist-success-sub">
                When the next cohort opens, we'll write to the address you
                just gave us. Nothing in the meantime.
              </p>
              <p className="waitlist-signoff">— Akki</p>
            </div>
          ) : (
            <form
              className="waitlist-form"
              onSubmit={submit}
              data-testid="waitlist-form"
            >
              <label htmlFor="waitlist-email" className="waitlist-label">
                Email
              </label>
              <input
                id="waitlist-email"
                type="email"
                inputMode="email"
                required
                autoComplete="email"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="waitlist-input"
                data-testid="waitlist-email-input"
                disabled={busy}
              />
              {error && (
                <p
                  className="waitlist-error"
                  role="alert"
                  data-testid="waitlist-error"
                >
                  {error}
                </p>
              )}
              <button
                type="submit"
                disabled={busy || !email.trim()}
                className="waitlist-submit"
                data-testid="waitlist-submit"
              >
                {busy ? "Adding you..." : "Add me to the list"}
              </button>
            </form>
          )}
        </div>
      </section>
    </WebsiteShell>
  );
}
