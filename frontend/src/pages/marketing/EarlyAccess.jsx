/**
 * Early access registration form. POSTs to /api/early-access/register.
 * Public, no auth. Returns 201 on success and shows a thank-you state.
 */
import React, { useState } from "react";
import MarketingShell from "@/components/marketing/MarketingShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { ArrowRight, Loader2, Check } from "lucide-react";

const API_BASE = `${process.env.REACT_APP_BACKEND_URL}/api`;

const ROLES = [
  { value: "executive", label: "Executive" },
  { value: "ned", label: "NED" },
  { value: "chair", label: "Chair" },
  { value: "other", label: "Other" },
];

export default function EarlyAccess() {
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [company, setCompany] = useState("");
  const [role, setRole] = useState("");
  const [boardCount, setBoardCount] = useState("");
  const [message, setMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState("");

  const onSubmit = async (e) => {
    e.preventDefault();
    if (!email.trim() || submitting) return;
    setSubmitting(true);
    setError("");
    try {
      const r = await fetch(`${API_BASE}/early-access/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: email.trim(),
          full_name: fullName.trim() || null,
          company: company.trim() || null,
          role: role || null,
          board_count: boardCount === "" ? null : Number(boardCount),
          message: message.trim() || null,
        }),
      });
      if (r.status === 201 || r.status === 200) {
        setSubmitted(true);
      } else if (r.status === 429) {
        setError("You have made several requests already. Please try again in an hour.");
      } else {
        const data = await r.json().catch(() => ({}));
        const detail = data?.detail;
        const msg =
          typeof detail === "string"
            ? detail
            : Array.isArray(detail) && detail[0]?.msg
              ? detail[0].msg
              : "We could not register your request. Please check your details and try again.";
        setError(msg);
      }
    } catch (err) {
      setError("We could not reach the server. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  if (submitted) {
    return (
      <MarketingShell>
        <section
          className="max-w-[680px] mx-auto px-6 lg:px-10 py-24 md:py-32 text-center"
          data-testid="early-access-thanks"
        >
          <div className="w-12 h-12 rounded-full bg-[var(--accent)]/10 flex items-center justify-center mx-auto mb-6">
            <Check className="w-5 h-5 text-[var(--accent)]" strokeWidth={2} />
          </div>
          <h1 className="akki-serif text-[32px] md:text-[40px] leading-[1.15] text-[var(--ink)] mb-4 font-normal">
            Thank you. We'll be in touch.
          </h1>
          <p className="akki-serif text-[16px] leading-[1.7] text-[var(--deep)] max-w-[44ch] mx-auto">
            Your registration is recorded. We review applications in batches and respond from a real address.
          </p>
        </section>
      </MarketingShell>
    );
  }

  return (
    <MarketingShell>
      <section
        className="max-w-[640px] mx-auto px-6 lg:px-10 py-16 md:py-24"
        data-testid="early-access-page"
      >
        <p className="akki-overline mb-3 text-[var(--accent)]">Early Access</p>
        <h1 className="akki-serif text-[36px] sm:text-[44px] leading-[1.1] tracking-tight text-[var(--ink)] mb-5 font-normal">
          Apply for early access
        </h1>
        <p className="akki-serif text-[16px] leading-[1.7] text-[var(--deep)] mb-10 max-w-[56ch]">
          Tell us a little about you and the boards you serve. We will be in touch from a real address.
        </p>

        <form onSubmit={onSubmit} className="space-y-6" data-testid="early-access-form" noValidate>
          <div>
            <label htmlFor="ea-email" className="akki-overline mb-2 block">
              Email <span className="text-[var(--accent)]">·</span> required
            </label>
            <Input
              id="ea-email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@company.com"
              maxLength={200}
              aria-label="Email address"
              aria-required="true"
              data-testid="ea-email"
              className="bg-white rounded-md h-12 text-[15px] text-[var(--ink)] placeholder:text-[var(--muted)] border-[var(--rule)] focus:border-[var(--accent)]"
            />
          </div>

          <div>
            <label htmlFor="ea-full-name" className="akki-overline mb-2 block">Full name</label>
            <Input
              id="ea-full-name"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              maxLength={200}
              aria-label="Full name"
              data-testid="ea-full-name"
              className="bg-white rounded-md h-12 text-[15px] text-[var(--ink)] placeholder:text-[var(--muted)] border-[var(--rule)] focus:border-[var(--accent)]"
            />
          </div>

          <div>
            <label htmlFor="ea-company" className="akki-overline mb-2 block">Company</label>
            <Input
              id="ea-company"
              value={company}
              onChange={(e) => setCompany(e.target.value)}
              maxLength={200}
              aria-label="Company"
              data-testid="ea-company"
              className="bg-white rounded-md h-12 text-[15px] text-[var(--ink)] placeholder:text-[var(--muted)] border-[var(--rule)] focus:border-[var(--accent)]"
            />
          </div>

          <div>
            <label htmlFor="ea-role" className="akki-overline mb-2 block">Role</label>
            <Select value={role} onValueChange={setRole}>
              <SelectTrigger
                id="ea-role"
                aria-label="Role"
                data-testid="ea-role"
                className="bg-white rounded-md h-12 text-[15px] text-[var(--ink)] border-[var(--rule)]"
              >
                <SelectValue placeholder="Choose one" />
              </SelectTrigger>
              <SelectContent>
                {ROLES.map((r) => (
                  <SelectItem key={r.value} value={r.value}>{r.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div>
            <label htmlFor="ea-board-count" className="akki-overline mb-2 block">
              Primary board count
            </label>
            <Input
              id="ea-board-count"
              type="number"
              min={0}
              max={50}
              value={boardCount}
              onChange={(e) => setBoardCount(e.target.value)}
              aria-label="Primary board count"
              data-testid="ea-board-count"
              className="bg-white rounded-md h-12 text-[15px] text-[var(--ink)] placeholder:text-[var(--muted)] border-[var(--rule)] focus:border-[var(--accent)]"
            />
          </div>

          <div>
            <label htmlFor="ea-message" className="akki-overline mb-2 block">Message</label>
            <Textarea
              id="ea-message"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              rows={4}
              maxLength={2000}
              aria-label="Message"
              data-testid="ea-message"
              className="bg-white rounded-md text-[14px] text-[var(--ink)] placeholder:text-[var(--muted)] border-[var(--rule)] focus:border-[var(--accent)] resize-none"
            />
          </div>

          {error && (
            <p
              className="text-[13px] text-[var(--accent)]"
              role="alert"
              data-testid="ea-error"
            >
              {error}
            </p>
          )}

          <div className="pt-2">
            <Button
              type="submit"
              disabled={!email.trim() || submitting}
              className="bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white rounded-sm h-12 px-7 text-[14px] font-medium disabled:opacity-50"
              data-testid="ea-submit"
            >
              {submitting ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" /> Submitting
                </>
              ) : (
                <>
                  Apply for early access <ArrowRight className="w-4 h-4 ml-2" />
                </>
              )}
            </Button>
          </div>
        </form>
      </section>
    </MarketingShell>
  );
}
