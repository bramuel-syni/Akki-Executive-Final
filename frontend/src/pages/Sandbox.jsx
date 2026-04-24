/**
 * Sandbox — pre-auth evaluation intake.
 *
 * 4 questions. Warm editorial feel. No chrome from the signed-in app; this
 * is the conversion moment. On submit we POST to /api/sandbox/generate and
 * navigate to /sandbox/generating/:session_id to watch the 10-stage narrative.
 */
import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import axios from "axios";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { toast } from "sonner";
import { Landmark, Briefcase, Layers, ArrowRight, Loader2 } from "lucide-react";

const API_BASE = `${process.env.REACT_APP_BACKEND_URL}/api`;

const SECTORS = [
  { value: "financial_services", label: "Financial services (banking, asset mgmt, insurance, fintech)" },
  { value: "saas",            label: "SaaS / Technology" },
  { value: "logistics",       label: "Logistics and supply chain" },
  { value: "healthcare",      label: "Healthcare" },
  { value: "manufacturing",   label: "Manufacturing" },
  { value: "retail",          label: "Retail and consumer" },
  { value: "real_estate",     label: "Real estate and construction" },
  { value: "other",           label: "Other" },
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
  { value: "ned", label: "NED", icon: Landmark,  sub: "Non-executive director / board member" },
  { value: "executive", label: "Executive", icon: Briefcase, sub: "CEO, CFO, operating executive" },
  { value: "both", label: "Both", icon: Layers, sub: "I serve on boards and run a business" },
];

export default function Sandbox() {
  const navigate = useNavigate();
  const [companyName, setCompanyName] = useState("");
  const [sector, setSector] = useState("");
  const [role, setRole] = useState("");
  const [region, setRegion] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const canSubmit = companyName.trim().length > 0 && sector && role && region && !submitting;

  const onSubmit = async (e) => {
    e?.preventDefault?.();
    if (!canSubmit) return;
    setSubmitting(true);
    try {
      const { data } = await axios.post(`${API_BASE}/sandbox/generate`, {
        company_name: companyName.trim(), sector, role, region,
      });
      navigate(`/sandbox/generating/${data.session_id}`);
    } catch (err) {
      setSubmitting(false);
      toast.error(err.response?.data?.detail || "We couldn't start your sandbox. Try again.");
    }
  };

  return (
    <div className="min-h-screen bg-[var(--cream)] flex flex-col">
      {/* Tiny top bar */}
      <header className="px-8 py-5 flex items-center justify-between border-b border-[var(--rule)]">
        <a href="/" className="akki-brand text-[18px] text-[var(--ink)]">AKKI</a>
        <a href="/signin" className="text-[13px] text-[var(--muted)] hover:text-[var(--ink)] transition-colors" data-testid="sandbox-link-signin">
          Already have an account? <span className="underline-offset-2 hover:underline">Sign in</span>
        </a>
      </header>

      <main className="flex-1 flex items-start md:items-center justify-center px-6 py-10 md:py-16">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: [0.2, 0.8, 0.2, 1] }}
          className="max-w-[560px] w-full"
        >
          <p className="akki-overline mb-3">Sandbox · 60 seconds · no sign-up</p>
          <h1
            className="akki-serif text-[30px] md:text-[36px] leading-[1.12] text-[var(--ink)] mb-3"
            data-testid="sandbox-hero-title"
          >
            Try AKKI on data that looks like yours.
          </h1>
          <p className="text-[15px] text-[var(--muted)] leading-relaxed mb-10 max-w-[460px]">
            Four questions. AKKI will build you a fictional company mirroring your sector and region,
            then read the pack and surface observations you can explore for 14 days.
          </p>

          <form onSubmit={onSubmit} className="space-y-9" data-testid="sandbox-intake-form">
            {/* Q1 — company name */}
            <div>
              <label className="akki-overline mb-2 block">
                Q1 · What company do you lead or serve on the board of?
              </label>
              <Input
                value={companyName}
                onChange={(e) => setCompanyName(e.target.value)}
                placeholder="e.g., Acme Banking Group"
                maxLength={120}
                autoFocus
                className="bg-white rounded-md h-12 text-[16px] border-[var(--rule)] focus:border-[var(--accent)]"
                data-testid="sandbox-q1-company"
              />
            </div>

            {/* Q2 — sector */}
            <div>
              <label className="akki-overline mb-2 block">Q2 · What sector?</label>
              <Select value={sector} onValueChange={setSector}>
                <SelectTrigger
                  className="bg-white rounded-md h-12 text-[15px] border-[var(--rule)]"
                  data-testid="sandbox-q2-sector"
                >
                  <SelectValue placeholder="Choose the sector closest to your work" />
                </SelectTrigger>
                <SelectContent position="popper" side="bottom" align="start" sideOffset={4}>
                  {SECTORS.map((s) => (
                    <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Q3 — role (visual cards) */}
            <div>
              <label className="akki-overline mb-2 block">Q3 · What is your role?</label>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3" data-testid="sandbox-q3-role-cards">
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
                      data-testid={`sandbox-role-${r.value}`}
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
                <SelectTrigger
                  className="bg-white rounded-md h-12 text-[15px] border-[var(--rule)]"
                  data-testid="sandbox-q4-region"
                >
                  <SelectValue placeholder="Pick a region" />
                </SelectTrigger>
                <SelectContent position="popper" side="bottom" align="start" sideOffset={4}>
                  {REGIONS.map((r) => (
                    <SelectItem key={r.value} value={r.value}>{r.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <Button
              type="submit"
              disabled={!canSubmit}
              className="w-full bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white rounded-md h-12 text-[15px] font-medium disabled:opacity-50 disabled:cursor-not-allowed"
              data-testid="sandbox-submit-btn"
            >
              {submitting ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : null}
              {submitting ? "Starting your sandbox…" : "Create my sandbox"}
              {!submitting && <ArrowRight className="w-4 h-4 ml-2" />}
            </Button>

            <p className="text-[12.5px] text-[var(--muted)] leading-relaxed">
              This creates a fictional environment with mock data. No sign-up needed. Explore for up to 14 days.
            </p>
          </form>
        </motion.div>
      </main>
    </div>
  );
}
