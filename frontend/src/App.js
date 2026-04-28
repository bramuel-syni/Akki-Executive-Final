import React from "react";
import "@/App.css";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "@/contexts/AuthContext";
import ProtectedRoute from "@/components/ProtectedRoute";
import { Toaster } from "@/components/ui/sonner";

import Landing from "@/pages/Landing";
import SignIn from "@/pages/SignIn";
import SignUp from "@/pages/SignUp";
import Onboarding from "@/pages/Onboarding";
import AppHome from "@/pages/AppHome";
import Workspace from "@/pages/Workspace";
import Prepare from "@/pages/Prepare";
import Activity from "@/pages/Activity";
import DocumentViewer from "@/pages/DocumentViewer";
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
import QuickResults from "@/pages/QuickResults";
import Manage from "@/pages/Manage";
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
import Blog from "@/pages/marketing/Blog";
import BlogPost from "@/pages/marketing/BlogPost";
import BlogAdmin from "@/pages/marketing/BlogAdmin";

function PublicOnlyRoute({ children, allowSandbox = false }) {
  const { account } = useAuth();
  if (account === null) return null;
  // Sandbox users must be allowed through to /signup so they can convert.
  if (account && !(allowSandbox && account.is_sandbox)) return <Navigate to="/app" replace />;
  return children;
}

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Toaster position="top-right" richColors />
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/about" element={<About />} />
          <Route path="/features" element={<Features />} />
          <Route path="/security" element={<Security />} />
          <Route path="/blog" element={<Blog />} />
          <Route path="/blog/:slug" element={<BlogPost />} />
          <Route path="/respond/:token" element={<RespondToChecklist />} />
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

          <Route path="/onboarding" element={<ProtectedRoute><Onboarding /></ProtectedRoute>} />
          <Route path="/app" element={<ProtectedRoute><AppHome /></ProtectedRoute>} />
          <Route path="/app/cycle" element={<ProtectedRoute><Cycle /></ProtectedRoute>} />
          <Route path="/app/monitor" element={<ProtectedRoute><Monitor /></ProtectedRoute>} />
          <Route path="/app/plays" element={<ProtectedRoute><PlaysLibrary /></ProtectedRoute>} />
          <Route path="/app/plays/:playId" element={<ProtectedRoute><PlayView /></ProtectedRoute>} />
          <Route path="/app/blog-admin" element={<ProtectedRoute><BlogAdmin /></ProtectedRoute>} />
          <Route path="/app/workspace" element={<ProtectedRoute><Workspace /></ProtectedRoute>} />
          <Route path="/app/prepare" element={<ProtectedRoute><Prepare /></ProtectedRoute>} />
          <Route path="/app/activity" element={<ProtectedRoute><Activity /></ProtectedRoute>} />
          {/* Apr-2026: Signals + Briefings consolidated into /app/prepare. Old
              routes redirect — keeps email/bookmark links alive without a 404. */}
          <Route path="/app/highlights" element={<Navigate to="/app/prepare" replace />} />
          <Route path="/app/briefings" element={<Navigate to="/app/prepare" replace />} />
          {/* v4.2: Ask merges into Workspace; any /app/ask redirects there */}
          <Route path="/app/ask" element={<Navigate to="/app/workspace" replace />} />
          <Route path="/app/simulate" element={<ProtectedRoute><Simulate /></ProtectedRoute>} />
          <Route path="/app/lens" element={<ProtectedRoute><LensRoom /></ProtectedRoute>} />
          <Route path="/app/chat" element={<ProtectedRoute><Chat /></ProtectedRoute>} />
          <Route path="/app/influence" element={<ProtectedRoute><InfluenceMap /></ProtectedRoute>} />
          <Route path="/admin/health" element={<ProtectedRoute><HealthDashboard /></ProtectedRoute>} />
          <Route path="/admin/sandbox-kpi" element={<ProtectedRoute><SandboxKPI /></ProtectedRoute>} />
          <Route path="/admin/signal-kpi" element={<ProtectedRoute><SignalKPI /></ProtectedRoute>} />
          <Route path="/app/quick-results/:contextId/:docId" element={<ProtectedRoute><QuickResults /></ProtectedRoute>} />
          <Route path="/app/learn" element={<ProtectedRoute><Learn /></ProtectedRoute>} />
          <Route path="/app/learn/:id" element={<ProtectedRoute><Learn /></ProtectedRoute>} />
          <Route path="/app/manage" element={<ProtectedRoute><Manage /></ProtectedRoute>} />
          <Route path="/app/documents/:id" element={<ProtectedRoute><DocumentViewer /></ProtectedRoute>} />
          <Route path="/app/contexts" element={<ProtectedRoute><ContextPortfolio /></ProtectedRoute>} />
          <Route path="/app/contexts/new" element={<ProtectedRoute><NewContext /></ProtectedRoute>} />
          <Route path="/app/new-workspace" element={<ProtectedRoute><NewContext /></ProtectedRoute>} />
          <Route path="/app/settings" element={<ProtectedRoute><TenantSettings /></ProtectedRoute>} />
          <Route path="/app/settings/billing" element={<ProtectedRoute><TenantSettings /></ProtectedRoute>} />
          <Route path="/app/security" element={<ProtectedRoute><AccountSecurity /></ProtectedRoute>} />

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
