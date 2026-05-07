/**
 * NewWorkspace ("Add company") — same 5-question editorial journey as the
 * public Sandbox page. The product feedback was explicit: "There is no good
 * reason for these to be different flows."
 *
 * On submit we POST /api/sandbox/contexts/seeded which provisions a real
 * (non-sandbox) context, seeds it with the matching sector template, then
 * we switch into it. The home page picks up the tutorial card from there.
 */
import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import AppShell from "@/components/layout/AppShell";
import { useAuth } from "@/contexts/AuthContext";
import { api, apiErrorMessage } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  ArrowRight, Landmark, Briefcase, Layers, Loader2, ArrowLeft,
} from "lucide-react";
import { toast } from "sonner";

const SECTORS = [
  { value: "financial_services", label: "Financial services (banking, asset mgmt, insurance, fintech)" },
  { value: "saas",            label: "SaaS / Technology" },
  { value: "logistics",       label: "Logistics and supply chain" },
  { value: "healthcare",      label: "Healthcare" },
  { value: "manufacturing",   label: "Manufacturing" },
  { value: "retail",          label: "Retail and consumer" },
  { value: "real_estate",     label: "Real estate and construction" },
  { value: "other",           label: "Other (I'll describe it)" },
];

const REGIONS = [
  { value: "east_africa",     label: "East Africa" },
  { value: "west_africa",     label: "West Africa" },
  { value: "southern_africa", label: "Southern Africa" },
  { value: "north_africa",    label: "North Africa" },
  { value: "europe",          label: "Europe" },
  { value: "north_america",   label: "North America" },
  { value: "middle_east",     label: "Middle East" },
  { value: "asia_pacific",    label: "Asia-Pacific" },
];

const ROLES = [
  { value: "ned",       label: "NED",       icon: Landmark,  sub: "Non-executive director / board member" },
  { value: "executive", label: "Executive", icon: Briefcase, sub: "CEO, CFO, operating executive" },
  { value: "both",      label: "Both",      icon: Layers,    sub: "I serve on boards and run a business" },
];

const TRIGGER_CLS =
  "bg-white rounded-md h-12 text-[15px] border-[var(--rule)] " +
  "text-[var(--ink)] data-[placeholder]:text-[var(--muted)] " +
  "focus:border-[var(--accent)]";

export default function NewWorkspace() {
  const navigate = useNavigate();
  const { refreshContexts, switchContext } = useAuth();

  const [companyName, setCompanyName] = useState("");
  const [sector, setSector] = useState("");
  const [otherSectorName, setOtherSectorName] = useState("");
  const [otherSectorDesc, setOtherSectorDesc] = useState("");
  const [role, setRole] = useState("");
  const [region, setRegion] = useState("");
  const [objective, setObjective] = useState("");
  const [seedData, setSeedData] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  const isOther = sector === "other";
  const otherOk = !isOther || (otherSectorName.trim().length > 0 && otherSectorDesc.trim().length > 0);
  const canSubmit =
    companyName.trim().length > 0 &&
    sector && role && region &&
    objective.trim().length >= 10 &&
    otherOk &&
    !submitting;

  const onSubmit = async (e) => {
    e?.preventDefault?.();
    if (!canSubmit) return;
    setSubmitting(true);
    try {
      const { data } = await api.post(`/sandbox/contexts/seeded`, {
        company_name: companyName.trim(),
        sector,
        role,
        region,
        objective: objective.trim(),
        other_sector_name: isOther ? otherSectorName.trim() : null,
        other_sector_description: isOther ? otherSectorDesc.trim() : null,
        seed_data: seedData,
      });
      await refreshContexts();
      if (data?.context_id) switchContext(data.context_id);
      toast.success(`${companyName.trim()} created`);
      navigate("/app");
    } catch (err) {
      setSubmitting(false);
      toast.error(apiErrorMessage(err));
    }
  };

  return (
    <AppShell>
      <div className="min-h-[calc(100vh-4rem)] bg-[var(--cream)]">
        <div className="akki-w-narrow px-6 py-12 md:py-16">
          <button
            onClick={() => navigate(-1)}
            className="text-[12.5px] text-[var(--muted)] hover:text-[var(--ink)] inline-flex items-center gap-1.5 mb-6"
            data-testid="newctx-back"
          >
            <ArrowLeft className="w-3.5 h-3.5" /> Back
          </button>

          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, ease: [0.2, 0.8, 0.2, 1] }}
          >
            <p className="akki-overline mb-3">Add company · 60 seconds</p>
            <h1
              className="akki-serif text-[30px] md:text-[36px] leading-[1.12] text-[var(--ink)] mb-3"
              data-testid="newctx-hero-title"
            >
              Add a company AKKI can read for you.
            </h1>
            <p className="text-[15px] text-[var(--muted)] leading-relaxed mb-10 max-w-[480px]">
              Five questions. AKKI builds a starter pack mirroring the sector and region you choose,
              then waits for your real documents.
            </p>

            <form onSubmit={onSubmit} className="space-y-9" data-testid="newctx-intake-form">
              {/* Q1 — company name */}
              <div>
                <label className="akki-overline mb-2 block">
                  Q1 · Company name
                </label>
                <Input
                  value={companyName}
                  onChange={(e) => setCompanyName(e.target.value)}
                  placeholder="e.g., Acme Banking Group"
                  maxLength={120}
                  autoFocus
                  className="bg-white rounded-md h-12 text-[16px] text-[var(--ink)] placeholder:text-[var(--muted)] border-[var(--rule)] focus:border-[var(--accent)]"
                  data-testid="newctx-q1-company"
                />
              </div>

              {/* Q2 — sector */}
              <div>
                <label className="akki-overline mb-2 block">Q2 · Sector</label>
                <Select value={sector} onValueChange={setSector}>
                  <SelectTrigger className={TRIGGER_CLS} data-testid="newctx-q2-sector">
                    <SelectValue placeholder="Choose the closest sector" />
                  </SelectTrigger>
                  <SelectContent className="max-h-[360px]">
                    {SECTORS.map((s) => (
                      <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>

                <AnimatePresence initial={false}>
                  {isOther && (
                    <motion.div
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: "auto" }}
                      exit={{ opacity: 0, height: 0 }}
                      transition={{ duration: 0.25 }}
                      className="overflow-hidden"
                      data-testid="newctx-other-sector-block"
                    >
                      <div className="pt-4 space-y-4">
                        <div>
                          <label className="akki-overline mb-2 block text-[10px]">Name your sector</label>
                          <Input
                            value={otherSectorName}
                            onChange={(e) => setOtherSectorName(e.target.value)}
                            placeholder="e.g., Renewable energy, Education, Mining"
                            maxLength={80}
                            className="bg-white rounded-md h-11 text-[15px] text-[var(--ink)] placeholder:text-[var(--muted)] border-[var(--rule)] focus:border-[var(--accent)]"
                            data-testid="newctx-other-sector-name"
                          />
                        </div>
                        <div>
                          <label className="akki-overline mb-2 block text-[10px]">What does the company do?</label>
                          <Textarea
                            value={otherSectorDesc}
                            onChange={(e) => setOtherSectorDesc(e.target.value)}
                            placeholder="Two lines is enough — what you sell, who pays, what regulators care about."
                            rows={3}
                            maxLength={400}
                            className="bg-white rounded-md text-[14px] text-[var(--ink)] placeholder:text-[var(--muted)] border-[var(--rule)] focus:border-[var(--accent)] resize-none"
                            data-testid="newctx-other-sector-desc"
                          />
                        </div>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>

              {/* Q3 — role */}
              <div>
                <label className="akki-overline mb-2 block">Q3 · Your role on this company</label>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3" data-testid="newctx-q3-role-cards">
                  {ROLES.map((r) => {
                    const Icon = r.icon;
                    const active = role === r.value;
                    return (
                      <motion.button
                        key={r.value}
                        type="button"
                        onClick={() => setRole(r.value)}
                        whileHover={{ y: -2 }}
                        className={`text-left p-3 rounded-md border bg-white transition-colors ${
                          active
                            ? "border-[var(--accent)] ring-1 ring-[var(--accent)]"
                            : "border-[var(--rule)] hover:border-[var(--accent)]/50"
                        }`}
                        data-testid={`newctx-role-${r.value}`}
                      >
                        <Icon className={`w-4 h-4 mb-2 ${active ? "text-[var(--accent)]" : "text-[var(--muted)]"}`} strokeWidth={1.8} />
                        <p className="akki-serif text-[16px] text-[var(--ink)]">{r.label}</p>
                        <p className="text-[11.5px] text-[var(--muted)] mt-0.5 leading-snug">{r.sub}</p>
                      </motion.button>
                    );
                  })}
                </div>
              </div>

              {/* Q4 — region */}
              <div>
                <label className="akki-overline mb-2 block">Q4 · Where is the business based?</label>
                <Select value={region} onValueChange={setRegion}>
                  <SelectTrigger className={TRIGGER_CLS} data-testid="newctx-q4-region">
                    <SelectValue placeholder="Pick a region" />
                  </SelectTrigger>
                  <SelectContent className="max-h-[400px]">
                    {REGIONS.map((r) => (
                      <SelectItem key={r.value} value={r.value}>{r.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Q5 — objective */}
              <div>
                <label className="akki-overline mb-2 block">
                  Q5 · What outcome would make this company worth tracking here?
                </label>
                <Textarea
                  value={objective}
                  onChange={(e) => setObjective(e.target.value)}
                  placeholder="e.g., 'Spot the soft spots in our CFO's quarterly memo before the audit committee meets.'"
                  rows={3}
                  maxLength={400}
                  className="bg-white rounded-md text-[14px] text-[var(--ink)] placeholder:text-[var(--muted)] border-[var(--rule)] focus:border-[var(--accent)] resize-none"
                  data-testid="newctx-q5-objective"
                />
                <p className="text-[11.5px] text-[var(--muted)] italic mt-1.5">
                  We use this to shape the first brief — and to measure later whether AKKI delivered on it.
                </p>
              </div>

              {/* Seed toggle */}
              <label
                className="flex items-start gap-3 cursor-pointer text-[13px] text-[var(--deep)] bg-[var(--cream-deep)]/40 border border-[var(--rule)] rounded-md p-3"
                data-testid="newctx-seed-toggle"
              >
                <input
                  type="checkbox"
                  checked={seedData}
                  onChange={(e) => setSeedData(e.target.checked)}
                  className="mt-0.5 accent-[var(--accent)]"
                />
                <span className="leading-snug">
                  Seed a starter pack so the company isn't empty when I land.
                  <span className="block text-[var(--muted)] italic mt-0.5">
                    Sector-shaped board pack, signals, and a draft briefing — replaceable by your real documents.
                  </span>
                </span>
              </label>

              <Button
                type="submit"
                disabled={!canSubmit}
                className="w-full bg-[var(--chrome)] hover:bg-[var(--chrome)]/90 text-white rounded-md h-12 text-[15px] font-medium disabled:opacity-50 disabled:cursor-not-allowed"
                data-testid="newctx-submit-btn"
              >
                {submitting ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : null}
                {submitting ? "Creating your company…" : "Create company"}
                {!submitting && <ArrowRight className="w-4 h-4 ml-2" />}
              </Button>
            </form>
          </motion.div>
        </div>
      </div>
    </AppShell>
  );
}
