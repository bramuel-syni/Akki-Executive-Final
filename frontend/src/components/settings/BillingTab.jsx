import React, { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api, apiErrorMessage } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { CheckCircle2, Loader2, CreditCard, Sparkles } from "lucide-react";

/**
 * Settings → Billing tab.
 *
 * Server-side plan catalog (free/pro/team) with Stripe Checkout for the
 * paid tiers. After Stripe redirects back with ?session_id=… we poll
 * /api/billing/status until the payment is paid (or expired). The plan
 * upgrade itself is applied server-side (in checkout/status + webhook),
 * so we just refresh on success.
 */
export default function BillingTab() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [plans, setPlans] = useState([]);
  const [me, setMe] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(null); // plan_id currently checking-out
  const [poll, setPoll] = useState(null); // { sessionId, attempt }

  const load = useCallback(async () => {
    try {
      const [a, b] = await Promise.all([
        api.get("/billing/plans"),
        api.get("/billing/me"),
      ]);
      setPlans(a.data.plans || []);
      setMe(b.data || null);
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  // ---- post-Stripe return polling ------------------------------------------
  useEffect(() => {
    const sessionId = searchParams.get("session_id");
    const cancelled = searchParams.get("cancelled");
    if (cancelled) {
      toast.message("Checkout cancelled. No charge was made.");
      const next = new URLSearchParams(searchParams);
      next.delete("cancelled");
      setSearchParams(next, { replace: true });
      return;
    }
    if (sessionId && !poll) {
      setPoll({ sessionId, attempt: 0 });
    }
  }, [searchParams, poll, setSearchParams]);

  useEffect(() => {
    if (!poll) return;
    let cancelled = false;
    const tick = async () => {
      if (poll.attempt >= 8) {
        toast.error("Payment status check timed out. Refresh in a minute.");
        const next = new URLSearchParams(searchParams);
        next.delete("session_id");
        setSearchParams(next, { replace: true });
        setPoll(null);
        return;
      }
      try {
        const { data } = await api.get(`/billing/status/${poll.sessionId}`);
        if (data.payment_status === "paid") {
          toast.success(`You're now on the ${data.plan_id.toUpperCase()} plan.`);
          await load();
          const next = new URLSearchParams(searchParams);
          next.delete("session_id");
          setSearchParams(next, { replace: true });
          setPoll(null);
          return;
        }
        if (data.status === "expired") {
          toast.error("Checkout session expired. Please try again.");
          const next = new URLSearchParams(searchParams);
          next.delete("session_id");
          setSearchParams(next, { replace: true });
          setPoll(null);
          return;
        }
        if (!cancelled) setTimeout(() => setPoll((p) => p && { ...p, attempt: p.attempt + 1 }), 2000);
      } catch (e) {
        if (!cancelled) setTimeout(() => setPoll((p) => p && { ...p, attempt: p.attempt + 1 }), 2000);
      }
    };
    tick();
    return () => { cancelled = true; };
  }, [poll, searchParams, setSearchParams, load]);

  const onCheckout = async (planId) => {
    setBusy(planId);
    try {
      const { data } = await api.post("/billing/checkout", {
        plan_id: planId,
        origin_url: window.location.origin,
      });
      if (data.url) { window.location.href = data.url; }
      else { toast.error("Checkout could not be started."); }
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setBusy(null); }
  };

  if (loading) {
    return <div className="p-12 text-center text-[12px] uppercase tracking-widest text-[var(--muted)]">Loading…</div>;
  }

  const currentPlanId = me?.plan?.id || "free";

  return (
    <section className="space-y-8" data-testid="billing-tab">
      {poll && (
        <div className="bg-amber-50 border border-amber-200 rounded-md p-3 text-[13px] text-amber-900 flex items-center gap-2" data-testid="billing-polling">
          <Loader2 className="w-4 h-4 animate-spin" /> Confirming your payment with Stripe…
        </div>
      )}

      <header>
        <h2 className="akki-serif text-[22px] text-[var(--ink)] mb-1">Billing</h2>
        <p className="text-[13px] text-[var(--muted)]">
          You're on <strong className="text-[var(--ink)]">{me?.plan?.name || "Free"}</strong>
          {me?.subscription_status === "active" && <span className="ml-2 text-[11px] uppercase tracking-wider text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded">active</span>}.
          Upgrade any time. Cancel any time. No surprises.
        </p>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {plans.map((p) => {
          const isCurrent = p.id === currentPlanId;
          const isFree = p.price_usd === 0;
          return (
            <div key={p.id}
              className={`rounded-lg p-5 border-2 ${isCurrent ? "border-[var(--accent)] bg-[var(--cream)]" : "border-[var(--rule)] bg-white"} flex flex-col`}
              data-testid={`billing-plan-${p.id}`}>
              <p className="text-[10.5px] uppercase tracking-[0.18em] text-[var(--muted)] font-mono mb-1">{p.id === "team" ? "TEAMS" : p.id.toUpperCase()}</p>
              <p className="akki-serif text-[22px] text-[var(--ink)] mb-1">{p.name}</p>
              <p className="text-[13px] text-[var(--deep)] italic mb-3">{p.tagline}</p>
              <p className="akki-serif text-[28px] text-[var(--ink)] mb-1">
                {isFree ? "Free" : <>${p.price_usd.toFixed(0)}<span className="text-[14px] text-[var(--muted)]">/{p.interval}</span></>}
              </p>
              <ul className="space-y-1.5 text-[13px] text-[var(--deep)] mt-3 mb-5 flex-1">
                {p.features.map((f, i) => (
                  <li key={i} className="flex items-start gap-2">
                    <CheckCircle2 className="w-3.5 h-3.5 text-[var(--accent)] mt-1 shrink-0" strokeWidth={1.7} />
                    <span>{f}</span>
                  </li>
                ))}
              </ul>
              {isCurrent ? (
                <Button disabled variant="outline" className="border-[var(--rule)]" data-testid={`billing-current-${p.id}`}>
                  <CheckCircle2 className="w-3.5 h-3.5 mr-1.5 text-[var(--accent)]" /> Current plan
                </Button>
              ) : isFree ? (
                <Button disabled variant="outline" className="border-[var(--rule)]">
                  Free tier
                </Button>
              ) : (
                <Button
                  onClick={() => onCheckout(p.id)}
                  disabled={busy === p.id}
                  className="bg-[var(--chrome)] hover:bg-[var(--chrome)]/90 text-white"
                  data-testid={`billing-upgrade-${p.id}`}
                >
                  {busy === p.id
                    ? <><Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> Redirecting…</>
                    : <><Sparkles className="w-3.5 h-3.5 mr-1.5" /> {p.cta}</>}
                </Button>
              )}
            </div>
          );
        })}
      </div>

      <footer className="text-[12px] text-[var(--muted)] flex items-center gap-1.5 pt-4 border-t border-[var(--rule)]">
        <CreditCard className="w-3 h-3" /> Payments processed by Stripe in test mode. No charges in this preview.
      </footer>
    </section>
  );
}
