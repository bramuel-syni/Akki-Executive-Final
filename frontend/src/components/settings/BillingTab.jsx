import React, { useCallback, useEffect, useState } from "react";
import { api, apiErrorMessage } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { CheckCircle2, Loader2, Sparkles, BellRing } from "lucide-react";

/**
 * Billing & Subscription — Coming Soon (chunk c, 2026-05-25).
 *
 * The previous §M4 Stripe checkout flow is gone. The user has chosen
 * to surface an honest "Coming Soon" state instead of running a
 * silent-fake-success mock.
 *
 * Two surfaces:
 *   1. The Coming-Soon hero (heading + body + Notify-me CTA).
 *      Verbatim copy is owned server-side at
 *      `routers/billing.py::COMING_SOON_HEADING` / `..._BODY` / `..._CTA`
 *      so tests can verbatim-assert against the same string.
 *   2. A read-only preview of the plan catalog so the user knows what
 *      they'll get later. NO upgrade buttons. The current-plan card is
 *      marked "Current plan"; the others are marked "Coming soon".
 *
 * `POST /api/notify-billing-launch` records the requester's interest;
 * idempotent (server side set-if-not-exists).
 */

// Spec-verbatim copy — must match `routers/billing.py` exactly.
const COMING_SOON_HEADING = "Billing & Subscription — Coming Soon";
const COMING_SOON_BODY =
  "We're finalizing our subscription tiers. Your account is fully " +
  "active during this preview period; billing will roll out in a " +
  "future release.";
const COMING_SOON_CTA = "Notify me when this is ready";

export default function BillingTab() {
  const [plans, setPlans] = useState([]);
  const [me, setMe] = useState(null);
  const [loading, setLoading] = useState(true);
  const [notifying, setNotifying] = useState(false);
  const [notifyState, setNotifyState] = useState(null);

  const load = useCallback(async () => {
    try {
      const [a, b] = await Promise.all([
        api.get("/billing/plans"),
        api.get("/billing/me"),
      ]);
      setPlans(a.data.plans || []);
      setMe(b.data || null);
    } catch (e) {
      toast.error(apiErrorMessage(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const onNotify = async () => {
    setNotifying(true);
    try {
      const { data } = await api.post("/notify-billing-launch");
      setNotifyState(data);
      if (data.already_subscribed) {
        toast.message("You're already on the list — we'll email you.");
      } else {
        toast.success("Got it — we'll email you when billing launches.");
      }
    } catch (e) {
      toast.error(apiErrorMessage(e));
    } finally {
      setNotifying(false);
    }
  };

  if (loading) {
    return (
      <div
        className="p-12 text-center text-[12px] uppercase tracking-widest text-[var(--muted)]"
        data-testid="billing-loading"
      >
        Loading…
      </div>
    );
  }

  const currentPlanId = me?.plan?.id || "free";

  return (
    <section className="space-y-10" data-testid="billing-tab">
      <header className="space-y-3" data-testid="billing-coming-soon-hero">
        <p className="akki-overline tracking-[0.18em] text-[var(--accent)]">
          Billing
        </p>
        <h2
          className="akki-serif text-[28px] sm:text-[32px] leading-[1.15] text-[var(--ink)]"
          data-testid="billing-coming-soon-heading"
        >
          {COMING_SOON_HEADING}
        </h2>
        <p
          className="text-[14px] leading-[1.7] text-[var(--deep)] max-w-[62ch]"
          data-testid="billing-coming-soon-body"
        >
          {COMING_SOON_BODY}
        </p>
        <div className="pt-3">
          <Button
            onClick={onNotify}
            disabled={notifying || notifyState?.already_subscribed}
            className="bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white"
            data-testid="billing-notify-cta"
          >
            {notifying ? (
              <>
                <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                Adding you to the list…
              </>
            ) : notifyState?.already_subscribed ? (
              <>
                <CheckCircle2 className="w-3.5 h-3.5 mr-1.5" />
                You're on the list
              </>
            ) : notifyState?.notified ? (
              <>
                <CheckCircle2 className="w-3.5 h-3.5 mr-1.5" />
                We'll email you
              </>
            ) : (
              <>
                <BellRing className="w-3.5 h-3.5 mr-1.5" />
                {COMING_SOON_CTA}
              </>
            )}
          </Button>
        </div>
        {me?.subscription_status === "active" ? (
          <p
            className="mt-3 inline-block text-[11px] uppercase tracking-wider text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded"
            data-testid="billing-deferred-banner"
          >
            Billing launch deferred — your current access continues.
          </p>
        ) : null}
      </header>

      <div
        className="space-y-3"
        data-testid="billing-plans-preview"
        aria-labelledby="billing-plans-preview-heading"
      >
        <h3
          id="billing-plans-preview-heading"
          className="akki-serif text-[18px] text-[var(--ink)]"
        >
          What you'll get when billing launches
        </h3>
        <p className="text-[13px] text-[var(--muted)] max-w-[62ch]">
          A preview of the tiers we're finalizing. Nothing on this page
          charges your card — there is no checkout in this release.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-3">
          {plans.map((p) => {
            const isCurrent = p.id === currentPlanId;
            const isFree = p.price_usd === 0;
            return (
              <div
                key={p.id}
                className={`rounded-lg p-5 border-2 ${
                  isCurrent
                    ? "border-[var(--accent)] bg-[var(--cream)]"
                    : "border-[var(--rule)] bg-white"
                } flex flex-col`}
                data-testid={`billing-plan-${p.id}`}
              >
                <p className="text-[10.5px] uppercase tracking-[0.18em] text-[var(--muted)] font-mono mb-1">
                  {p.id === "team" ? "TEAMS" : p.id.toUpperCase()}
                </p>
                <p className="akki-serif text-[22px] text-[var(--ink)] mb-1">
                  {p.name}
                </p>
                <p className="text-[13px] text-[var(--deep)] italic mb-3">
                  {p.tagline}
                </p>
                <p className="akki-serif text-[28px] text-[var(--ink)] mb-1">
                  {isFree ? (
                    "Free"
                  ) : (
                    <>
                      ${p.price_usd.toFixed(0)}
                      <span className="text-[14px] text-[var(--muted)]">
                        /{p.interval}
                      </span>
                    </>
                  )}
                </p>
                <ul className="space-y-1.5 text-[13px] text-[var(--deep)] mt-3 mb-5 flex-1">
                  {p.features.map((f, i) => (
                    <li key={i} className="flex items-start gap-2">
                      <CheckCircle2
                        className="w-3.5 h-3.5 text-[var(--accent)] mt-1 shrink-0"
                        strokeWidth={1.7}
                      />
                      <span>{f}</span>
                    </li>
                  ))}
                </ul>
                {isCurrent ? (
                  <Button
                    disabled
                    variant="outline"
                    className="border-[var(--rule)]"
                    data-testid={`billing-current-${p.id}`}
                  >
                    <CheckCircle2 className="w-3.5 h-3.5 mr-1.5 text-[var(--accent)]" />{" "}
                    Current plan
                  </Button>
                ) : (
                  <Button
                    disabled
                    variant="outline"
                    className="border-[var(--rule)] text-[var(--muted)]"
                    data-testid={`billing-coming-soon-${p.id}`}
                  >
                    <Sparkles className="w-3.5 h-3.5 mr-1.5" /> Coming soon
                  </Button>
                )}
              </div>
            );
          })}
        </div>
      </div>

      <footer className="text-[12px] text-[var(--muted)] pt-4 border-t border-[var(--rule)]">
        No charges in this preview. Subscriptions launch in a future
        release.
      </footer>
    </section>
  );
}
