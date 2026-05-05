import React from "react";
import "@/App.css";
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { AuthProvider, useAuth } from "@/contexts/AuthContext";
import ProtectedRoute from "@/components/ProtectedRoute";
import { Toaster } from "@/components/ui/sonner";

import Landing from "@/pages/Landing";
import SolvaLanding from "@/pages/SolvaLanding";
import SignIn from "@/pages/SignIn";
import SignUp from "@/pages/SignUp";
import FirstSession from "@/pages/FirstSession";
import UpgradeModal from "@/components/depth/UpgradeModal";
import AppHome from "@/pages/AppHome";
import Workspace from "@/pages/Workspace";
import Prepare from "@/pages/Prepare";
import Activity from "@/pages/Activity";
import ReadingView from "@/pages/ReadingView";
import CycleSettings from "@/pages/CycleSettings";
import DailyReview from "@/pages/DailyReview";
import Learn from "@/pages/Learn";
import TenantSettings from "@/pages/TenantSettings";
import AccountSecurity from "@/pages/AccountSecurity";
import InviteAccept from "@/pages/InviteAccept";
import NewContext from "@/pages/NewWorkspace";
import ContextPortfolio from "@/pages/ContextPortfolio";
import Simulate from "@/pages/Simulate";
import LensRoom from "@/pages/LensRoom";
import Chat from "@/pages/Chat";
import InfluenceMap from "@/pages/InfluenceMap";
import HealthDashboard from "@/pages/admin/HealthDashboard";
import SandboxKPI from "@/pages/admin/SandboxKPI";
import SignalKPI from "@/pages/admin/SignalKPI";
import LLMSpend from "@/pages/admin/LLMSpend";
import AuthEvents from "@/pages/admin/AuthEvents";
import AdminIndex from "@/pages/admin/AdminIndex";
import QuickResults from "@/pages/QuickResults";
import Manage from "@/pages/Manage";
import Enterprise from "@/pages/Enterprise";
import Decks from "@/pages/Decks";
import SolvaApp from "@/pages/SolvaApp";
import SolvaSession from "@/pages/SolvaSession";
import Sandbox from "@/pages/Sandbox";
import SandboxGenerating from "@/pages/SandboxGenerating";
import Cycle from "@/pages/Cycle";
import Monitor from "@/pages/Monitor";
import PlaysLibrary from "@/pages/PlaysLibrary";
import PlayView from "@/pages/PlayView";
import RespondToChecklist from "@/pages/RespondToChecklist";
import About from "@/pages/marketing/About";
import Features from "@/pages/marketing/Features";
import Security from "@/pages/marketing/Security";
import Plans from "@/pages/marketing/Plans";
import EnterpriseMarketing from "@/pages/marketing/Enterprise";
import EarlyAccess from "@/pages/marketing/EarlyAccess";
import Blog from "@/pages/marketing/Blog";
import BlogPost from "@/pages/marketing/BlogPost";
import BlogAdmin from "@/pages/marketing/BlogAdmin";
import SharedArtefact from "@/pages/SharedArtefact";
import InboundQueue from "@/pages/InboundQueue";
import StudioComposerPage from "@/pages/StudioComposerPage";
// Phase 13.3 — new top-level surfaces
import WorkStudio from "@/pages/WorkStudio";
import PulsePlaceholder from "@/pages/PulsePlaceholder";

function PublicOnlyRoute({ children, allowSandbox = false }) {
  const { account } = useAuth();
  if (account === null) return null;
  // Sandbox users must be allowed through to /signup so they can convert.
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

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Toaster position="top-right" richColors />
        <UpgradeModal />
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/solva" element={<SolvaLanding />} />
          {/* Phase 13.1 — legacy /solve URL alias. Solve was renamed to
              Solva in Phase 13.1; the alias keeps any external link
              (bookmarks, old emails, search-engine results) working
              silently. Plan to retire in Phase 14. */}
          <Route path="/solve" element={<Navigate to="/solva" replace />} />
          <Route path="/about" element={<About />} />
          <Route path="/features" element={<Features />} />
          <Route path="/security" element={<Security />} />
          <Route path="/plans" element={<Plans />} />
          <Route path="/enterprise" element={<EnterpriseMarketing />} />
          <Route path="/early-access" element={<EarlyAccess />} />
          <Route path="/methodology" element={<Navigate to="/about#methodology" replace />} />
          <Route path="/blog" element={<Blog />} />
          <Route path="/blog/:slug" element={<BlogPost />} />
          <Route path="/respond/:token" element={<RespondToChecklist />} />
          <Route path="/shared/:token" element={<SharedArtefact />} />
          {/* Phase 11 ITEM A — /share/:token alias. The Chair invitation
              emails out of studio.py currently use /shared/:token; this
              alias keeps newer communications (and muscle-memory typing)
              on the shorter URL without breaking older emails. Same
              component, same read-only surface. */}
          <Route path="/share/:token" element={<SharedArtefact />} />
          <Route path="/signin" element={<PublicOnlyRoute><SignIn /></PublicOnlyRoute>} />
          {/* URL aliases for muscle-memory / external-bookmark variants. The
              app's internal links use /signin, but users (and search engines,
              and old emails we've sent) commonly hit /sign-in or /login. The
              catch-all below would otherwise bounce them silently to /, which
              looks identical to the user as 'login is broken'. */}
          <Route path="/sign-in" element={<Navigate to="/signin" replace />} />
          <Route path="/login" element={<Navigate to="/signin" replace />} />
          <Route path="/log-in" element={<Navigate to="/signin" replace />} />
          <Route path="/signup" element={<PublicOnlyRoute allowSandbox><SignUp /></PublicOnlyRoute>} />
          <Route path="/sign-up" element={<Navigate to="/signup" replace />} />
          <Route path="/register" element={<Navigate to="/signup" replace />} />
          <Route path="/invite/:token" element={<InviteAccept />} />
          <Route path="/sandbox" element={<Sandbox />} />
          <Route path="/sandbox/generating/:sessionId" element={<SandboxGenerating />} />

          <Route path="/app/first-session" element={<ProtectedRoute><FirstSession /></ProtectedRoute>} />
          <Route path="/onboarding" element={<Navigate to="/app/first-session" replace />} />
          <Route path="/app" element={<Gated><AppHome /></Gated>} />
          <Route path="/app/cycle" element={<Gated><Cycle /></Gated>} />
          <Route path="/app/monitor" element={<Gated><Monitor /></Gated>} />
          <Route path="/app/plays" element={<Gated><PlaysLibrary /></Gated>} />
          <Route path="/app/plays/:playId" element={<Gated><PlayView /></Gated>} />
          <Route path="/app/blog-admin" element={<Gated><BlogAdmin /></Gated>} />
          <Route path="/app/workspace" element={<Gated><Workspace /></Gated>} />
          {/* Phase 13.2 — /app/prepare absorbed into Cycle Manager's Briefs
              tab. Bookmarks and email deep-links keep working silently;
              the legacy <Prepare /> page component is still exported but
              now serves the Cycle tabs (`embedded` mode). Plan to retire
              the redirect in Phase 14 once outbound emails have rotated. */}
          <Route path="/app/prepare" element={<Navigate to="/app/cycle?tab=briefs" replace />} />
          <Route path="/app/inbound-queue" element={<Gated><InboundQueue /></Gated>} />
          <Route path="/app/activity" element={<Gated><Activity /></Gated>} />
          {/* Apr-2026: Signals + Briefings consolidated into /app/prepare,
              now further consolidated by Phase 13.2 into Cycle Manager.
              The chain is: /app/highlights → /app/prepare → /app/cycle?tab=briefs.
              Each hop is a Navigate replace so history stays clean. */}
          <Route path="/app/highlights" element={<Navigate to="/app/cycle?tab=signals" replace />} />
          <Route path="/app/briefings" element={<Navigate to="/app/cycle?tab=briefs" replace />} />
          {/* v4.2: Ask merges into Workspace; any /app/ask redirects there */}
          <Route path="/app/ask" element={<Navigate to="/app/workspace" replace />} />
          <Route path="/app/simulate" element={<Gated><Simulate /></Gated>} />
          <Route path="/app/lens" element={<Gated><LensRoom /></Gated>} />
          <Route path="/app/chat" element={<Gated><Chat /></Gated>} />
          <Route path="/app/influence" element={<Gated><InfluenceMap /></Gated>} />
          <Route path="/admin/health" element={<ProtectedRoute><HealthDashboard /></ProtectedRoute>} />
          <Route path="/admin/sandbox-kpi" element={<ProtectedRoute><SandboxKPI /></ProtectedRoute>} />
          <Route path="/admin/signal-kpi" element={<ProtectedRoute><SignalKPI /></ProtectedRoute>} />
          <Route path="/admin/llm-spend" element={<ProtectedRoute><LLMSpend /></ProtectedRoute>} />
          <Route path="/admin/auth-events" element={<ProtectedRoute><AuthEvents /></ProtectedRoute>} />
          <Route path="/admin" element={<ProtectedRoute><AdminIndex /></ProtectedRoute>} />
          <Route path="/app/quick-results/:contextId/:docId" element={<Gated><QuickResults /></Gated>} />
          <Route path="/app/learn" element={<Gated><Learn /></Gated>} />
          <Route path="/app/learn/:id" element={<Gated><Learn /></Gated>} />
          <Route path="/app/manage" element={<Gated><Manage /></Gated>} />
          <Route path="/app/enterprise" element={<Gated><Enterprise /></Gated>} />
          {/* Phase 13.3 — Work Studio is the new unified entry hub for
              in-flight briefings/decks/reports across the active context.
              `/app/decks` listing redirects here with the Decks tab
              pre-selected; the per-deck detail page (`/app/decks/:id`)
              still routes to the existing `<Decks />` component because
              the deck detail UI has not moved. */}
          <Route path="/app/work-studio" element={<Gated><WorkStudio /></Gated>} />
          <Route path="/app/decks" element={<Navigate to="/app/work-studio?view=decks" replace />} />
          <Route path="/app/decks/:deckId" element={<Gated><Decks /></Gated>} />
          {/* Phase 13.3 — Pulse holding page. Real Pulse module ships in
              Phase 14. The link in the primary top nav points here so
              users discover the feature ahead of build. */}
          <Route path="/app/pulse" element={<Gated><PulsePlaceholder /></Gated>} />
          <Route path="/app/studio/composer/:kind/:artefactId" element={<Gated><StudioComposerPage /></Gated>} />
          {/* Phase A — Solva is now a single production surface mounted
              directly at /app/solva. The legacy AppSolva stub and the
              v2-poc URL alias have both been retired. */}
          <Route path="/app/solva" element={<Gated><SolvaApp /></Gated>} />
          <Route path="/app/solva/v2-poc" element={<Navigate to="/app/solva" replace />} />
          {/* Phase I.2 — Solva v3 Guided Flow state-machine page. */}
          <Route path="/app/solva/session/new" element={<Gated><SolvaSession /></Gated>} />
          <Route path="/app/solva/session/:sessionId" element={<Gated><SolvaSession /></Gated>} />
          {/* Legacy /app/solve alias for muscle memory and external
              bookmarks. Redirects to the v2 surface. */}
          <Route path="/app/solve" element={<Navigate to="/app/solva" replace />} />
          <Route path="/app/documents/:id" element={<Gated><DocumentRouteSwitch /></Gated>} />
          <Route path="/app/contexts" element={<Gated><ContextPortfolio /></Gated>} />
          {/* Phase 15.2 — cosmetic alias renaming Contexts → Companies in
              user-facing copy. Backend paths stay /api/contexts/* so we
              keep /app/contexts functional and add /app/companies for the
              renamed UI vocabulary + email links. */}
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
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
