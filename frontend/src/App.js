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
import Highlights from "@/pages/Highlights";
import Briefings from "@/pages/Briefings";
import DocumentViewer from "@/pages/DocumentViewer";
import Learn from "@/pages/Learn";
import TenantSettings from "@/pages/TenantSettings";
import AccountSecurity from "@/pages/AccountSecurity";
import InviteAccept from "@/pages/InviteAccept";
import NewContext from "@/pages/NewWorkspace";
import ContextPortfolio from "@/pages/ContextPortfolio";
import Simulate from "@/pages/Simulate";
import LensRoom from "@/pages/LensRoom";
import Manage from "@/pages/Manage";
import Sandbox from "@/pages/Sandbox";
import SandboxGenerating from "@/pages/SandboxGenerating";
import Cycle from "@/pages/Cycle";
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
          <Route path="/signup" element={<PublicOnlyRoute allowSandbox><SignUp /></PublicOnlyRoute>} />
          <Route path="/invite/:token" element={<InviteAccept />} />
          <Route path="/sandbox" element={<Sandbox />} />
          <Route path="/sandbox/generating/:sessionId" element={<SandboxGenerating />} />

          <Route path="/onboarding" element={<ProtectedRoute><Onboarding /></ProtectedRoute>} />
          <Route path="/app" element={<ProtectedRoute><AppHome /></ProtectedRoute>} />
          <Route path="/app/cycle" element={<ProtectedRoute><Cycle /></ProtectedRoute>} />
          <Route path="/app/blog-admin" element={<ProtectedRoute><BlogAdmin /></ProtectedRoute>} />
          <Route path="/app/workspace" element={<ProtectedRoute><Workspace /></ProtectedRoute>} />
          <Route path="/app/highlights" element={<ProtectedRoute><Highlights /></ProtectedRoute>} />
          {/* v4.2: Ask merges into Workspace; any /app/ask redirects there */}
          <Route path="/app/ask" element={<Navigate to="/app/workspace" replace />} />
          <Route path="/app/briefings" element={<ProtectedRoute><Briefings /></ProtectedRoute>} />
          <Route path="/app/simulate" element={<ProtectedRoute><Simulate /></ProtectedRoute>} />
          <Route path="/app/lens" element={<ProtectedRoute><LensRoom /></ProtectedRoute>} />
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
