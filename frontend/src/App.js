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

function PublicOnlyRoute({ children }) {
  const { account } = useAuth();
  if (account === null) return null;
  if (account) return <Navigate to="/app" replace />;
  return children;
}

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Toaster position="top-right" richColors />
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/signin" element={<PublicOnlyRoute><SignIn /></PublicOnlyRoute>} />
          <Route path="/signup" element={<PublicOnlyRoute><SignUp /></PublicOnlyRoute>} />
          <Route path="/invite/:token" element={<InviteAccept />} />

          <Route path="/onboarding" element={<ProtectedRoute><Onboarding /></ProtectedRoute>} />
          <Route path="/app" element={<ProtectedRoute><AppHome /></ProtectedRoute>} />
          <Route path="/app/workspace" element={<ProtectedRoute><Workspace /></ProtectedRoute>} />
          <Route path="/app/highlights" element={<ProtectedRoute><Highlights /></ProtectedRoute>} />
          {/* v4.2: Ask merges into Workspace; any /app/ask redirects there */}
          <Route path="/app/ask" element={<Navigate to="/app/workspace" replace />} />
          <Route path="/app/briefings" element={<ProtectedRoute><Briefings /></ProtectedRoute>} />
          <Route path="/app/simulate" element={<ProtectedRoute><Simulate /></ProtectedRoute>} />
          <Route path="/app/lens" element={<ProtectedRoute><LensRoom /></ProtectedRoute>} />
          <Route path="/app/learn" element={<ProtectedRoute><Learn /></ProtectedRoute>} />
          <Route path="/app/learn/:id" element={<ProtectedRoute><Learn /></ProtectedRoute>} />
          <Route path="/app/documents/:id" element={<ProtectedRoute><DocumentViewer /></ProtectedRoute>} />
          <Route path="/app/contexts" element={<ProtectedRoute><ContextPortfolio /></ProtectedRoute>} />
          <Route path="/app/contexts/new" element={<ProtectedRoute><NewContext /></ProtectedRoute>} />
          <Route path="/app/new-workspace" element={<ProtectedRoute><NewContext /></ProtectedRoute>} />
          <Route path="/app/settings" element={<ProtectedRoute><TenantSettings /></ProtectedRoute>} />
          <Route path="/app/security" element={<ProtectedRoute><AccountSecurity /></ProtectedRoute>} />

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
