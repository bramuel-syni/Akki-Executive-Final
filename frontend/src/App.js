import React, { Suspense, lazy } from "react";
import "@/App.css";
import { BrowserRouter, Navigate, Route, Routes, useLocation, useParams } from "react-router-dom";
import { AuthProvider, useAuth } from "@/contexts/AuthContext";
import ProtectedRoute from "@/components/ProtectedRoute";
// R.followup.2 (2026-05-27) — page-level superadmin enforcement.
// Wraps every `/app/admin/*` and `/admin/*` route so a non-superadmin
// session can't even reach the page shell (data endpoints already
// enforce superadmin server-side; this is the second gate).
import SuperadminRoute from "@/components/SuperadminRoute";
import { Toaster } from "@/components/ui/sonner";

// Patch 18 — code-split.
// Public marketing landing + auth pages stay eagerly imported because
// they're the first impression and gating reduces useful interactivity
// on slow networks. Everything else (app routes, admin, sandbox, deep
// marketing pages) is lazy-loaded per route via React.lazy.
import WebsiteHome from "@/website/pages/Home";
import SignIn from "@/pages/SignIn";
import SignUp from "@/pages/SignUp";
import UpgradeModal from "@/components/depth/UpgradeModal";
import FeedbackWidget from "@/components/feedback/FeedbackWidget";
import Day16Banner from "@/components/cohort/Day16Banner";
// Phase Y (2026-05-27) — First-login onboarding briefs modal.
import OnboardingBriefsModal from "@/components/onboarding/OnboardingBriefsModal";
import SpecialAskModal from "@/components/cohort/SpecialAskModal";
import useTrialStatus from "@/hooks/useTrialStatus";

// -- Lazy: marketing deeper routes (rarely visited from cold start) ----------
const Landing = lazy(() => import("@/pages/Landing"));
const About = lazy(() => import("@/pages/marketing/About"));
const Features = lazy(() => import("@/pages/marketing/Features"));
const Security = lazy(() => import("@/pages/marketing/Security"));
const Plans = lazy(() => import("@/pages/marketing/Plans"));
const EnterpriseMarketing = lazy(() => import("@/pages/marketing/Enterprise"));
// EarlyAccess legacy marketing page — /early-access route now aliases to /cohort (Sprint M.5)
const Blog = lazy(() => import("@/pages/marketing/Blog"));
const BlogPost = lazy(() => import("@/pages/marketing/BlogPost"));
const BlogAdmin = lazy(() => import("@/pages/marketing/BlogAdmin"));
const WebsiteWhyAkki = lazy(() => import("@/website/pages/WhyAkki"));
const WebsiteWhatAkkiDoes = lazy(() => import("@/website/pages/WhatAkkiDoes"));
const WebsiteTrust = lazy(() => import("@/website/pages/Trust"));
const WebsiteCohort = lazy(() => import("@/website/pages/Cohort"));
const WebsiteWaitlist = lazy(() => import("@/website/pages/Waitlist"));
const WebsitePricing = lazy(() => import("@/website/pages/Pricing"));
const WebsiteAbout = lazy(() => import("@/website/pages/About"));
const WebsiteContact = lazy(() => import("@/website/pages/Contact"));
const WebsitePrivacy = lazy(() => import("@/website/pages/Privacy"));
const WebsiteTerms = lazy(() => import("@/website/pages/Terms"));
const WebsiteMethodology = lazy(() => import("@/website/pages/Methodology"));
const WebsiteExco360 = lazy(() => import("@/website/pages/Exco360"));
const WebsiteProductSolva = lazy(() => import("@/website/pages/product/Solva"));
const WebsiteProductChat = lazy(() => import("@/website/pages/product/AkkiChat"));
const WebsiteProductWorkStudio = lazy(() => import("@/website/pages/product/WorkStudio"));
const WebsiteProductCycle = lazy(() => import("@/website/pages/product/CycleManager"));
const WebsiteProductMonitor = lazy(() => import("@/website/pages/product/Monitor"));
const WebsiteProductPulse = lazy(() => import("@/website/pages/product/Pulse"));
const WebsiteProductJournal = lazy(() => import("@/website/pages/product/DocumentJournal"));
const TrustCenter = lazy(() => import("@/pages/TrustCenter"));  // H3
const WebsiteForExecutives = lazy(() => import("@/website/pages/ForExecutives"));
const WebsiteForExco = lazy(() => import("@/website/pages/ForExco"));
const WebsiteForNeds = lazy(() => import("@/website/pages/ForNeds"));
const WebsiteForOrganisations = lazy(() => import("@/website/pages/ForOrganisations"));

// -- Lazy: protected app routes ----------------------------------------------
const FirstSession = lazy(() => import("@/pages/FirstSession"));
const AppHome = lazy(() => import("@/pages/AppHome"));
// Phase R.5.a (2026-05-27) — Cohort console + Early access opt-in
const CohortConsole = lazy(() => import("@/pages/admin/CohortConsole"));
// Phase V (2026-05-27) — Admin user CRUD portal.
const AdminUsers = lazy(() => import("@/pages/admin/AdminUsers"));
// Phase P4.B (2026-02) — admin cohort applications surface.
const AdminCohortApplications = lazy(() => import("@/pages/admin/AdminCohortApplications"));
const AdminInbox = lazy(() => import("@/pages/admin/AdminInbox"));
// AA.followup.4 (2026-02 fork-resume) — Extraction Activity superadmin view.
const ExtractionsActivity = lazy(() => import("@/pages/admin/ExtractionsActivity"));
// Phase W (2026-02 fork-resume) — Multi-tenant org list view (superadmin).
const AdminTenants = lazy(() => import("@/pages/admin/AdminTenants"));
// Phase S (2026-05-27) — Password reset pages (public, no auth).
const ForgotPassword = lazy(() => import("@/pages/ForgotPassword"));
const ResetPassword  = lazy(() => import("@/pages/ResetPassword"));
// Phase U (2026-05-27) — OAuth callback handler.
const OAuthCallback  = lazy(() => import("@/pages/OAuthCallback"));
// Phase P2 D.2 (2026-02) — Public status page (no auth).
const StatusPage = lazy(() => import("@/pages/StatusPage"));
// Phase P2.1-4 (2026-02) — ErrorBoundary diagnostic test-throw route.
const ThrowDiagnostic = lazy(() => import("@/pages/ThrowDiagnostic"));
// Phase P4.D (2026-02) — Cohort magic-link landing page.
const WelcomePage = lazy(() => import("@/pages/WelcomePage"));
// C1-revised Phase A (2026-02) — First-login password-set page.
const SetPasswordRequired = lazy(() => import("@/pages/SetPasswordRequired"));
const CohortCopyEditor = lazy(() => import("@/pages/admin/CohortCopyEditor"));
const EarlyAccessOptIn = lazy(() => import("@/pages/EarlyAccessOptIn"));
const Questions = lazy(() => import("@/pages/Questions"));
const Workspace = lazy(() => import("@/pages/Workspace"));
const Activity = lazy(() => import("@/pages/Activity"));
// E.4 (2026-05-26) — ReadingView archived. The Universal Document
// Drawer (Phase E.3) is the canonical surface for reading documents.
// /app/documents/:id now redirects to /app/work-studio?doc_id=:id.
// See _archived/e4_doc_routes/.
const DailyReview = lazy(() => import("@/pages/DailyReview"));
const Learn = lazy(() => import("@/pages/Learn"));
const TenantSettings = lazy(() => import("@/pages/TenantSettings"));
const AccountSecurity = lazy(() => import("@/pages/AccountSecurity"));
const InviteAccept = lazy(() => import("@/pages/InviteAccept"));
const NewContext = lazy(() => import("@/pages/NewWorkspace"));
const NewsStub = lazy(() => import("@/pages/NewsStub"));
const Events = lazy(() => import("@/pages/Events"));
const Simulate = lazy(() => import("@/pages/Simulate"));
const LensRoom = lazy(() => import("@/pages/LensRoom"));
const Chat = lazy(() => import("@/pages/Chat"));
const ArchivedChats = lazy(() => import("@/pages/ArchivedChats"));
const InfluenceMap = lazy(() => import("@/pages/InfluenceMap"));
const SandboxApp = lazy(() => import("@/sandbox/SandboxApp"));
const Manage = lazy(() => import("@/pages/Manage"));
const HelpFeatures = lazy(() => import("@/pages/HelpFeatures"));  // Phase E — legacy /help (kept for /help-legacy)
const Wiki = lazy(() => import("@/pages/Wiki"));  // Phase P1 γ — wiki framework, replaces /help
const Enterprise = lazy(() => import("@/pages/Enterprise"));
const Decks = lazy(() => import("@/pages/Decks"));
const SolvaApp = lazy(() => import("@/pages/SolvaApp"));
const SolvaSession = lazy(() => import("@/pages/SolvaSession"));
const SolvaSessions = lazy(() => import("@/pages/SolvaSessions"));
// Phase E Sub-task A (2026-05-16) — Phase D session page wired at a
// distinct route so the legacy SolvaSession.jsx stays available for
// pre-Phase-D sessions until the migration in Phase E Sub-task F.
const SolvaPhaseDSession = lazy(() => import("@/pages/SolvaPhaseDSession"));
// Phase E Sub-task D (2026-05-16) — admin observability dashboard.
const SynisenseObservability = lazy(() => import("@/pages/SynisenseObservability"));
const Cycle = lazy(() => import("@/pages/Cycle"));
const CycleList = lazy(() => import("@/pages/cycle/CycleList"));
// Phase F.1 (2026-05-26) — Task Manager (rename of Cycle Manager UI).
// Canonical surface: /app/task-manager. /app/cycle remains as
// backwards-compat alias (renders the legacy CycleList listing).
const TaskManager = lazy(() => import("@/pages/TaskManager"));
// Phase F.5 (2026-05-26) — Contributor magic-link portal. PUBLIC route,
// no AppShell, no auth gate. Mounted at /contribute/:token.
const ContributorPortal = lazy(() => import("@/pages/ContributorPortal"));
// Phase F.6 (2026-05-26) — Account-scoped task activity full-page view.
const TaskManagerActivity = lazy(() => import("@/pages/TaskManagerActivity"));
// T5 (2026-05-25) — C7 Draft Journal + C8 Ready to Compile Journal.
const CycleDraftJournal = lazy(() => import("@/pages/cycle/CycleDraftJournal"));
const CycleReadyJournal = lazy(() => import("@/pages/cycle/CycleReadyJournal"));
const Monitor = lazy(() => import("@/pages/Monitor"));
const RespondToChecklist = lazy(() => import("@/pages/RespondToChecklist"));
const SharedArtefact = lazy(() => import("@/pages/SharedArtefact"));
const InboundQueue = lazy(() => import("@/pages/InboundQueue"));
const StudioComposerPage = lazy(() => import("@/pages/StudioComposerPage"));
const WorkStudio = lazy(() => import("@/pages/WorkStudio"));
const AnalyzeJournal = lazy(() => import("@/pages/AnalyzeJournal"));
// Phase Z (2026-05-27, Z-slice-4) — Canonical Documents Journal page.
const DocumentsPage = lazy(() => import("@/pages/DocumentsPage"));
// Phase E.2 (2026-05-26) — full-page Recent Activity surface.
const WorkStudioActivity = lazy(() => import("@/pages/WorkStudioActivity"));
const WorkStudioDocumentPage = lazy(() => import("@/pages/WorkStudioDocumentPage"));
const Pulse = lazy(() => import("@/pages/Pulse"));
const PulseIdeas = lazy(() => import("@/pages/PulseIdeas"));
const SearchResults = lazy(() => import("@/pages/SearchResults"));
const NedMeeting = lazy(() => import("@/pages/ned/NedMeeting"));
const NedCommittee = lazy(() => import("@/pages/ned/NedCommittee"));
const NedInbox = lazy(() => import("@/pages/ned/NedInbox"));
// Prepare page kept for back-compat (not in routes today but imported elsewhere)

// -- Lazy: admin (separate chunk) --------------------------------------------
const HealthDashboard = lazy(() => import("@/pages/admin/HealthDashboard"));
const SandboxKPI = lazy(() => import("@/pages/admin/SandboxKPI"));
const SignalKPI = lazy(() => import("@/pages/admin/SignalKPI"));
const LLMSpend = lazy(() => import("@/pages/admin/LLMSpend"));
const AuthEvents = lazy(() => import("@/pages/admin/AuthEvents"));
const AdminIndex = lazy(() => import("@/pages/admin/AdminIndex"));

// Phase H.5 route consolidation (2026-05-27) — `Home1` archived. All
// legacy portfolio entry routes (/app/portfolio, /app/companies,
// /app/contexts) collapse into `/app` (no-active-context branch of
// AppHome → ContextPortfolio).

function PublicOnlyRoute({ children, allowSandbox = false }) {
  const { account } = useAuth();
  if (account === null) return null;
  // Sandbox users must be allowed through to /signup so they can convert.
  // Phase H.5 (2026-05-27) — post-auth target collapsed to `/app`
  // (was `/app/portfolio` while Home1 was the canonical entry).
  // The AppHome dispatcher routes the no-active-context branch to
  // the new Portfolio Landing.
  if (account && !(allowSandbox && account.is_sandbox)) return <Navigate to="/app" replace />;
  return children;
}

/**
 * FirstSessionGuard — Phase 4 / Advisory 5.
 *
 * When a signed-in user hasn't completed (or skipped) First Session, every
 * /app/* route is short-circuited to /app/first-session. Three exceptions:
 *   · /app/first-session itself (the destination).
 *   · /app/settings/* (so users can fix email/password/MFA mid-flow).
 *   · /app/review (so the Daily Review badge remains clickable — though for
 *     a brand-new user the badge is unlikely to appear anyway).
 *
 * Grandfathered users (account.first_session.status === "skipped" applied on
 * first `/auth/me` for any account with a completed legacy context_object)
 * never hit the redirect.
 */
function FirstSessionGuard({ children }) {
  const { account } = useAuth();
  const location = useLocation();
  if (!account) return children; // unauth / loading — let ProtectedRoute handle
  const fs = account.first_session || { status: "not_started" };
  const done = fs.status === "completed" || fs.status === "skipped";
  if (done) return children;
  const path = location.pathname || "";
  const allowed =
    path === "/app/first-session" ||
    path.startsWith("/app/first-session/") ||
    path.startsWith("/app/settings") ||
    path === "/app/review" ||
    path === "/app/security";
  if (!allowed) {
    return <Navigate to="/app/first-session" replace />;
  }
  return children;
}

/**
 * SetPasswordGuard — C1-revised Phase A (2026-02).
 *
 * Authenticated guard. When the account row carries
 * `has_set_password === false` (strict bool), any /app/* destination
 * is short-circuited to `/auth/set-password`. Legacy accounts where
 * the flag is missing / null / true pass through (mirrors the server-
 * side gate in `services/first_login_password_set.py`).
 *
 * Co-resident with FirstSessionGuard inside <Gated>. Order matters:
 * the password-set step happens BEFORE the first-session wizard so a
 * cohort applicant lands on the password screen before the intake
 * questions (which would otherwise post and 428).
 */
function SetPasswordGuard({ children }) {
  const { account } = useAuth();
  const location = useLocation();
  if (!account) return children;
  if (account.has_set_password !== false) return children;
  return (
    <Navigate
      to="/auth/set-password"
      replace
      state={{ from: (location.pathname || "") + (location.search || "") }}
    />
  );
}

/** E.4 (2026-05-26) — /app/documents/:id redirects to the Universal
 *  Document Drawer (Phase E.3). The drawer mounts on /app/work-studio
 *  and listens for `?doc_id=` to open. Old bookmarks survive via this
 *  redirect.
 *  Archived: pages/ReadingView.jsx + components/reading/* + the two
 *  hooks (useDocumentParagraphs, useReadingScrollSync).
 *  See _archived/e4_doc_routes/.
 */
function DocumentRouteSwitch() {
  const { id } = useParams();
  return <Navigate to={`/app/work-studio?doc_id=${encodeURIComponent(id || "")}`} replace />;
}

function Gated({ children }) {
  return (
    <ProtectedRoute>
      <SetPasswordGuard>
        <FirstSessionGuard>
          <HardLockGuard>
            {/* Phase R.5.b (2026-05-27) — Day-16 soft-warning banner on top. */}
            <Day16Banner />
            {children}
            {/* Phase R.4 (2026-05-27) — Feedback widget on every gated surface. */}
            <FeedbackWidget />
            {/* Phase R.5.b.2 (2026-05-27) — Day-14 special-ask modal (surfaces conditionally). */}
            <SpecialAskModal />
            {/* Phase Y (2026-05-27) — First-login onboarding briefs (self-gates
                by `onboarding_briefs_shown_at == null` from the account row). */}
            <OnboardingBriefsModal />
          </HardLockGuard>
        </FirstSessionGuard>
      </SetPasswordGuard>
    </ProtectedRoute>
  );
}

/**
 * Phase R.5.a (2026-05-27) — Hard-lock guard.
 *
 * When `useTrialStatus().locked === true` (trial crossed Day 22),
 * force-redirect to /app/early-access-opt-in unless already there.
 */
function HardLockGuard({ children }) {
  const trial = useTrialStatus();
  const location = useLocation();
  if (trial.locked && !location.pathname.startsWith("/app/early-access-opt-in")) {
    return <Navigate to="/app/early-access-opt-in" replace />;
  }
  return children;
}

// Lazy fallback — intentionally invisible. Renders nothing during the
// per-chunk fetch (typically <300ms on a warm cache). A spinner would
// cause a flash before the real UI mounts.
function LazyFallback() { return null; }

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Toaster position="top-right" richColors />
        <UpgradeModal />
        <Suspense fallback={<LazyFallback />}>
        <Routes>
          {/* Phase I1 (2026-05-11) — pre-login website (10-page MVP).
              `/` now serves the new senior-peer-voice marketing site.
              The legacy `Landing` and `About` routes are repointed to
              the new website surfaces. Older marketing pages
              (Features/Security/Plans/Enterprise/EarlyAccess/Blog)
              remain as deeper routes for back-link compatibility but
              are not in the new website's primary nav. */}
          <Route path="/" element={<WebsiteHome />} />
          <Route path="/why-akki" element={<WebsiteWhyAkki />} />
          <Route path="/what-akki-does" element={<WebsiteWhatAkkiDoes />} />
          <Route path="/trust" element={<WebsiteTrust />} />
          <Route path="/cohort" element={<WebsiteCohort />} />
          <Route path="/waitlist" element={<WebsiteWaitlist />} />
          <Route path="/pricing" element={<WebsitePricing />} />
          <Route path="/about" element={<WebsiteAbout />} />
          <Route path="/contact" element={<WebsiteContact />} />
          <Route path="/privacy" element={<WebsitePrivacy />} />
          <Route path="/terms" element={<WebsiteTerms />} />
          <Route path="/methodology" element={<WebsiteMethodology />} />
          <Route path="/help" element={<Wiki />} />{/* Phase P1 γ — wiki framework */}
          <Route path="/help/:slug" element={<Wiki />} />{/* Phase P1 γ — wiki article */}
          <Route path="/help-legacy" element={<HelpFeatures />} />{/* Phase E (kept as fallback) */}
          <Route path="/status" element={<StatusPage />} />{/* Phase P2 D.2 — public status */}
          <Route path="/__throw" element={<ThrowDiagnostic />} />{/* Phase P2.1-4 — error boundary diagnostic */}
          <Route path="/welcome/:token" element={<WelcomePage />} />{/* Phase P4.D — magic-link landing */}
          <Route path="/exco360" element={<WebsiteExco360 />} />
          {/* v7 (2026-05-12): per-product pages move to top-level routes. */}
          <Route path="/solva" element={<WebsiteProductSolva />} />
          <Route path="/akki-chat" element={<WebsiteProductChat />} />
          <Route path="/work-studio" element={<WebsiteProductWorkStudio />} />
          <Route path="/cycle-manager" element={<WebsiteProductCycle />} />
          <Route path="/monitor" element={<WebsiteProductMonitor />} />
          <Route path="/pulse" element={<WebsiteProductPulse />} />
          <Route path="/document-journal" element={<WebsiteProductJournal />} />
          {/* Back-compat: legacy /product and /product/<x> routes
              redirect to v7 top-level surfaces via Navigate. */}
          <Route path="/product" element={<Navigate to="/what-akki-does" replace />} />
          <Route path="/product/solva" element={<Navigate to="/solva" replace />} />
          <Route path="/product/akki-chat" element={<Navigate to="/akki-chat" replace />} />
          <Route path="/product/work-studio" element={<Navigate to="/work-studio" replace />} />
          <Route path="/product/cycle-manager" element={<Navigate to="/cycle-manager" replace />} />
          <Route path="/product/monitor" element={<Navigate to="/monitor" replace />} />
          <Route path="/product/pulse" element={<Navigate to="/pulse" replace />} />
          <Route path="/for-executives" element={<WebsiteForExecutives />} />
          <Route path="/for-exco" element={<WebsiteForExco />} />
          <Route path="/for-non-executive-directors" element={<WebsiteForNeds />} />
          <Route path="/for-organisations" element={<WebsiteForOrganisations />} />

          {/* Phase F.5 (2026-05-26) — Contributor magic-link portal.
              PUBLIC route, no auth gate, no AppShell. Mounted before
              the marketing routes so /contribute/:token never falls
              through to a marketing page. */}
          <Route path="/contribute/:token" element={<ContributorPortal />} />

          {/* Retained marketing routes (back-link compatibility) */}
          <Route path="/landing-legacy" element={<Landing />} />
          {/* v7: /solva is now the v7 marketing page (above). The
              authenticated landing for Solva lives at /app/solva. */}
          <Route path="/features" element={<Features />} />
          <Route path="/security" element={<Security />} />
          <Route path="/plans" element={<Plans />} />
          <Route path="/enterprise" element={<EnterpriseMarketing />} />
          <Route path="/early-access" element={<Navigate to="/cohort" replace />} />
          <Route path="/blog" element={<Blog />} />
          <Route path="/blog/:slug" element={<BlogPost />} />
          <Route path="/respond/:token" element={<RespondToChecklist />} />
          <Route path="/shared/:token" element={<SharedArtefact />} />
          <Route path="/share/:token" element={<SharedArtefact />} />
          <Route path="/signin" element={<PublicOnlyRoute><SignIn /></PublicOnlyRoute>} />
          <Route path="/signup" element={<PublicOnlyRoute allowSandbox><SignUp /></PublicOnlyRoute>} />
          <Route path="/invite/:token" element={<InviteAccept />} />
          {/* Phase S (2026-05-27) — Password reset (public, no auth). */}
          <Route path="/forgot-password" element={<ForgotPassword />} />
          <Route path="/reset-password/:token" element={<ResetPassword />} />
          {/* Phase U (2026-05-27) — OAuth callback. PUBLIC route, no auth
              gate (the session_id exchange is the auth event). */}
          <Route path="/oauth/callback" element={<OAuthCallback />} />
          {/* C1-revised Phase A (2026-02) — First-login password-set page.
              Authenticated (ProtectedRoute) but OUTSIDE <Gated> so the
              SetPasswordGuard doesn't loop the user onto itself. The
              page itself short-circuits to /app/ when has_set_password
              is not strict-bool false (so a legacy user manually
              navigating here gets bounced back). */}
          <Route
            path="/auth/set-password"
            element={
              <ProtectedRoute>
                <SetPasswordRequired />
              </ProtectedRoute>
            }
          />
          {/* M.4: legacy /sandbox/legacy + /sandbox/generating + /quick-results
              retired. Phase J (2026-05-12): /sandbox is now the new
              Generative Sandbox MVP. Legacy /legacy-sandbox routes
              archived 2026-05-26 (CLEANUP_B1_LOG.md) — SandboxV2 page
              moved to frontend/src/_archived_legacy/. */}
          <Route path="/sandbox" element={<SandboxApp />} />
          {/* J1 (2026-05-24) — public alias for the Trust Center page so
              marketing / external links land on the real surface without
              needing to know the /app prefix. Forwards any querystring
              (e.g. ?intro=shield) verbatim. */}
          <Route
            path="/trust-center"
            element={<Navigate to={`/app/trust-center${window.location.search}`} replace />}
          />

          <Route path="/app/first-session" element={<ProtectedRoute><FirstSession /></ProtectedRoute>} />
          {/* Phase R.5.a (2026-05-27) — Early access opt-in (the ONLY route a hard-locked user can navigate to). */}
          <Route path="/app/early-access-opt-in" element={<ProtectedRoute><EarlyAccessOptIn /></ProtectedRoute>} />
          {/* Phase R.5.a (2026-05-27) — Superadmin cohort console. */}
          <Route path="/app/admin/cohort" element={<SuperadminRoute><Gated><CohortConsole /></Gated></SuperadminRoute>} />
          <Route path="/app/admin/cohort-applications" element={<SuperadminRoute><Gated><AdminCohortApplications /></Gated></SuperadminRoute>} />{/* Phase P4.B */}
          <Route path="/app/admin/inbox" element={<SuperadminRoute><Gated><AdminInbox /></Gated></SuperadminRoute>} />{/* Phase P5.8.2 */}
          {/* Phase V (2026-05-27) — Admin user CRUD portal (superadmin only). */}
          <Route path="/app/admin/users" element={<SuperadminRoute><Gated><AdminUsers /></Gated></SuperadminRoute>} />
          {/* AA.followup.4 — Extraction Activity superadmin view */}
          <Route path="/app/admin/extractions" element={<SuperadminRoute><Gated><ExtractionsActivity /></Gated></SuperadminRoute>} />
          {/* Phase W — Multi-tenant org list view (superadmin) */}
          <Route path="/app/admin/tenants" element={<SuperadminRoute><Gated><AdminTenants /></Gated></SuperadminRoute>} />
          {/* Phase R.5.b (2026-05-27) — Founder copy editor. */}
          <Route path="/app/admin/cohort/copy" element={<SuperadminRoute><Gated><CohortCopyEditor /></Gated></SuperadminRoute>} />
          <Route path="/app" element={<Gated><AppHome /></Gated>} />
          {/* Phase H.5 (2026-05-27) — legacy portfolio routes collapsed
              to /app. /app/portfolio used to render Home1 (now
              archived). External bookmarks redirect transparently. */}
          <Route path="/app/portfolio" element={<Navigate to="/app" replace />} />
          <Route path="/app/questions" element={<Gated><Questions /></Gated>} />
          <Route path="/app/cycle/:cycleId/questions" element={<Gated><Questions /></Gated>} />
          {/* Phase F.1 (2026-05-26) — Task Manager is the canonical
              surface. /app/cycle stays as a backwards-compat alias to
              the legacy CycleList listing while /app/task-manager
              renders the new TaskManager page. */}
          <Route path="/app/task-manager" element={<Gated><TaskManager /></Gated>} />
          <Route path="/app/task-manager/activity" element={<Gated><TaskManagerActivity /></Gated>} />
          <Route path="/app/task-manager/:taskId" element={<Gated><TaskManager /></Gated>} />
          <Route path="/app/cycle" element={<Gated><CycleList /></Gated>} />
          {/* T5 (2026-05-25) — Spec §4.B → C6/C7 Journals. */}
          <Route path="/app/cycle/drafts" element={<Gated><CycleDraftJournal /></Gated>} />
          <Route path="/app/cycle/ready" element={<Gated><CycleReadyJournal /></Gated>} />
          <Route path="/app/cycle/:cycleId" element={<Gated><Cycle /></Gated>} />
          {/* Phase E — NED Cycle Manager */}
          <Route path="/app/ned/meeting/:id" element={<Gated><NedMeeting /></Gated>} />
          <Route path="/app/ned/committee/:cid/:committee" element={<Gated><NedCommittee /></Gated>} />
          <Route path="/app/ned/inbox" element={<Gated><NedInbox /></Gated>} />
          <Route path="/app/monitor" element={<Gated><Monitor /></Gated>} />
          {/* CLEANUP B2 (2026-05-26): /app/plays + /app/plays/:playId
              routes archived per PROVENANCE_TRACE_PLAYS_CYCLE.md —
              Plays surface ORPHAN (no canonical reference). Pages
              moved to frontend/src/_archived_legacy/pages/. Home/Decks
              integrations call /api/contexts/{cid}/plays with a
              `.catch(() => ({ data: { plays: [] } }))` fallback and
              continue to render empty Plays sections. */}
          <Route path="/app/blog-admin" element={<Gated><BlogAdmin /></Gated>} />
          <Route path="/app/workspace" element={<Gated><Workspace /></Gated>} />
          <Route path="/app/inbound-queue" element={<Gated><InboundQueue /></Gated>} />
          <Route path="/app/activity" element={<Gated><Activity /></Gated>} />
          <Route path="/app/simulate" element={<Gated><Simulate /></Gated>} />
          <Route path="/app/lens" element={<Gated><LensRoom /></Gated>} />
          <Route path="/app/chat" element={<Gated><Chat /></Gated>} />
          <Route path="/app/trust-center" element={<Gated><TrustCenter /></Gated>} />  {/* H3 */}
          <Route path="/app/chats/archived" element={<Gated><ArchivedChats /></Gated>} />
          <Route path="/app/influence" element={<Gated><InfluenceMap /></Gated>} />
          <Route path="/admin/health" element={<SuperadminRoute><HealthDashboard /></SuperadminRoute>} />
          <Route path="/admin/sandbox-kpi" element={<SuperadminRoute><SandboxKPI /></SuperadminRoute>} />
          <Route path="/admin/signal-kpi" element={<SuperadminRoute><SignalKPI /></SuperadminRoute>} />
          <Route path="/admin/llm-spend" element={<SuperadminRoute><LLMSpend /></SuperadminRoute>} />
          <Route path="/admin/auth-events" element={<SuperadminRoute><AuthEvents /></SuperadminRoute>} />
          <Route path="/admin" element={<SuperadminRoute><AdminIndex /></SuperadminRoute>} />
          <Route path="/app/learn" element={<Gated><Learn /></Gated>} />
          <Route path="/app/learn/:id" element={<Gated><Learn /></Gated>} />
          <Route path="/app/manage" element={<Gated><Manage /></Gated>} />
          <Route path="/app/enterprise" element={<Gated><Enterprise /></Gated>} />
          <Route path="/app/work-studio" element={<Gated><WorkStudio /></Gated>} />
          {/* Phase P5.14 — Work Studio Analyze tab. Sibling page; does NOT
              touch the Generate surface.
              Track A Phase 2 (2026-06-04) — backward-compat redirect to
              the new /app/analyze journal surface. The flat surface stays
              accessible only as a redirect target for any deep-links. */}
          <Route path="/app/work-studio/analyze" element={<Navigate to="/app/analyze" replace />} />
          {/* Track A Phase 2 (2026-06-04) — Analyze Journal. */}
          <Route path="/app/analyze" element={<Gated><AnalyzeJournal /></Gated>} />
          {/* Phase Z (2026-05-27, Z-slice-4) — Canonical Documents
              Journal. Surfaces every document organized by origin
              (Akki-generated / Uploaded / Emailed). Public route under
              <Gated> wrapper — any authenticated user can land here
              (this is a daily-use exec surface). */}
          <Route path="/app/documents" element={<Gated><DocumentsPage /></Gated>} />
          {/* Phase E.2 — Recent Activity full-page view */}
          <Route path="/app/work-studio/activity" element={<Gated><WorkStudioActivity /></Gated>} />
          {/* T3.3 (2026-05-25) — G8 ratified dedicated full-page
              surface for Board Packs + Committee Packs. The pre-T3
              route here pointed to <WorkStudio /> and auto-opened
              the overlay; per G8 these two kinds now render as a
              standalone page (W3), while Minutes / Decks / Reports
              still open the overlay drawer from the listing (W4). */}
          <Route path="/app/work-studio/document/:artefactId" element={<Gated><WorkStudioDocumentPage /></Gated>} />
          <Route path="/app/decks/:deckId" element={<Gated><Decks /></Gated>} />
          <Route path="/app/pulse" element={<Gated><Pulse /></Gated>} />
          {/* Phase P5.15 — Pulse Ideas by Akki (weekly cited synthesis).
              Sibling page; does NOT touch the Signals surface. */}
          <Route path="/app/pulse/ideas" element={<Gated><PulseIdeas /></Gated>} />
          {/* Phase F0 — Universal Search full results page. */}
          <Route path="/app/search" element={<Gated><SearchResults /></Gated>} />
          <Route path="/app/studio/composer/:kind/:artefactId" element={<Gated><StudioComposerPage /></Gated>} />
          <Route path="/app/solva" element={<Gated><SolvaApp /></Gated>} />
          <Route path="/app/solva/sessions" element={<Gated><SolvaSessions /></Gated>} />
          <Route path="/app/solva/session/new" element={<Gated><SolvaSession /></Gated>} />
          <Route path="/app/solva/session/:sessionId" element={<Gated><SolvaSession /></Gated>} />
          {/* Phase E Sub-task A — Phase D engine surface. */}
          <Route path="/app/solva/phase-d/session/new" element={<Gated><SolvaPhaseDSession /></Gated>} />
          <Route path="/app/solva/phase-d/session/:sessionId" element={<Gated><SolvaPhaseDSession /></Gated>} />
          <Route path="/app/admin/synisense-observability" element={<SuperadminRoute><Gated><SynisenseObservability /></Gated></SuperadminRoute>} />
          <Route path="/app/documents/:id" element={<Gated><DocumentRouteSwitch /></Gated>} />
          {/* Phase H.5 (2026-05-27) — /app/contexts and /app/companies
              landing routes collapsed to /app. ContextPortfolio renders
              there via the AppHome dispatcher's no-active-context
              branch. External bookmarks redirect transparently. */}
          <Route path="/app/contexts" element={<Navigate to="/app" replace />} />
          <Route path="/app/companies" element={<Navigate to="/app" replace />} />
          {/* H.1 (2026-05-26) — Portfolio Landing news stub. Full feed lands in H.3. */}
          <Route path="/app/news" element={<Gated><NewsStub /></Gated>} />
          {/* I.4.a (2026-05-27) — Events page (manual entry). */}
          <Route path="/app/events" element={<Gated><Events /></Gated>} />
          <Route path="/app/companies/new" element={<Gated><NewContext /></Gated>} />
          <Route path="/app/contexts/new" element={<Gated><NewContext /></Gated>} />
          <Route path="/app/new-workspace" element={<Gated><NewContext /></Gated>} />
          <Route path="/app/settings" element={<Gated><TenantSettings /></Gated>} />
          {/* CLEANUP B2 (2026-05-26): /app/settings/cycle route archived
              — CycleSettings.jsx was the only consumer of cycle_config
              router (now archived) and useCycleConfig hook (now archived).
              Orphan route, not in nav, not in spec. */}
          <Route path="/app/review" element={<Gated><DailyReview /></Gated>} />
          <Route path="/app/settings/billing" element={<Gated><TenantSettings /></Gated>} />
          <Route path="/app/security" element={<Gated><AccountSecurity /></Gated>} />

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        </Suspense>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
