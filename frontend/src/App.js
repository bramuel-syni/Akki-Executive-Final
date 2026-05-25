import React, { Suspense, lazy } from "react";
import "@/App.css";
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { AuthProvider, useAuth } from "@/contexts/AuthContext";
import ProtectedRoute from "@/components/ProtectedRoute";
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

// -- Lazy: marketing deeper routes (rarely visited from cold start) ----------
const Landing = lazy(() => import("@/pages/Landing"));
const SolvaLanding = lazy(() => import("@/pages/SolvaLanding"));
const About = lazy(() => import("@/pages/marketing/About"));
const Features = lazy(() => import("@/pages/marketing/Features"));
const Security = lazy(() => import("@/pages/marketing/Security"));
const Plans = lazy(() => import("@/pages/marketing/Plans"));
const EnterpriseMarketing = lazy(() => import("@/pages/marketing/Enterprise"));
const EarlyAccess = lazy(() => import("@/pages/marketing/EarlyAccess"));
const Blog = lazy(() => import("@/pages/marketing/Blog"));
const BlogPost = lazy(() => import("@/pages/marketing/BlogPost"));
const BlogAdmin = lazy(() => import("@/pages/marketing/BlogAdmin"));
const WebsiteWhyAkki = lazy(() => import("@/website/pages/WhyAkki"));
const WebsiteWhatAkkiDoes = lazy(() => import("@/website/pages/WhatAkkiDoes"));
const WebsiteTrust = lazy(() => import("@/website/pages/Trust"));
const WebsiteCohort = lazy(() => import("@/website/pages/Cohort"));
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
const Home1 = lazy(() => import("@/pages/home/Home1"));
const Questions = lazy(() => import("@/pages/Questions"));
const Workspace = lazy(() => import("@/pages/Workspace"));
const Activity = lazy(() => import("@/pages/Activity"));
const ReadingView = lazy(() => import("@/pages/ReadingView"));
const CycleSettings = lazy(() => import("@/pages/CycleSettings"));
const DailyReview = lazy(() => import("@/pages/DailyReview"));
const Learn = lazy(() => import("@/pages/Learn"));
const TenantSettings = lazy(() => import("@/pages/TenantSettings"));
const AccountSecurity = lazy(() => import("@/pages/AccountSecurity"));
const InviteAccept = lazy(() => import("@/pages/InviteAccept"));
const NewContext = lazy(() => import("@/pages/NewWorkspace"));
const ContextPortfolio = lazy(() => import("@/pages/ContextPortfolio"));
const Simulate = lazy(() => import("@/pages/Simulate"));
const LensRoom = lazy(() => import("@/pages/LensRoom"));
const Chat = lazy(() => import("@/pages/Chat"));
const ArchivedChats = lazy(() => import("@/pages/ArchivedChats"));
const InfluenceMap = lazy(() => import("@/pages/InfluenceMap"));
const SandboxV2 = lazy(() => import("@/pages/SandboxV2"));
const SandboxApp = lazy(() => import("@/sandbox/SandboxApp"));
const Manage = lazy(() => import("@/pages/Manage"));
const HelpFeatures = lazy(() => import("@/pages/HelpFeatures"));  // Phase E — /help
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
const Monitor = lazy(() => import("@/pages/Monitor"));
const PlaysLibrary = lazy(() => import("@/pages/PlaysLibrary"));
const PlayView = lazy(() => import("@/pages/PlayView"));
const RespondToChecklist = lazy(() => import("@/pages/RespondToChecklist"));
const SharedArtefact = lazy(() => import("@/pages/SharedArtefact"));
const InboundQueue = lazy(() => import("@/pages/InboundQueue"));
const StudioComposerPage = lazy(() => import("@/pages/StudioComposerPage"));
const WorkStudio = lazy(() => import("@/pages/WorkStudio"));
const Pulse = lazy(() => import("@/pages/Pulse"));
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

// Patch 3 — Home 1 needs to render even when the user has an active context
// (the explicit "Back to portfolio" path).
function PortfolioRoute() { return <Home1 />; }

function PublicOnlyRoute({ children, allowSandbox = false }) {
  const { account } = useAuth();
  if (account === null) return null;
  // Sandbox users must be allowed through to /signup so they can convert.
  // QA-2026-05-16-001 (Chunk 15, 2026-05-21) — when an already-authed
  // user (or a just-authed one mid-state-flush) lands here, redirect to
  // `/app/portfolio` instead of `/app`. This matches the SignIn handler
  // default and ensures the post-login experience always lands on Home 1
  // (the portfolio surface) regardless of whether the React state flush
  // racing the navigate() call wins.
  if (account && !(allowSandbox && account.is_sandbox)) return <Navigate to="/app/portfolio" replace />;
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

/** Document route — always renders ReadingView. The `?v=*` switch from
 *  the Phase 1 default-flip transition was retired in Phase 3 along with
 *  the legacy DocumentViewer. Any `?v=` param is now ignored.
 *  See /app/docs/ux-advisories-v1.md (Phase 3 changelog).
 */
function DocumentRouteSwitch() {
  return <ReadingView />;
}

function Gated({ children }) {
  return (
    <ProtectedRoute>
      <FirstSessionGuard>{children}</FirstSessionGuard>
    </ProtectedRoute>
  );
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
          <Route path="/pricing" element={<WebsitePricing />} />
          <Route path="/about" element={<WebsiteAbout />} />
          <Route path="/contact" element={<WebsiteContact />} />
          <Route path="/privacy" element={<WebsitePrivacy />} />
          <Route path="/terms" element={<WebsiteTerms />} />
          <Route path="/methodology" element={<WebsiteMethodology />} />
          <Route path="/help" element={<HelpFeatures />} />{/* Phase E */}
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

          {/* Retained marketing routes (back-link compatibility) */}
          <Route path="/landing-legacy" element={<Landing />} />
          {/* v7: /solva is now the v7 marketing page (above). The
              authenticated landing for Solva lives at /app/solva. */}
          <Route path="/features" element={<Features />} />
          <Route path="/security" element={<Security />} />
          <Route path="/plans" element={<Plans />} />
          <Route path="/enterprise" element={<EnterpriseMarketing />} />
          <Route path="/early-access" element={<EarlyAccess />} />
          <Route path="/blog" element={<Blog />} />
          <Route path="/blog/:slug" element={<BlogPost />} />
          <Route path="/respond/:token" element={<RespondToChecklist />} />
          <Route path="/shared/:token" element={<SharedArtefact />} />
          <Route path="/share/:token" element={<SharedArtefact />} />
          <Route path="/signin" element={<PublicOnlyRoute><SignIn /></PublicOnlyRoute>} />
          <Route path="/signup" element={<PublicOnlyRoute allowSandbox><SignUp /></PublicOnlyRoute>} />
          <Route path="/invite/:token" element={<InviteAccept />} />
          {/* M.4: legacy /sandbox/legacy + /sandbox/generating + /quick-results
              retired. Phase J (2026-05-12): /sandbox is now the new
              Generative Sandbox MVP. The legacy guided tour (SandboxV2)
              moved to /legacy-sandbox for back-link compatibility. */}
          <Route path="/sandbox" element={<SandboxApp />} />
          <Route path="/legacy-sandbox" element={<SandboxV2 />} />
          <Route path="/legacy-sandbox/resume" element={<SandboxV2 />} />
          {/* J1 (2026-05-24) — public alias for the Trust Center page so
              marketing / external links land on the real surface without
              needing to know the /app prefix. Forwards any querystring
              (e.g. ?intro=shield) verbatim. */}
          <Route
            path="/trust-center"
            element={<Navigate to={`/app/trust-center${window.location.search}`} replace />}
          />

          <Route path="/app/first-session" element={<ProtectedRoute><FirstSession /></ProtectedRoute>} />
          <Route path="/app" element={<Gated><AppHome /></Gated>} />
          {/* Patch 3 — explicit portfolio entry (always Home 1). */}
          <Route path="/app/questions" element={<Gated><Questions /></Gated>} />
          <Route path="/app/cycle/:cycleId/questions" element={<Gated><Questions /></Gated>} />
          <Route path="/app/portfolio" element={<Gated><PortfolioRoute /></Gated>} />
          <Route path="/app/cycle" element={<Gated><CycleList /></Gated>} />
          <Route path="/app/cycle/:cycleId" element={<Gated><Cycle /></Gated>} />
          {/* Phase E — NED Cycle Manager */}
          <Route path="/app/ned/meeting/:id" element={<Gated><NedMeeting /></Gated>} />
          <Route path="/app/ned/committee/:cid/:committee" element={<Gated><NedCommittee /></Gated>} />
          <Route path="/app/ned/inbox" element={<Gated><NedInbox /></Gated>} />
          <Route path="/app/monitor" element={<Gated><Monitor /></Gated>} />
          <Route path="/app/plays" element={<Gated><PlaysLibrary /></Gated>} />
          <Route path="/app/plays/:playId" element={<Gated><PlayView /></Gated>} />
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
          <Route path="/admin/health" element={<ProtectedRoute><HealthDashboard /></ProtectedRoute>} />
          <Route path="/admin/sandbox-kpi" element={<ProtectedRoute><SandboxKPI /></ProtectedRoute>} />
          <Route path="/admin/signal-kpi" element={<ProtectedRoute><SignalKPI /></ProtectedRoute>} />
          <Route path="/admin/llm-spend" element={<ProtectedRoute><LLMSpend /></ProtectedRoute>} />
          <Route path="/admin/auth-events" element={<ProtectedRoute><AuthEvents /></ProtectedRoute>} />
          <Route path="/admin" element={<ProtectedRoute><AdminIndex /></ProtectedRoute>} />
          <Route path="/app/learn" element={<Gated><Learn /></Gated>} />
          <Route path="/app/learn/:id" element={<Gated><Learn /></Gated>} />
          <Route path="/app/manage" element={<Gated><Manage /></Gated>} />
          <Route path="/app/enterprise" element={<Gated><Enterprise /></Gated>} />
          <Route path="/app/work-studio" element={<Gated><WorkStudio /></Gated>} />
          {/* Chunk 8 (2026-05-18, QA-2026-05-16-029) — direct overlay URL
              so the overlay is reachable independent of the brief-drawer
              entry point. WorkStudio reads `:artefactId` and auto-opens
              the overlay. */}
          <Route path="/app/work-studio/document/:artefactId" element={<Gated><WorkStudio /></Gated>} />
          <Route path="/app/decks/:deckId" element={<Gated><Decks /></Gated>} />
          <Route path="/app/pulse" element={<Gated><Pulse /></Gated>} />
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
          <Route path="/app/admin/synisense-observability" element={<Gated><SynisenseObservability /></Gated>} />
          <Route path="/app/documents/:id" element={<Gated><DocumentRouteSwitch /></Gated>} />
          <Route path="/app/contexts" element={<Gated><ContextPortfolio /></Gated>} />
          {/* Phase 15.2 cosmetic alias: /app/companies alongside /app/contexts. */}
          <Route path="/app/companies" element={<Gated><ContextPortfolio /></Gated>} />
          <Route path="/app/companies/new" element={<Gated><NewContext /></Gated>} />
          <Route path="/app/contexts/new" element={<Gated><NewContext /></Gated>} />
          <Route path="/app/new-workspace" element={<Gated><NewContext /></Gated>} />
          <Route path="/app/settings" element={<Gated><TenantSettings /></Gated>} />
          <Route path="/app/settings/cycle" element={<Gated><CycleSettings /></Gated>} />
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
