import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import AppShell from "@/components/layout/AppShell";
import { useAuth } from "@/contexts/AuthContext";
import { api, apiErrorMessage } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { toast } from "sonner";
import {
  ArrowRight, ArrowLeft, Landmark, Briefcase, Layers, Check, Sparkles,
  CheckCircle2, Edit3, ShieldCheck,
} from "lucide-react";
import {
  SHARED_QUESTIONS, NED_QUESTIONS, EXEC_QUESTIONS,
} from "@/lib/onboardingQuestions";

const ROLES = [
  {
    value: "ned", title: "Non-Executive Director",
    subtitle: "You serve on one or more boards as a NED.",
    icon: Landmark,
  },
  {
    value: "executive", title: "Operating Executive",
    subtitle: "You report into a board or lead an operating team.",
    icon: Briefcase,
  },
  {
    value: "dual", title: "Both",
    subtitle: "NED and Executive. Switch any time.",
    icon: Layers,
  },
];

function ProgressBar({ value, total }) {
  const pct = Math.min(100, Math.round((value / total) * 100));
  return (
    <div className="flex items-center gap-3">
      <div className="flex-1 h-[3px] bg-slate-100 rounded-sm overflow-hidden">
        <div
          className="h-full bg-[#C9A961] transition-all duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-[10px] uppercase tracking-[0.2em] text-slate-400 font-mono">
        {value}/{total}
      </span>
    </div>
  );
}

export default function Onboarding() {
  const { account, activeContext, bootstrap, refreshContexts } = useAuth();
  const navigate = useNavigate();

  const [step, setStep] = useState(0);
  // 0 = role declaration, 1..7 = audit questions, 8 = review/submit, 9 = done
  const TOTAL_QUESTIONS = 7;

  const [declaredRole, setDeclaredRole] = useState(
    account?.declared_role && account.declared_role !== "undeclared" ? account.declared_role : null
  );
  const [auditRole, setAuditRole] = useState(null); // "ned" | "executive" within this context
  const [answers, setAnswers] = useState({});
  const [industries, setIndustries] = useState([]);
  const [jurisdictions, setJurisdictions] = useState([]);
  const [saving, setSaving] = useState(false);
  const [loadedExisting, setLoadedExisting] = useState(false);

  const isDeclared = account?.declared_role && account.declared_role !== "undeclared";

  // Load context object if it exists (resumable)
  useEffect(() => {
    if (!activeContext?.id) return;
    (async () => {
      try {
        const { data } = await api.get(`/contexts/${activeContext.id}/context-object`);
        if (data) {
          setAnswers({
            industry: data.industry, sector: data.sector,
            jurisdiction: data.jurisdiction, ...(data.answers || {}),
          });
          setAuditRole(data.role || null);
          if (data.completed) setStep(9);
          else if (typeof data.step === "number" && data.step > 0) setStep(data.step);
        }
      } catch { /* ignore */ }
      finally { setLoadedExisting(true); }
    })();
  }, [activeContext?.id]);

  // Default step to 1 (audit start) once role is declared and context exists
  useEffect(() => {
    if (!loadedExisting) return;
    if (isDeclared && step === 0) setStep(1);
  }, [isDeclared, loadedExisting, step]);

  // Default auditRole from declared_role (dual → executive by default; user can change)
  useEffect(() => {
    if (!auditRole && isDeclared) {
      const def = account.declared_role === "ned" ? "ned" : "executive";
      setAuditRole(def);
    }
  }, [auditRole, isDeclared, account?.declared_role]);

  // Load industry/jurisdiction presets
  useEffect(() => {
    (async () => {
      try {
        const [i, j] = await Promise.all([
          api.get("/presets/industries"),
          api.get("/presets/jurisdictions"),
        ]);
        setIndustries(i.data); setJurisdictions(j.data);
      } catch { /* silent */ }
    })();
  }, []);

  // --- Handlers ---
  const declare = async () => {
    if (!declaredRole) return;
    setSaving(true);
    try {
      await api.post("/auth/declare-role", { declared_role: declaredRole });
      await bootstrap();
      setAuditRole(declaredRole === "ned" ? "ned" : "executive");
      setStep(1);
      toast.success("Role declared");
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setSaving(false); }
  };

  const questions = useMemo(() => {
    return [
      SHARED_QUESTIONS[0],
      SHARED_QUESTIONS[1],
      ...(auditRole === "ned" ? NED_QUESTIONS : EXEC_QUESTIONS),
    ];
  }, [auditRole]);

  const currentQuestion = step >= 1 && step <= TOTAL_QUESTIONS ? questions[step - 1] : null;
  const currentValue = currentQuestion ? answers[currentQuestion.id] : null;

  const canAdvance = useMemo(() => {
    if (!currentQuestion) return false;
    if (currentQuestion.type === "multi") return Array.isArray(currentValue) && currentValue.length > 0;
    if (currentQuestion.type === "industry") return !!answers.industry;
    if (currentQuestion.type === "jurisdiction") return !!answers.jurisdiction;
    return !!currentValue;
  }, [currentQuestion, currentValue, answers]);

  const persist = useCallback(async (opts = {}) => {
    if (!activeContext?.id) return;
    try {
      const base = { industry: answers.industry, sector: answers.sector, jurisdiction: answers.jurisdiction };
      const rest = { ...answers };
      delete rest.industry; delete rest.sector; delete rest.jurisdiction;
      await api.post(`/contexts/${activeContext.id}/context-object`, {
        ...base, role: auditRole, answers: rest,
        step: opts.step ?? step, completed: !!opts.completed,
      });
      await refreshContexts();
    } catch (e) { toast.error(apiErrorMessage(e)); throw e; }
  }, [activeContext?.id, answers, auditRole, step, refreshContexts]);

  const onNext = async () => {
    if (!canAdvance) return;
    if (step < TOTAL_QUESTIONS) {
      await persist({ step: step + 1 });
      setStep(step + 1);
    } else if (step === TOTAL_QUESTIONS) {
      setStep(8); // review
    }
  };

  const onBack = () => step > 1 && setStep(step - 1);

  const onSubmit = async () => {
    setSaving(true);
    try {
      await persist({ completed: true, step: TOTAL_QUESTIONS });
      setStep(9);
      toast.success("Context Object saved");
    } catch { /* error already toasted */ }
    finally { setSaving(false); }
  };

  const setAnswer = (id, v) => setAnswers((prev) => ({ ...prev, [id]: v }));

  const toggleMulti = (id, v) => {
    setAnswers((prev) => {
      const list = Array.isArray(prev[id]) ? prev[id] : [];
      return { ...prev, [id]: list.includes(v) ? list.filter((x) => x !== v) : [...list, v] };
    });
  };

  // -------- Render --------
  if (!loadedExisting) {
    return <AppShell><div className="p-12 text-center text-slate-400 text-xs uppercase tracking-widest">Loading…</div></AppShell>;
  }

  // ====== STEP 0 · ROLE DECLARATION ======
  if (step === 0) {
    return (
      <AppShell>
        <div className="p-8 md:p-12 max-w-5xl mx-auto">
          <div className="mb-10">
            <p className="akki-overline mb-3">Module M2 · Step 1 of 3</p>
            <h1 className="text-4xl font-light tracking-tight text-[#0A1F44] mb-3">Declare your role.</h1>
            <p className="text-base text-slate-500 max-w-2xl leading-relaxed">
              Choose how you act. This shapes your Home, your audit questions, and which surfaces are emphasised.
            </p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5 mb-8">
            {ROLES.map((r) => {
              const I = r.icon; const active = declaredRole === r.value;
              return (
                <button
                  key={r.value} type="button"
                  onClick={() => setDeclaredRole(r.value)}
                  className={`text-left border p-6 rounded-sm transition-all ${active ? "border-[#C9A961] bg-amber-50/30 ring-1 ring-[#C9A961]/40 -translate-y-0.5 shadow-sm" : "border-[#E1E6ED] bg-white hover:border-slate-300"}`}
                  data-testid={`role-option-${r.value}`}
                >
                  <I className={`w-5 h-5 mb-4 ${active ? "text-[#C9A961]" : "text-slate-400"}`} strokeWidth={1.6} />
                  <p className="text-sm font-medium text-[#0A1F44] mb-1">{r.title}</p>
                  <p className="text-xs text-slate-500 leading-relaxed">{r.subtitle}</p>
                </button>
              );
            })}
          </div>
          <Button
            onClick={declare} disabled={!declaredRole || saving}
            className="bg-[#0A1F44] hover:bg-[#0E2958] rounded-sm h-11 px-6 group"
            data-testid="declare-role-btn"
          >
            {saving ? "Saving…" : "Continue to audit"}
            {!saving && <ArrowRight className="w-4 h-4 ml-2 group-hover:translate-x-0.5 transition-transform" />}
          </Button>
        </div>
      </AppShell>
    );
  }

  // ====== STEP 9 · DONE ======
  if (step === 9) {
    return (
      <AppShell>
        <div className="p-8 md:p-12 max-w-4xl mx-auto">
          <div className="bg-white border border-[#E1E6ED] rounded-sm p-10">
            <div className="flex items-start gap-5 mb-8">
              <div className="w-12 h-12 bg-[#C9A961]/10 border border-[#C9A961]/40 flex items-center justify-center rounded-sm">
                <CheckCircle2 className="w-6 h-6 text-[#C9A961]" strokeWidth={1.8} />
              </div>
              <div>
                <p className="akki-overline mb-1">Context Object v1 · saved</p>
                <h1 className="text-3xl font-light tracking-tight text-[#0A1F44] mb-2">
                  AKKI is tuned to <span className="text-[#C9A961]">{activeContext?.name}.</span>
                </h1>
                <p className="text-sm text-slate-500 max-w-2xl leading-relaxed">
                  Every signal, briefing, and lens session in this context will be grounded in the profile below. You can update your answers any time from Settings.
                </p>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-px bg-[#E1E6ED] border border-[#E1E6ED] rounded-sm">
              {questions.map((q) => {
                const v = answers[q.id];
                const display =
                  q.type === "multi" && Array.isArray(v)
                    ? v.map((x) => q.options?.find((o) => o.value === x)?.label || x).join(", ")
                    : q.type === "single"
                      ? q.options?.find((o) => o.value === v)?.label || v
                      : v || "—";
                return (
                  <div key={q.id} className="bg-white p-5">
                    <p className="text-[10px] uppercase tracking-wider text-slate-400 mb-1.5">
                      {q.question}
                    </p>
                    <p className="text-sm text-[#0A1F44]">{display || "—"}</p>
                  </div>
                );
              })}
            </div>

            <div className="flex items-center gap-3 mt-8">
              <Button
                onClick={() => { setStep(1); }}
                variant="outline"
                className="rounded-sm h-10 border-[#E1E6ED]"
                data-testid="edit-audit-btn"
              >
                <Edit3 className="w-4 h-4 mr-2" /> Edit answers
              </Button>
              <Link to="/app">
                <Button className="bg-[#0A1F44] hover:bg-[#0E2958] rounded-sm h-10 group" data-testid="go-home-btn">
                  Go to home <ArrowRight className="w-4 h-4 ml-2 group-hover:translate-x-0.5 transition-transform" />
                </Button>
              </Link>
            </div>
          </div>

          <div className="mt-8 flex items-center gap-3 text-xs text-slate-500">
            <ShieldCheck className="w-4 h-4 text-[#C9A961]" strokeWidth={1.6} />
            <span>
              Answers are versioned. Every update creates a new Context Object version — the previous one is retained for audit.
            </span>
          </div>
        </div>
      </AppShell>
    );
  }

  // ====== STEP 8 · REVIEW ======
  if (step === 8) {
    return (
      <AppShell>
        <div className="p-8 md:p-12 max-w-4xl mx-auto">
          <div className="mb-8">
            <p className="akki-overline mb-2">Module M2 · Review</p>
            <h1 className="text-3xl font-light tracking-tight text-[#0A1F44] mb-2">
              Review your answers
            </h1>
            <p className="text-sm text-slate-500">
              Submitting saves Context Object v1 for <strong className="text-[#0A1F44]">{activeContext?.name}</strong>.
            </p>
          </div>
          <div className="bg-white border border-[#E1E6ED] rounded-sm">
            {questions.map((q, idx) => {
              const v = answers[q.id];
              const display =
                q.type === "multi" && Array.isArray(v)
                  ? v.map((x) => q.options?.find((o) => o.value === x)?.label || x).join(", ")
                  : q.type === "single"
                    ? q.options?.find((o) => o.value === v)?.label || v
                    : v || "—";
              return (
                <div key={q.id} className="px-6 py-4 border-b last:border-b-0 border-[#E1E6ED] flex items-start justify-between gap-6">
                  <div>
                    <p className="text-[10px] uppercase tracking-wider text-slate-400 font-mono mb-1">Q{idx + 1}</p>
                    <p className="text-sm font-medium text-[#0A1F44] mb-1">{q.question}</p>
                    <p className="text-sm text-slate-600">{display || "—"}</p>
                  </div>
                  <Button
                    size="sm" variant="ghost"
                    onClick={() => setStep(idx + 1)}
                    className="rounded-sm h-8 text-xs text-slate-500"
                    data-testid={`edit-q-${q.id}`}
                  >
                    <Edit3 className="w-3.5 h-3.5 mr-1.5" /> Edit
                  </Button>
                </div>
              );
            })}
          </div>
          <div className="flex items-center gap-3 mt-8">
            <Button onClick={() => setStep(TOTAL_QUESTIONS)} variant="outline" className="rounded-sm h-10 border-[#E1E6ED]" data-testid="review-back-btn">
              <ArrowLeft className="w-4 h-4 mr-2" /> Back
            </Button>
            <Button
              onClick={onSubmit} disabled={saving}
              className="bg-[#C9A961] hover:bg-[#B39556] text-[#0A1F44] font-medium rounded-sm h-10 group"
              data-testid="submit-audit-btn"
            >
              {saving ? "Saving…" : "Save Context Object"}
              {!saving && <Sparkles className="w-4 h-4 ml-2" />}
            </Button>
          </div>
        </div>
      </AppShell>
    );
  }

  // ====== STEPS 1..7 · QUESTIONS ======
  const q = currentQuestion;
  return (
    <AppShell>
      <div className="p-8 md:p-12 max-w-3xl mx-auto">
        <div className="mb-8">
          <ProgressBar value={step} total={TOTAL_QUESTIONS} />
          <div className="flex items-center gap-2 mt-4">
            <p className="akki-overline">Question {step} of {TOTAL_QUESTIONS}</p>
            {auditRole && (
              <span className="text-[10px] uppercase tracking-[0.2em] text-slate-400">
                · {auditRole === "ned" ? "NED audit" : "Executive audit"}
              </span>
            )}
          </div>
        </div>

        <div className="bg-white border border-[#E1E6ED] rounded-sm p-8 md:p-10 akki-fade-up" key={step}>
          <h2 className="text-2xl font-light tracking-tight text-[#0A1F44] mb-3">
            {q.question}
          </h2>
          {q.hint && <p className="text-sm text-slate-500 mb-8">{q.hint}</p>}

          {q.type === "industry" && (
            <div className="space-y-4 max-w-md">
              <div className="space-y-2">
                <Label className="text-xs uppercase tracking-wider text-slate-500 font-semibold">Industry</Label>
                <Select value={answers.industry || ""} onValueChange={(v) => {
                  setAnswer("industry", v);
                  setAnswer("sector", null);
                }}>
                  <SelectTrigger className="rounded-sm h-11" data-testid="industry-select">
                    <SelectValue placeholder="Choose an industry" />
                  </SelectTrigger>
                  <SelectContent className="rounded-sm">
                    {industries.map((i) => (
                      <SelectItem key={i.id} value={i.id}>{i.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              {answers.industry && (
                <div className="space-y-2">
                  <Label className="text-xs uppercase tracking-wider text-slate-500 font-semibold">Sector (optional)</Label>
                  <Select value={answers.sector || ""} onValueChange={(v) => setAnswer("sector", v)}>
                    <SelectTrigger className="rounded-sm h-11" data-testid="sector-select">
                      <SelectValue placeholder="Choose a sector" />
                    </SelectTrigger>
                    <SelectContent className="rounded-sm">
                      {(industries.find((i) => i.id === answers.industry)?.sectors || []).map((s) => (
                        <SelectItem key={s} value={s}>{s}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}
            </div>
          )}

          {q.type === "jurisdiction" && (
            <div className="space-y-3 max-w-md">
              <div className="flex flex-wrap gap-2">
                {jurisdictions.map((j) => {
                  const active = answers.jurisdiction === j;
                  return (
                    <button
                      key={j} type="button"
                      onClick={() => setAnswer("jurisdiction", j)}
                      className={`text-xs px-3 py-1.5 border rounded-sm transition-colors ${active ? "bg-[#0A1F44] text-white border-[#0A1F44]" : "bg-white border-[#E1E6ED] text-slate-600 hover:border-slate-300"}`}
                      data-testid={`jurisdiction-${j.toLowerCase().replace(/\s+/g, '-')}`}
                    >
                      {j}
                    </button>
                  );
                })}
              </div>
              <div className="space-y-2 pt-2">
                <Label className="text-xs uppercase tracking-wider text-slate-500 font-semibold">Or enter a specific jurisdiction</Label>
                <Input
                  value={answers.jurisdiction || ""}
                  onChange={(e) => setAnswer("jurisdiction", e.target.value)}
                  className="rounded-sm h-10"
                  placeholder="Type a jurisdiction"
                  data-testid="jurisdiction-input"
                />
              </div>
            </div>
          )}

          {q.type === "single" && (
            <div className="space-y-2">
              {q.options.map((opt) => {
                const active = currentValue === opt.value;
                return (
                  <button
                    key={opt.value} type="button"
                    onClick={() => setAnswer(q.id, opt.value)}
                    className={`w-full text-left flex items-center justify-between gap-4 border rounded-sm px-5 py-3.5 transition-colors ${active ? "border-[#C9A961] bg-amber-50/30 ring-1 ring-[#C9A961]/40" : "border-[#E1E6ED] hover:border-slate-300"}`}
                    data-testid={`opt-${q.id}-${opt.value}`}
                  >
                    <span className="text-sm text-[#0A1F44]">{opt.label}</span>
                    {active && <Check className="w-4 h-4 text-[#C9A961]" strokeWidth={2} />}
                  </button>
                );
              })}
            </div>
          )}

          {q.type === "multi" && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {q.options.map((opt) => {
                const active = Array.isArray(currentValue) && currentValue.includes(opt.value);
                return (
                  <button
                    key={opt.value} type="button"
                    onClick={() => toggleMulti(q.id, opt.value)}
                    className={`text-left flex items-center justify-between gap-3 border rounded-sm px-4 py-3 transition-colors ${active ? "border-[#C9A961] bg-amber-50/30 ring-1 ring-[#C9A961]/40" : "border-[#E1E6ED] hover:border-slate-300"}`}
                    data-testid={`opt-${q.id}-${opt.value}`}
                  >
                    <span className="text-sm text-[#0A1F44]">{opt.label}</span>
                    <div className={`w-4 h-4 border rounded-sm flex items-center justify-center ${active ? "bg-[#C9A961] border-[#C9A961]" : "border-slate-300"}`}>
                      {active && <Check className="w-3 h-3 text-[#0A1F44]" strokeWidth={2.5} />}
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        <div className="flex items-center justify-between mt-8">
          <Button
            variant="ghost"
            onClick={onBack} disabled={step <= 1}
            className="rounded-sm h-10 text-slate-500 hover:text-[#0A1F44]"
            data-testid="back-btn"
          >
            <ArrowLeft className="w-4 h-4 mr-2" /> Back
          </Button>
          <Button
            onClick={onNext} disabled={!canAdvance}
            className="bg-[#0A1F44] hover:bg-[#0E2958] rounded-sm h-10 px-6 group"
            data-testid="next-btn"
          >
            {step === TOTAL_QUESTIONS ? "Review" : "Next"}
            <ArrowRight className="w-4 h-4 ml-2 group-hover:translate-x-0.5 transition-transform" />
          </Button>
        </div>
      </div>
    </AppShell>
  );
}
