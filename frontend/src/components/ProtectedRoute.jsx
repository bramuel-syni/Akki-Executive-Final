import React from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";

export default function ProtectedRoute({ children }) {
  const { account } = useAuth();
  const location = useLocation();

  if (account === null) {
    return (
      <div className="h-screen flex items-center justify-center bg-[#FAFBFC]" data-testid="auth-loading">
        <div className="flex flex-col items-center gap-3">
          <div className="w-1.5 h-1.5 bg-[#C9A961] akki-pulse-gold rounded-full" />
          <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Verifying session</p>
        </div>
      </div>
    );
  }
  if (!account) {
    return <Navigate to="/signin" state={{ from: location.pathname }} replace />;
  }
  return children;
}
