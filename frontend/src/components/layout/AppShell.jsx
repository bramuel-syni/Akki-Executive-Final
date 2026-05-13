/**
 * AppShell — Chunk 6.5 (2026-05-13) refactor.
 *
 * Outer authenticated layout. Two-column flexbox:
 *
 *   ┌──────────────────────────────────────────────────────┐
 *   │            │              TopBar (64px sticky)        │
 *   │  LeftRail  ├──────────────────────────────────────────┤
 *   │  (sticky)  │   main content (children)                │
 *   │            │                                          │
 *   │            ├──────────────────────────────────────────┤
 *   │            │   trust footer                           │
 *   └──────────────────────────────────────────────────────┘
 *
 * The previous shell rendered TWO header rows (logo header + primary
 * 8-tab nav) plus a giant legacy left rail guarded behind `false &&`.
 * Both are gone. The single source of truth for navigation is now
 * `<LeftRail />`; the slim `<TopBar />` only carries page-level chrome
 * (breadcrumb / search / bell / add-doc / help / avatar).
 *
 * Below 1100px the LeftRail auto-collapses to icon-only width (64px).
 * Below 768px (md) the LeftRail hides entirely; the avatar menu and
 * a mobile drawer (rendered here) carry the same navigation links so
 * tablet/phone users aren't stranded.
 *
 * All the previous global-modal mounts (UniversalSearch, Confirm
 * Context Switch, Company Switcher, Upload, Trust, Keyboard Help,
 * Context Switch, Sponsored banner, MFA nudge, Role mismatch banner)
 * stay mounted here — they pre-date Chunk 6.5 and are correctly
 * scoped to the shell.
 */
import React, { useEffect, useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import {
  Settings, LogOut, ShieldCheck, Menu, X,
  Home, Send, Presentation, BookOpenCheck, MessageCircle, Activity,
  Sparkles, GraduationCap, HelpCircle,
} from "lucide-react";
import UploadModal from "@/components/upload/UploadModal";
import { isSponsoredContext } from "@/lib/sponsorship";
import TrustPanel from "@/components/governance/TrustPanel";
import ContextSwitchModal from "@/components/layout/ContextSwitchModal";
import useKeyboardShortcuts from "@/hooks/useKeyboardShortcuts";
import KeyboardHelp from "@/components/layout/KeyboardHelp";
import UniversalSearchDialog from "@/components/search/UniversalSearchDialog";
import ConfirmContextSwitchModal from "@/components/search/ConfirmContextSwitchModal";
import CompanySwitcherDialog from "@/components/layout/CompanySwitcherDialog";

// Chunk 6.5 — new shell primitives.
import LeftRail from "@/components/shell/LeftRail";
import TopBar from "@/components/shell/TopBar";


// Mobile drawer link list (same 9 modules as the LeftRail).
const MOBILE_MODULES = [
  { to: "/app",               label: "Home",             icon: Home,            end: true },
  { to: "/app/cycle",         label: "Cycle Manager",    icon: Send },
  { to: "/app/work-studio",   label: "Work Studio",      icon: Presentation },
  { to: "/app/workspace",     label: "Document Journal", icon: BookOpenCheck },
  { to: "/app/chat",          label: "Akki Chat",        icon: MessageCircle },
  { to: "/app/monitor",       label: "Monitor",          icon: Activity },
  { to: "/app/pulse",         label: "Pulse",            icon: Sparkles },
  { to: "/app/learn",         label: "Learn",            icon: GraduationCap },
  { to: "/app/questions",     label: "Questions",        icon: HelpCircle },
];


export default function AppShell({ children }) {
  const {
    account, activeContext, contexts, switchContext, logout,
    activeRole, availableRoles, switchRole,
  } = useAuth();
  const navigate = useNavigate();

  const [trustOpen, setTrustOpen] = useState(false);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [searchPending, setSearchPending] = useState(null);
  const [helpOpen, setHelpOpen] = useState(false);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  // Global event listeners (carried over from the pre-Chunk-6.5 shell).
  useEffect(() => {
    const handler = () => setTrustOpen(true);
    window.addEventListener("akki:open-trust-panel", handler);
    return () => window.removeEventListener("akki:open-trust-panel", handler);
  }, []);

  useEffect(() => {
    const onOpenUpload = () => setUploadOpen(true);
    window.addEventListener("akki:open-upload-modal", onOpenUpload);
    return () => window.removeEventListener("akki:open-upload-modal", onOpenUpload);
  }, []);

  useKeyboardShortcuts({ openHelp: () => setHelpOpen(true) });

  const mismatched =
    activeRole && activeContext?.my_role &&
    activeRole !== activeContext.my_role &&
    (activeRole === "ned" || activeRole === "executive") &&
    (activeContext.my_role === "ned" || activeContext.my_role === "executive");

  const mfaOwnerNudge = account && !account.mfa_enabled &&
    activeContext && activeContext.my_sub_role === "admin";

  const isSponsored = isSponsoredContext(activeContext);

  return (
    <div className="min-h-screen flex bg-[var(--cream)]" data-testid="app-shell">
      <LeftRail />

      {/* Right column: top bar + main + footer. min-w-0 so long
          inner content (e.g. wide tables) doesn't blow out the flex. */}
      <div className="flex flex-col flex-1 min-w-0">
        <TopBar
          onOpenUpload={() => setUploadOpen(true)}
          onOpenHelp={() => setHelpOpen(true)}
          onOpenTrust={() => setTrustOpen(true)}
        />

        {/* Mobile-only nav trigger row — the LeftRail is hidden below md;
            tap the menu to open a slide-out drawer with the same 9
            modules. Visible only below md to avoid duplicating the
            rail's affordances on tablet+. */}
        <button
          type="button"
          onClick={() => setMobileNavOpen(true)}
          className="md:hidden inline-flex items-center justify-center gap-2 self-start ml-4 mt-2 mb-1 px-3 py-1.5 text-[12.5px] text-[var(--ink)] bg-[var(--cream-deep)] hover:bg-[var(--cream-deep)]/80 rounded-md transition-colors"
          aria-label="Open navigation"
          data-testid="mobile-nav-trigger"
        >
          <Menu className="w-4 h-4" strokeWidth={1.7} />
          Menu
        </button>

        {/* Persistent inline banners (kept from the legacy shell). */}
        {mfaOwnerNudge && (
          <div
            className="flex items-center justify-between px-8 py-2.5 bg-amber-50/70 border-b border-amber-200 text-amber-900 text-xs"
            data-testid="mfa-owner-nudge"
          >
            <span>
              <strong className="font-semibold">Security recommended:</strong> Enable MFA to protect your account and this context.
            </span>
            <Button
              size="sm" variant="outline"
              className="rounded-sm h-7 border-amber-300 text-amber-900 hover:bg-amber-100"
              onClick={() => navigate("/app/security")}
              data-testid="enable-mfa-nudge-btn"
            >
              Enable MFA
            </Button>
          </div>
        )}
        {mismatched && (
          <div
            className="flex items-center gap-3 px-8 py-2 bg-[var(--ink)]/5 border-b border-[var(--ink)]/20 text-xs text-[var(--ink)]"
            data-testid="role-mismatch-banner"
          >
            <span className="akki-overline">Heads up</span>
            <span className="text-slate-600">
              You&apos;re acting as <strong>{activeRole}</strong> but <strong>{activeContext.name}</strong> is a <strong>{activeContext.my_role === "ned" ? "NED" : "Executive"}</strong> context.
            </span>
            <button
              type="button"
              onClick={() => {
                const target = activeContext.my_role;
                switchRole(target);
                toast.success(`Now acting as ${target === "ned" ? "NED" : "Executive"} on ${activeContext.name}.`);
              }}
              className="ml-auto inline-flex items-center gap-1.5 px-3 py-1 text-[11.5px] font-medium bg-[var(--chrome)] text-white hover:bg-[var(--chrome)]/90 rounded-sm transition-colors"
              data-testid="role-mismatch-fix-btn"
            >
              Act as {activeContext.my_role === "ned" ? "NED" : "Executive"}
            </button>
          </div>
        )}
        {isSponsored && (
          <div
            className="flex items-center gap-2 px-8 py-2 bg-[var(--ink)]/5 border-b border-[var(--accent)]/30 text-xs text-[var(--muted)]"
            data-testid="sponsored-context-banner"
          >
            <span>Sponsored. Your data stays with the sponsoring company.</span>
          </div>
        )}

        <main className="flex-1 min-w-0 flex flex-col" data-testid="app-shell-main">
          {children}
        </main>

        {/* Trust footer — unchanged from pre-Chunk-6.5. */}
        <footer
          className="border-t border-[var(--rule)] bg-[var(--cream-deep)]/60 px-8 py-3 mt-auto flex flex-wrap items-center gap-x-5 gap-y-1 text-[10.5px] text-[var(--muted)] font-mono uppercase tracking-wider"
          data-testid="trust-footer"
        >
          <span className="inline-flex items-center gap-1.5 text-[var(--deep)]">
            <ShieldCheck className="w-3 h-3 text-[var(--chrome)]" strokeWidth={2} />
            Synisense-shielded
          </span>
          <span>· Your data never leaves this account</span>
          <span className="hidden md:inline">· Every signal cites its source</span>
          <button
            type="button"
            onClick={() => navigate("/app/settings?tab=trust")}
            className="ml-auto hover:text-[var(--ink)] transition-colors cursor-pointer bg-transparent border-0 p-0 m-0 font-mono uppercase tracking-wider text-[10.5px] text-[var(--muted)]"
            data-testid="trust-footer-link"
          >
            Trust centre →
          </button>
        </footer>
      </div>

      {/* Mobile nav drawer — only visible below md. */}
      {mobileNavOpen && (
        <div className="fixed inset-0 z-50 md:hidden" data-testid="mobile-nav-drawer">
          <div
            className="absolute inset-0 bg-[var(--ink)]/30"
            onClick={() => setMobileNavOpen(false)}
          />
          <aside className="absolute left-0 top-0 bottom-0 w-[280px] bg-[var(--cream)] border-r border-[var(--rule)] py-4 px-2 flex flex-col">
            <div className="flex items-center justify-between px-3 pb-2 mb-2 border-b border-[var(--rule)]">
              <p className="akki-overline">Navigation</p>
              <button
                type="button"
                onClick={() => setMobileNavOpen(false)}
                aria-label="Close navigation"
                className="w-8 h-8 inline-flex items-center justify-center text-[var(--muted)] hover:text-[var(--ink)] hover:bg-[var(--cream-deep)] rounded-md"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            {MOBILE_MODULES.map((n) => {
              const Icon = n.icon;
              return (
                <NavLink
                  key={n.to}
                  to={n.to}
                  end={n.end}
                  onClick={() => setMobileNavOpen(false)}
                  className={({ isActive }) =>
                    `akki-serif px-4 py-3 text-[14px] rounded-md mx-1 transition-colors border-l-2 flex items-center gap-2 ${
                      isActive
                        ? "border-[var(--accent)] text-[var(--ink)] bg-[var(--cream-deep)]/40 font-medium"
                        : "border-transparent text-[var(--deep)] hover:bg-[var(--cream-deep)]/40 hover:text-[var(--ink)]"
                    }`
                  }
                  data-testid={`mobile-nav-${n.label.toLowerCase().replace(/\s+/g, "-")}`}
                >
                  <Icon className="w-4 h-4" strokeWidth={1.7} /> {n.label}
                </NavLink>
              );
            })}
            <div className="mt-auto pt-3 border-t border-[var(--rule)] px-3">
              <button
                type="button"
                onClick={() => { setMobileNavOpen(false); navigate("/app/settings"); }}
                className="w-full text-left text-[13px] text-[var(--deep)] hover:text-[var(--ink)] py-2 inline-flex items-center gap-2"
              >
                <Settings className="w-4 h-4" /> Settings
              </button>
              <button
                type="button"
                onClick={async () => { setMobileNavOpen(false); await logout(); navigate("/signin"); }}
                className="w-full text-left text-[13px] text-red-600 hover:text-red-700 py-2 inline-flex items-center gap-2"
              >
                <LogOut className="w-4 h-4" /> Sign out
              </button>
            </div>
          </aside>
        </div>
      )}

      {/* Global modal mounts (unchanged from pre-Chunk-6.5). */}
      <UniversalSearchDialog onCrossContextRequest={(row) => setSearchPending({
        from_context_id: activeContext?.id,
        from_context_name: activeContext?.name,
        to_context_id: row.context_id,
        to_context_name: row.context_name,
        surface: row.surface,
        result_id: row.id,
        deep_link: row.deep_link,
        type: row.type,
      })} />
      <ConfirmContextSwitchModal pending={searchPending} onClose={() => setSearchPending(null)} />
      <CompanySwitcherDialog />

      <UploadModal
        open={uploadOpen}
        onClose={() => setUploadOpen(false)}
        onUploaded={(doc) => {
          toast.success("Added to your Document Journal.");
          window.dispatchEvent(new CustomEvent("akki:document-uploaded"));
          if (doc?.id) navigate(`/app/documents/${doc.id}`);
        }}
      />

      <TrustPanel open={trustOpen} onOpenChange={setTrustOpen} />
      <KeyboardHelp open={helpOpen} onOpenChange={setHelpOpen} />
      <ContextSwitchModal />
    </div>
  );
}
