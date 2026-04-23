import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import AppShell from "@/components/layout/AppShell";
import { useAuth } from "@/contexts/AuthContext";
import { api, apiErrorMessage } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ArrowRight, Landmark, Briefcase } from "lucide-react";
import { toast } from "sonner";

const TYPES = [
  { value: "ned_personal", title: "NED personal board", desc: "A board you serve on as a non-executive director (your own context).", icon: Landmark },
  { value: "executive_personal", title: "Executive personal", desc: "Your own operating context. Data belongs to you.", icon: Briefcase },
];

export default function NewContext() {
  const [name, setName] = useState("");
  const [type, setType] = useState("executive_personal");
  const [industry, setIndustry] = useState("");
  const [jurisdiction, setJurisdiction] = useState("");
  const [busy, setBusy] = useState(false);
  const { refreshContexts, switchContext } = useAuth();
  const navigate = useNavigate();

  const submit = async (e) => {
    e.preventDefault();
    if (!name.trim()) return;
    setBusy(true);
    try {
      const { data } = await api.post("/contexts", {
        name: name.trim(), type,
        industry: industry || undefined,
        jurisdiction: jurisdiction || undefined,
      });
      await refreshContexts(); switchContext(data.id);
      toast.success(`${data.name} created`);
      navigate("/onboarding");
    } catch (err) { toast.error(apiErrorMessage(err)); }
    finally { setBusy(false); }
  };

  return (
    <AppShell>
      <div className="p-8 max-w-2xl mx-auto">
        <div className="mb-8">
          <p className="akki-overline mb-2">Add a context</p>
          <h1 className="text-3xl font-light tracking-tight text-[var(--ink)] mb-2">
            New context
          </h1>
          <p className="text-sm text-slate-500">
            Each context is isolated — data, signals, members, and briefings stay within it. Sponsored contexts (provisioned by an organisation) unlock at M4.
          </p>
        </div>
        <form onSubmit={submit} className="bg-white border border-[#E1E6ED] rounded-sm p-8 space-y-6" data-testid="new-context-form">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {TYPES.map((t) => {
              const I = t.icon;
              const active = type === t.value;
              return (
                <button
                  type="button" key={t.value}
                  onClick={() => setType(t.value)}
                  className={`text-left border rounded-sm p-5 transition-colors ${active ? "border-[var(--accent)] bg-amber-50/40 ring-1 ring-[var(--accent)]/40" : "border-[#E1E6ED] hover:border-slate-300"}`}
                  data-testid={`context-type-${t.value}`}
                >
                  <I className={`w-5 h-5 mb-3 ${active ? "text-[var(--accent)]" : "text-slate-400"}`} strokeWidth={1.6} />
                  <p className="text-sm font-medium text-[var(--ink)] mb-1">{t.title}</p>
                  <p className="text-xs text-slate-500 leading-relaxed">{t.desc}</p>
                </button>
              );
            })}
          </div>

          <div className="space-y-2">
            <Label className="text-xs uppercase tracking-wider text-slate-500 font-semibold">Context name</Label>
            <Input value={name} onChange={(e) => setName(e.target.value)} required className="rounded-sm h-10" placeholder="e.g. Stanbic Retail Banking" data-testid="new-context-name-input" />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label className="text-xs uppercase tracking-wider text-slate-500 font-semibold">Industry (optional)</Label>
              <Input value={industry} onChange={(e) => setIndustry(e.target.value)} className="rounded-sm h-10" placeholder="Banking, Retail, Fintech…" data-testid="new-context-industry-input" />
            </div>
            <div className="space-y-2">
              <Label className="text-xs uppercase tracking-wider text-slate-500 font-semibold">Jurisdiction (optional)</Label>
              <Input value={jurisdiction} onChange={(e) => setJurisdiction(e.target.value)} className="rounded-sm h-10" placeholder="Kenya · Nigeria · Pan-African" data-testid="new-context-jurisdiction-input" />
            </div>
          </div>
          <Button type="submit" disabled={busy || !name.trim()} className="bg-[var(--ink)] hover:bg-[#0E2958] rounded-sm h-10 group" data-testid="new-context-submit-btn">
            {busy ? "Creating…" : "Create context"}
            {!busy && <ArrowRight className="w-4 h-4 ml-2 group-hover:translate-x-0.5 transition-transform" />}
          </Button>
        </form>
      </div>
    </AppShell>
  );
}
