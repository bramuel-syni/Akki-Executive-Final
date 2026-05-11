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
import SandboxV2 from "@/pages/SandboxV2";
// Phase J (2026-05-12) — Generative Sandbox MVP replaces the legacy
// guided tour at /sandbox. The old tour moves to /legacy-sandbox.
import SandboxApp from "@/sandbox/SandboxApp";
import Manage from "@/pages/Manage";
import Enterprise from "@/pages/Enterprise";
import Decks from "@/pages/Decks";
import SolvaApp from "@/pages/SolvaApp";
import SolvaSession from "@/pages/SolvaSession";
import SolvaSessions from "@/pages/SolvaSessions";
import Cycle from "@/pages/Cycle";
import CycleList from "@/pages/cycle/CycleList";  // Cycle v2 — multi-cycle list landing
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
import Pulse from "@/pages/Pulse";
import SearchResults from "@/pages/SearchResults";  // Phase F0 — Universal Search results page

// Phase I1 (2026-05-11) + v7 (2026-05-12) — Pre-login marketing website.
// All website routes live OUTSIDE /app/*. v7 reinstates /pricing and
// adds /document-journal. Per-product pages move from /product/<x> to
// top-level routes (/solva, /akki-chat, /work-studio, etc.).
import WebsiteHome from "@/website/pages/Home";
import WebsiteWhyAkki from "@/website/pages/WhyAkki";
import WebsiteWhatAkkiDoes from "@/website/pages/WhatAkkiDoes";
import WebsiteTrust from "@/website/pages/Trust";
import WebsiteCohort from "@/website/pages/Cohort";
import WebsitePricing from "@/website/pages/Pricing";
import WebsiteAbout from "@/website/pages/About";
import WebsiteContact from "@/website/pages/Contact";
import WebsitePrivacy from "@/website/pages/Privacy";
import WebsiteTerms from "@/website/pages/Terms";
import WebsiteMethodology from "@/website/pages/Methodology";
import WebsiteExco360 from "@/website/pages/Exco360";
import WebsiteProductSolva from "@/website/pages/product/Solva";
import WebsiteProductChat from "@/website/pages/product/AkkiChat";
import WebsiteProductWorkStudio from "@/website/pages/product/WorkStudio";
import WebsiteProductCycle from "@/website/pages/product/CycleManager";
import WebsiteProductMonitor from "@/website/pages/product/Monitor";
import WebsiteProductPulse from "@/website/pages/product/Pulse";
import WebsiteProductJournal from "@/website/pages/product/DocumentJournal";
import WebsiteForExecutives from "@/website/pages/ForExecutives";
import WebsiteForExco from "@/website/pages/ForExco";
import WebsiteForNeds from "@/website/pages/ForNeds";
import WebsiteForOrganisations from "@/website/pages/ForOrganisations";
import NedMeeting from "@/pages/ned/NedMeeting";   // Phase E
import NedCommittee from "@/pages/ned/NedCommittee"; // Phase E
import NedInbox from "@/pages/ned/NedInbox";       // Cycle sprint — assignment handoff

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

          <Route path="/app/first-session" element={<ProtectedRoute><FirstSession /></ProtectedRoute>} />
          <Route path="/app" element={<Gated><AppHome /></Gated>} />
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
          <Route path="/app/decks/:deckId" element={<Gated><Decks /></Gated>} />
          <Route path="/app/pulse" element={<Gated><Pulse /></Gated>} />
          {/* Phase F0 — Universal Search full results page. */}
          <Route path="/app/search" element={<Gated><SearchResults /></Gated>} />
          <Route path="/app/studio/composer/:kind/:artefactId" element={<Gated><StudioComposerPage /></Gated>} />
          <Route path="/app/solva" element={<Gated><SolvaApp /></Gated>} />
          <Route path="/app/solva/sessions" element={<Gated><SolvaSessions /></Gated>} />
          <Route path="/app/solva/session/new" element={<Gated><SolvaSession /></Gated>} />
          <Route path="/app/solva/session/:sessionId" element={<Gated><SolvaSession /></Gated>} />
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
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
