import React, { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, apiErrorMessage } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import Logo from "@/components/brand/Logo";
import { Button } from "@/components/ui/button";
import { ArrowRight, CheckCircle2, Mail } from "lucide-react";

const CONTEXT_TYPE_LABEL = {
  ned_personal: "NED personal board",
  ned_sponsored: "NED sponsored board",
  executive_personal: "Executive personal company",
  executive_enterprise: "Executive enterprise company",
};

export default function InviteAccept() {
  const { token } = useParams();
  const [preview, setPreview] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [success, setSuccess] = useState(false);
  const { account, refreshContexts, switchContext } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get(`/invitations/by-token/${token}`);
        setPreview(data);
      } catch (e) { setError(apiErrorMessage(e, "Invitation not valid")); }
    })();
  }, [token]);

  const accept = async () => {
    setBusy(true);
    try {
      const { data } = await api.post(`/invitations/${token}/accept`);
      await refreshContexts(); switchContext(data.context.id);
      setSuccess(true);
      setTimeout(() => navigate("/app"), 1400);
    } catch (e) { setError(apiErrorMessage(e)); }
    finally { setBusy(false); }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#FAFBFC] p-6">
      <div className="w-full max-w-md bg-white border border-[#E1E6ED] rounded-sm p-10 akki-fade-up" data-testid="invite-accept-card">
        <div className="mb-8"><Logo size="lg" /></div>
        <p className="akki-overline mb-3">Company invitation</p>

        {error ? (
          <>
            <h1 className="text-2xl font-light tracking-tight text-[var(--ink)] mb-3">Invitation unavailable</h1>
            <p className="text-sm text-slate-600 mb-8">{error}</p>
            <Link to="/signin">
              <Button className="bg-[var(--ink)] hover:bg-[#0E2958] rounded-sm h-10" data-testid="invite-error-signin-btn">
                Back to sign in
              </Button>
            </Link>
          </>
        ) : success ? (
          <>
            <CheckCircle2 className="w-8 h-8 text-emerald-600 mb-4" />
            <h1 className="text-2xl font-light tracking-tight text-[var(--ink)] mb-2">Welcome to {preview?.context_name}</h1>
            <p className="text-sm text-slate-500">Redirecting…</p>
          </>
        ) : preview ? (
          <>
            <h1 className="text-2xl font-light tracking-tight text-[var(--ink)] mb-2">
              Join <span className="text-[var(--accent)]">{preview.context_name}</span>
            </h1>
            <p className="text-sm text-slate-500 mb-1 flex items-center gap-2">
              <Mail className="w-3.5 h-3.5" /> Invited as <strong className="text-[var(--ink)] font-medium">{preview.email}</strong> · {preview.role}
            </p>
            {preview.context_type && (
              <p className="text-[10px] uppercase tracking-[0.2em] text-slate-400 mb-6">
                {CONTEXT_TYPE_LABEL[preview.context_type] || preview.context_type}
              </p>
            )}

            {!account ? (
              <div className="space-y-3 mt-4">
                <p className="text-sm text-slate-600 border border-dashed border-[var(--accent)]/50 bg-amber-50/30 p-4 rounded-sm">
                  Sign in with <strong>{preview.email}</strong> to accept this invitation. If you don't have an account yet, create one with that email first.
                </p>
                <Link to="/signin" state={{ from: `/invite/${token}` }}>
                  <Button className="w-full bg-[var(--ink)] hover:bg-[#0E2958] rounded-sm h-11" data-testid="invite-go-signin-btn">
                    Sign in to accept <ArrowRight className="w-4 h-4 ml-2" />
                  </Button>
                </Link>
                <Link to="/signup" className="block">
                  <Button variant="outline" className="w-full rounded-sm h-11 border-[#E1E6ED]" data-testid="invite-go-signup-btn">
                    Create account
                  </Button>
                </Link>
              </div>
            ) : (
              <div className="space-y-3 mt-4">
                {account.email !== preview.email && (
                  <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 p-3 rounded-sm">
                    You're signed in as {account.email}. This invitation is for {preview.email}.
                    Please sign out and sign back in as {preview.email}.
                  </p>
                )}
                <Button
                  onClick={accept} disabled={busy || account.email !== preview.email}
                  className="w-full bg-[var(--accent)] hover:bg-[var(--accent)] text-[var(--ink)] font-medium rounded-sm h-11"
                  data-testid="invite-accept-btn"
                >
                  {busy ? "Joining…" : `Accept and join ${preview.context_name}`}
                </Button>
              </div>
            )}
          </>
        ) : (
          <p className="text-sm text-slate-500">Loading invitation…</p>
        )}
      </div>
    </div>
  );
}
