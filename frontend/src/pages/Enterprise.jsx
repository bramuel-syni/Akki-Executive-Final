import React, { useEffect, useMemo, useState } from "react";
import AppShell from "@/components/layout/AppShell";
import { useAuth } from "@/contexts/AuthContext";
import { api, apiErrorMessage } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { Building2, ShieldCheck, Users, Layers, Check } from "lucide-react";
import { toast } from "sonner";

/**
 * Enterprise — light-touch lead-gen surface.
 * Same app, same login, but signals to NEDs/Execs on Personal contexts that
 * Enterprise exists for organisations who want multi-seat sponsored data
 * ownership, audit-grade exports, SSO, and a managed onboarding.
 */
export default function Enterprise() {
  const { activeContext } = useAuth();
  const isPersonal = useMemo(() => {
    const t = activeContext?.type;
    return t === "ned_personal" || t === "executive_personal";
  }, [activeContext]);

  const [submitted, setSubmitted] = useState(false);
  const [companySize, setCompanySize] = useState("");
  const [timing, setTiming] = useState("");
  const [useCase, setUseCase] = useState("");
  const [sending, setSending] = useState(false);

  useEffect(() => {
    let live = true;
    api.get("/enterprise/interest/me")
      .then((r) => { if (live && r.data?.submitted) setSubmitted(true); })
      .catch(() => {});
    return () => { live = false; };
  }, []);

  const submit = async () => {
    setSending(true);
    try {
      await api.post("/enterprise/interest", {
        use_case: useCase, company_size: companySize, timing,
      });
      setSubmitted(true);
      toast.success("Thanks — we'll be in touch.");
    } catch (e) {
      toast.error(apiErrorMessage(e));
    } finally {
      setSending(false);
    }
  };

  return (
    <AppShell>
      <div className="max-w-4xl mx-auto px-6 py-12" data-testid="enterprise-page">
        <div className="mb-10">
          <p className="text-[11px] uppercase tracking-[0.2em] text-[var(--accent)] mb-2">
            Akki for Enterprise
          </p>
          <h1 className="akki-serif text-4xl sm:text-5xl text-[var(--ink)] tracking-tight leading-[1.05]">
            For boards and ExCos that need their AI to be auditable.
          </h1>
          <p className="text-[15px] text-slate-600 mt-5 leading-relaxed max-w-2xl">
            You're on the {isPersonal ? "Personal" : "current"} tier today.
            Enterprise turns AKKI into a sponsored, multi-seat workspace —
            owned by your organisation, with the controls a board secretariat
            and audit committee actually expect.
          </p>
        </div>

        <div className="grid md:grid-cols-2 gap-6 mb-12">
          {[
            { I: Users, t: "Multi-seat, sponsored", d: "Org-owned data, role-scoped access for directors, ExCo, secretariat, auditors." },
            { I: ShieldCheck, t: "Audit-grade provenance", d: "Every artefact carries source, model, validation pass, and the second-LLM verdict — exportable on demand." },
            { I: Layers, t: "Cross-board portfolio view", d: "NEDs sitting on multiple boards see the cross-cutting patterns, not just one room." },
            { I: Building2, t: "SSO, retention, residency", d: "SAML/OIDC, configurable retention windows, jurisdiction-aware data residency." },
          ].map(({ I, t, d }) => (
            <div key={t} className="bg-white border border-[#E1E6ED] rounded-sm p-6">
              <I className="w-5 h-5 text-[var(--accent)] mb-3" strokeWidth={1.7} />
              <h3 className="akki-serif text-[18px] text-[var(--ink)] mb-1">{t}</h3>
              <p className="text-[13px] text-slate-600 leading-relaxed">{d}</p>
            </div>
          ))}
        </div>

        <section className="bg-white border border-[#E1E6ED] rounded-sm p-8" data-testid="enterprise-interest-card">
          {submitted ? (
            <div className="space-y-4" data-testid="enterprise-interest-thanks">
              <div className="flex items-start gap-4">
                <Check className="w-6 h-6 text-[var(--accent)] mt-1" strokeWidth={1.7} />
                <div>
                  <h3 className="akki-serif text-[20px] text-[var(--ink)] mb-1">
                    Noted — thank you.
                  </h3>
                  <p className="text-[14px] text-slate-600 leading-relaxed">
                    We'll be in touch within two working days. In the meantime,
                    your Personal workspace stays exactly as it is.
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setSubmitted(false)}
                className="text-[12px] uppercase tracking-[0.14em] text-[var(--accent)] hover:underline pl-10"
                data-testid="enterprise-update-note-btn"
              >
                Update my note →
              </button>
            </div>
          ) : (
            <>
              <h2 className="akki-serif text-[22px] text-[var(--ink)] mb-1">
                Talk to us about Enterprise.
              </h2>
              <p className="text-[13px] text-slate-600 mb-6">
                A short note is plenty — we'll reach out to set up a 20-minute call.
              </p>
              <div className="grid md:grid-cols-2 gap-4 mb-4">
                <div>
                  <Label className="text-[11px] uppercase tracking-[0.16em] text-slate-500">
                    Company size
                  </Label>
                  <Select value={companySize} onValueChange={setCompanySize}>
                    <SelectTrigger className="mt-1.5" data-testid="enterprise-size-select">
                      <SelectValue placeholder="Select" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="1-10">1–10</SelectItem>
                      <SelectItem value="11-50">11–50</SelectItem>
                      <SelectItem value="51-250">51–250</SelectItem>
                      <SelectItem value="251-1000">251–1,000</SelectItem>
                      <SelectItem value="1000+">1,000+</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label className="text-[11px] uppercase tracking-[0.16em] text-slate-500">
                    Timing
                  </Label>
                  <Select value={timing} onValueChange={setTiming}>
                    <SelectTrigger className="mt-1.5" data-testid="enterprise-timing-select">
                      <SelectValue placeholder="Select" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="now">Evaluating now</SelectItem>
                      <SelectItem value="quarter">This quarter</SelectItem>
                      <SelectItem value="6mo">Next 6 months</SelectItem>
                      <SelectItem value="curious">Just curious</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div>
                <Label className="text-[11px] uppercase tracking-[0.16em] text-slate-500">
                  What's the use case? (Optional)
                </Label>
                <Textarea
                  value={useCase}
                  onChange={(e) => setUseCase(e.target.value)}
                  placeholder="e.g. equip our 9-NED main board with cross-portfolio pattern detection"
                  className="mt-1.5 min-h-[100px]"
                  data-testid="enterprise-usecase-input"
                />
              </div>
              <div className="mt-6 flex justify-end">
                <Button
                  onClick={submit}
                  disabled={sending}
                  className="bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white rounded-sm h-10 px-6"
                  data-testid="enterprise-submit-btn"
                >
                  {sending ? "Sending…" : "Request a conversation"}
                </Button>
              </div>
            </>
          )}
        </section>
      </div>
    </AppShell>
  );
}
