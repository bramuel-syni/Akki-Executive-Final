import React, { useCallback, useEffect, useMemo, useState } from "react";
import AppShell from "@/components/layout/AppShell";
import { useAuth } from "@/contexts/AuthContext";
import CommitteeManager from "@/components/settings/CommitteeManager";
import BillingTab from "@/components/settings/BillingTab";
import InboundEmailPanel from "@/components/settings/InboundEmailPanel";
import { api, apiErrorMessage } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader,
  DialogTitle, DialogTrigger,
} from "@/components/ui/dialog";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { toast } from "sonner";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  UserPlus, Trash2, Download, AlertTriangle, X, Copy, History, Users,
  UserCog, ArchiveX, Mail, Clock, CreditCard, Plug, ShieldCheck, Lock,
  UserCircle2, Layers, LogOut as LogOutIcon, Check, Star, Eye, Landmark,
  Briefcase, Sparkles, Building2,
} from "lucide-react";

const AVATARS = [
  "https://images.unsplash.com/photo-1642257834579-eee89ff3e9fd?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NDQ2NDF8MHwxfHNlYXJjaHwxfHxhZnJpY2FuJTIwYnVzaW5lc3MlMjBleGVjdXRpdmUlMjBwb3J0cmFpdHxlbnwwfHx8fDE3NzY1MzA5MTl8MA&ixlib=rb-4.1.0&q=85",
  "https://images.unsplash.com/photo-1637684666587-91e51b10a555?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NDQ2NDF8MHwxfHNlYXJjaHwyfHxhZnJpY2FuJTIwYnVzaW5lc3MlMjBleGVjdXRpdmUlMjBwb3J0cmFpdHxlbnwwfHx8fDE3NzY1MzA5MTl8MA&ixlib=rb-4.1.0&q=85",
  "https://images.unsplash.com/photo-1686628269082-c92c3189903f?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NDQ2NDF8MHwxfHNlYXJjaHwzfHxhZnJpY2FuJTIwYnVzaW5lc3MlMjBleGVjdXRpdmUlMjBwb3J0cmFpdHxlbnwwfHx8fDE3NzY1MzA5MTl8MA&ixlib=rb-4.1.0&q=85",
];

function avatarFor(email) {
  let h = 0;
  for (let i = 0; i < (email || "").length; i++) h = (h * 31 + email.charCodeAt(i)) | 0;
  return AVATARS[Math.abs(h) % AVATARS.length];
}

function formatDate(iso) {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
  } catch { return iso; }
}

const ACTION_LABELS = {
  "context.created": "Context created",
  "context.renamed": "Context renamed",
  "context.archived": "Context archived",
  "context.exported": "Data exported",
  "member.invited": "Member invited",
  "member.joined": "Member joined",
  "member.removed": "Member removed",
  "member.left": "Member left",
  "invitation.revoked": "Invitation revoked",
  "account.role_declared": "Role declared",
  "account.updated": "Account updated",
};

const CONTEXT_TYPE_LABEL = {
  ned_personal: "NED · Personal",
  ned_sponsored: "NED · Sponsored",
  executive_personal: "Executive · Personal",
  executive_enterprise: "Executive · Enterprise",
};

function ContextTypeBadge({ type }) {
  const isSponsored = type === "ned_sponsored" || type === "executive_enterprise";
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-sm text-[10px] font-medium uppercase tracking-wider ${isSponsored ? "bg-amber-50 text-[var(--accent)] border border-[var(--accent)]/30" : "bg-slate-100 text-slate-600 border border-slate-200"}`}>
      {CONTEXT_TYPE_LABEL[type] || type}
    </span>
  );
}

export default function Settings() {
  const { account, activeContext, contexts, switchContext, refreshContexts, bootstrap } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const contextId = activeContext?.id;
  const isAdmin = activeContext?.my_sub_role === "admin";

  // Tab deep-link: accept either ?tab=privacy or ?tab=trust (alias from the
  // global trust footer) — they render the same surface. Falls back to 'account'.
  // Also accept the path /app/settings/billing as an alias for ?tab=billing
  // (Stripe redirect lands there with ?session_id=...).
  const tabParam = (searchParams.get("tab") || "").toLowerCase();
  const onBillingPath = typeof window !== "undefined" && window.location.pathname.endsWith("/billing");
  const defaultTab = onBillingPath ? "billing" :
    tabParam === "trust" ? "privacy" :
    (tabParam && ["account", "contexts", "context", "members", "audit", "privacy", "danger", "billing", "integrations"].includes(tabParam))
      ? tabParam : "account";

  // Account editing
  const [accountName, setAccountName] = useState(account?.name || "");
  const [accountRole, setAccountRole] = useState(account?.declared_role || "undeclared");
  const [savingAccount, setSavingAccount] = useState(false);

  // Context editing
  const [contextName, setContextName] = useState(activeContext?.name || "");
  const [renaming, setRenaming] = useState(false);

  // Members / invites / audit
  const [members, setMembers] = useState([]);
  const [invites, setInvites] = useState([]);
  const [audit, setAudit] = useState([]);
  const [consentLog, setConsentLog] = useState([]);

  // Invite
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("executive");
  const [inviteOpen, setInviteOpen] = useState(false);
  const [inviteBusy, setInviteBusy] = useState(false);
  const [lastInviteLink, setLastInviteLink] = useState("");

  useEffect(() => {
    setContextName(activeContext?.name || "");
  }, [activeContext?.id, activeContext?.name]);

  useEffect(() => {
    setAccountName(account?.name || "");
    setAccountRole(account?.declared_role || "undeclared");
  }, [account?.id, account?.name, account?.declared_role]);

  const loadContextData = useCallback(async () => {
    if (!contextId) return;
    try {
      const [m, i, a] = await Promise.all([
        api.get(`/contexts/${contextId}/members`),
        api.get(`/contexts/${contextId}/invitations`),
        api.get(`/contexts/${contextId}/audit-log`),
      ]);
      setMembers(m.data); setInvites(i.data); setAudit(a.data);
    } catch (e) { toast.error(apiErrorMessage(e, "Failed to load context data")); }
  }, [contextId]);

  const loadConsent = useCallback(async () => {
    try {
      const { data } = await api.get("/accounts/me/consent-decisions");
      setConsentLog(data);
    } catch { /* silent — empty state is fine */ }
  }, []);

  useEffect(() => { loadContextData(); }, [loadContextData]);
  useEffect(() => { loadConsent(); }, [loadConsent]);

  // --- Handlers ---
  const onSaveAccount = async (e) => {
    e.preventDefault();
    setSavingAccount(true);
    try {
      await api.patch("/accounts/me", {
        name: accountName.trim(),
        declared_role: accountRole,
      });
      await bootstrap();
      toast.success("Account updated");
    } catch (err) { toast.error(apiErrorMessage(err)); }
    finally { setSavingAccount(false); }
  };

  const onSetDefault = async (cid) => {
    try {
      await api.post("/accounts/me/default-context", { context_id: cid });
      await bootstrap();
      toast.success("Default context updated");
    } catch (e) { toast.error(apiErrorMessage(e)); }
  };

  const onLeaveContext = async (cid) => {
    try {
      await api.post(`/contexts/${cid}/leave`);
      await refreshContexts();
      toast.success("You've left the context");
      if (cid === activeContext?.id && contexts.length > 1) {
        const next = contexts.find((c) => c.id !== cid);
        if (next) switchContext(next.id);
      }
    } catch (e) { toast.error(apiErrorMessage(e)); }
  };

  const onRename = async (e) => {
    e.preventDefault();
    if (!contextName.trim() || contextName === activeContext.name) return;
    setRenaming(true);
    try {
      await api.patch(`/contexts/${contextId}`, { name: contextName.trim() });
      await refreshContexts(); await loadContextData();
      toast.success("Context renamed");
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setRenaming(false); }
  };

  const onInvite = async (e) => {
    e.preventDefault();
    setInviteBusy(true);
    try {
      const { data } = await api.post(`/contexts/${contextId}/invitations`, {
        email: inviteEmail, role: inviteRole,
      });
      setLastInviteLink(data.accept_url); setInviteEmail(""); setInviteRole("executive");
      await loadContextData();
      toast.success(`Invitation sent to ${data.email}`);
    } catch (err) { toast.error(apiErrorMessage(err)); }
    finally { setInviteBusy(false); }
  };

  const onRemoveMember = async (accountIdToRemove) => {
    try {
      await api.delete(`/contexts/${contextId}/members/${accountIdToRemove}`);
      await loadContextData(); toast.success("Member removed");
    } catch (e) { toast.error(apiErrorMessage(e)); }
  };

  const onRevokeInvite = async (inviteId) => {
    try {
      await api.delete(`/contexts/${contextId}/invitations/${inviteId}`);
      await loadContextData(); toast.success("Invitation revoked");
    } catch (e) { toast.error(apiErrorMessage(e)); }
  };

  const onExport = async () => {
    try {
      const res = await fetch(`${api.defaults.baseURL}/contexts/${contextId}/export`,
        { method: "POST", credentials: "include" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      const disp = res.headers.get("Content-Disposition") || "";
      const match = /filename="([^"]+)"/.exec(disp);
      a.href = url;
      a.download = match ? match[1] : `akki-export-${contextId}.json`;
      a.click(); URL.revokeObjectURL(url);
      await loadContextData(); toast.success("Export downloaded");
    } catch (e) { toast.error(e.message || "Export failed"); }
  };

  const onArchive = async () => {
    try {
      await api.delete(`/contexts/${contextId}`);
      toast.success("Context archived");
      await refreshContexts(); navigate("/app");
    } catch (e) { toast.error(apiErrorMessage(e)); }
  };

  const orderedAudit = useMemo(() =>
    audit.slice().sort((a, b) => (b.created_at || "").localeCompare(a.created_at || "")),
  [audit]);

  if (!activeContext) {
    return <AppShell><div className="p-12 text-center text-slate-500 text-sm">No context selected.</div></AppShell>;
  }

  const roleIcon = accountRole === "ned" ? Landmark : accountRole === "dual" ? Layers : Briefcase;
  const AccRoleIcon = roleIcon;

  return (
    <AppShell>
      <div className="p-8 max-w-6xl mx-auto">
        <div className="mb-8">
          <p className="akki-overline mb-2">Administration · Module M1</p>
          <h1 className="text-3xl font-light tracking-tight text-[var(--ink)]">Settings</h1>
          <p className="text-sm text-slate-500 mt-2">
            Your account, your contexts, and how AKKI treats your data.
          </p>
        </div>

        <Tabs defaultValue={defaultTab} className="w-full">
          <TabsList className="bg-transparent border-b border-[#E1E6ED] w-full justify-start h-auto p-0 rounded-none mb-8 overflow-x-auto">
            {[
              ["account", "Account", UserCircle2],
              ["contexts", "Contexts", Layers],
              ["context", "This context", UserCog],
              ["members", "Members", Users],
              ["audit", "Audit log", History],
              ["privacy", "Trust", ShieldCheck],
              ["billing", "Billing", CreditCard],
              ["integrations", "Integrations", Plug],
              ["danger", "Danger", AlertTriangle],
            ].map(([v, l, I, lock]) => (
              <TabsTrigger
                key={v} value={v}
                disabled={!!lock}
                className="relative bg-transparent data-[state=active]:shadow-none data-[state=active]:bg-transparent rounded-none text-sm text-slate-500 data-[state=active]:text-[var(--ink)] py-3 px-5 border-b-2 border-transparent data-[state=active]:border-[var(--accent)] disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap"
                data-testid={`settings-tab-${v}`}
              >
                <I className="w-4 h-4 mr-2" strokeWidth={1.7} />
                {l}
                {lock && <span className="ml-2 text-[9px] uppercase tracking-wider text-slate-400 bg-slate-100 px-1.5 py-0.5 rounded-sm">{lock}</span>}
              </TabsTrigger>
            ))}
          </TabsList>

          {/* ACCOUNT */}
          <TabsContent value="account" className="space-y-8">
            <section className="bg-white border border-[#E1E6ED] rounded-sm">
              <div className="px-6 py-4 border-b border-[#E1E6ED] flex items-center gap-4">
                <img src={avatarFor(account?.email)} alt="" className="w-12 h-12 rounded-sm object-cover" />
                <div>
                  <p className="text-sm font-medium text-[var(--ink)]">{account?.name || "—"}</p>
                  <p className="text-xs text-slate-500">{account?.email}</p>
                </div>
                <div className="ml-auto flex items-center gap-1.5 text-[10px] uppercase tracking-[0.2em] text-[var(--accent)]">
                  <AccRoleIcon className="w-3 h-3" strokeWidth={2} />
                  {account?.declared_role === "dual" ? "NED + Executive" : account?.declared_role}
                </div>
              </div>
              <form onSubmit={onSaveAccount} className="p-6 space-y-5 max-w-lg" data-testid="account-form">
                <div className="space-y-2">
                  <Label className="text-xs uppercase tracking-wider text-slate-500 font-semibold">Name</Label>
                  <Input
                    value={accountName} onChange={(e) => setAccountName(e.target.value)}
                    className="rounded-sm h-10"
                    data-testid="account-name-input"
                  />
                </div>
                <div className="space-y-2">
                  <Label className="text-xs uppercase tracking-wider text-slate-500 font-semibold">Email</Label>
                  <Input value={account?.email || ""} disabled className="rounded-sm h-10 bg-slate-50" />
                  <p className="text-[10px] text-slate-400">Email cannot be changed in this build.</p>
                </div>
                <div className="space-y-2">
                  <Label className="text-xs uppercase tracking-wider text-slate-500 font-semibold">Declared role</Label>
                  <Select value={accountRole} onValueChange={setAccountRole}>
                    <SelectTrigger className="rounded-sm h-10 max-w-sm" data-testid="account-role-select">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="rounded-sm">
                      <SelectItem value="executive">Executive only</SelectItem>
                      <SelectItem value="ned">Non-Executive Director only</SelectItem>
                      <SelectItem value="dual">Both — NED + Executive</SelectItem>
                      <SelectItem value="undeclared">Undeclared</SelectItem>
                    </SelectContent>
                  </Select>
                  <p className="text-[10px] text-slate-400">
                    Changing role affects which surfaces are emphasised on Home.
                  </p>
                </div>
                <Button
                  type="submit" disabled={savingAccount}
                  className="bg-[var(--ink)] hover:bg-[#0E2958] rounded-sm h-9"
                  data-testid="save-account-btn"
                >
                  {savingAccount ? "Saving…" : "Save changes"}
                </Button>
              </form>
            </section>

            <section className="bg-white border border-[#E1E6ED] rounded-sm">
              <div className="px-6 py-4 border-b border-[#E1E6ED] flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-[var(--ink)] flex items-center gap-2">
                    <Lock className="w-4 h-4 text-[var(--accent)]" /> Account security
                  </p>
                  <p className="text-xs text-slate-500 mt-0.5">
                    Two-factor authentication, session management, sign-out.
                  </p>
                </div>
                <Button
                  onClick={() => navigate("/app/security")}
                  variant="outline"
                  className="rounded-sm h-9 border-[#E1E6ED]"
                  data-testid="open-security-btn"
                >
                  Manage security
                </Button>
              </div>
              <div className="px-6 py-4 flex items-center justify-between text-sm">
                <div className="flex items-center gap-3">
                  <span className="text-slate-500">Two-factor authentication</span>
                  <span className={`text-[10px] uppercase tracking-wider px-2 py-1 rounded-sm ${account?.mfa_enabled ? "bg-emerald-50 text-emerald-700 border border-emerald-200" : "bg-amber-50 text-amber-700 border border-amber-200"}`}>
                    {account?.mfa_enabled ? "Enabled" : "Off"}
                  </span>
                </div>
              </div>
            </section>
          </TabsContent>

          {/* CONTEXTS list */}
          <TabsContent value="contexts" className="space-y-6">
            <section>
              <div className="flex items-end justify-between mb-5">
                <div>
                  <p className="akki-overline mb-2">Your contexts</p>
                  <h2 className="text-xl font-medium tracking-tight text-[var(--ink)]">
                    {contexts.length} {contexts.length === 1 ? "context" : "contexts"}
                  </h2>
                </div>
                <Button
                  onClick={() => navigate("/app/contexts/new")}
                  className="bg-[var(--accent)] hover:bg-[var(--accent)] text-[var(--ink)] rounded-sm h-9 font-medium"
                  data-testid="add-context-btn"
                >
                  <Sparkles className="w-4 h-4 mr-2" /> Add context
                </Button>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {contexts.map((c) => {
                  const isActive = c.id === activeContext?.id;
                  const isDefault = c.id === account?.default_context_id;
                  const isOwner = c.owner_account_id === account?.id;
                  const ContextIcon = c.type?.startsWith("ned") ? Landmark : Building2;
                  return (
                    <div
                      key={c.id}
                      className={`relative bg-white border rounded-sm p-5 transition-colors ${isActive ? "border-[var(--accent)] ring-1 ring-[var(--accent)]/30" : "border-[#E1E6ED] hover:border-slate-300"}`}
                      data-testid={`context-card-${c.id}`}
                    >
                      <div className="flex items-start justify-between mb-3">
                        <ContextIcon className={`w-5 h-5 ${isActive ? "text-[var(--accent)]" : "text-slate-400"}`} strokeWidth={1.6} />
                        {isDefault && (
                          <span className="inline-flex items-center gap-1 text-[9px] uppercase tracking-widest text-[var(--accent)]">
                            <Star className="w-3 h-3 fill-[var(--accent)]" /> Default
                          </span>
                        )}
                      </div>
                      <p className="text-[var(--ink)] font-medium mb-1">{c.name}</p>
                      <div className="flex items-center gap-2 flex-wrap mb-4">
                        <ContextTypeBadge type={c.type} />
                        {c.my_role && (
                          <span className="text-[10px] uppercase tracking-wider text-slate-500">
                            Your role: <span className="text-[var(--ink)] font-medium">{c.my_role}</span>
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-2 flex-wrap">
                        {!isActive && (
                          <Button
                            size="sm" variant="outline"
                            className="rounded-sm h-8 text-xs border-[#E1E6ED]"
                            onClick={() => switchContext(c.id)}
                            data-testid={`switch-to-${c.id}`}
                          >
                            <Eye className="w-3.5 h-3.5 mr-1.5" /> Switch to
                          </Button>
                        )}
                        {!isDefault && (
                          <Button
                            size="sm" variant="outline"
                            className="rounded-sm h-8 text-xs border-[#E1E6ED]"
                            onClick={() => onSetDefault(c.id)}
                            data-testid={`set-default-${c.id}`}
                          >
                            <Star className="w-3.5 h-3.5 mr-1.5" /> Set default
                          </Button>
                        )}
                        {!isOwner && (
                          <AlertDialog>
                            <AlertDialogTrigger asChild>
                              <Button
                                size="sm" variant="ghost"
                                className="rounded-sm h-8 text-xs text-red-600 hover:bg-red-50 hover:text-red-700"
                                data-testid={`leave-context-${c.id}`}
                              >
                                <LogOutIcon className="w-3.5 h-3.5 mr-1.5" /> Leave
                              </Button>
                            </AlertDialogTrigger>
                            <AlertDialogContent className="rounded-sm">
                              <AlertDialogHeader>
                                <AlertDialogTitle>Leave {c.name}?</AlertDialogTitle>
                                <AlertDialogDescription>
                                  You'll lose access immediately. An admin will need to re-invite you to return.
                                </AlertDialogDescription>
                              </AlertDialogHeader>
                              <AlertDialogFooter>
                                <AlertDialogCancel className="rounded-sm">Cancel</AlertDialogCancel>
                                <AlertDialogAction className="bg-red-600 hover:bg-red-700 rounded-sm" onClick={() => onLeaveContext(c.id)} data-testid={`confirm-leave-${c.id}`}>
                                  Leave context
                                </AlertDialogAction>
                              </AlertDialogFooter>
                            </AlertDialogContent>
                          </AlertDialog>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </section>
          </TabsContent>

          {/* CONTEXT (active one) */}
          <TabsContent value="context" className="space-y-8">
            <section className="bg-white border border-[#E1E6ED] rounded-sm">
              <div className="px-6 py-4 border-b border-[#E1E6ED]">
                <p className="text-sm font-medium text-[var(--ink)]">Context identity</p>
                <p className="text-xs text-slate-500 mt-0.5">Visible to every member of this context.</p>
              </div>
              <form onSubmit={onRename} className="p-6 space-y-4 max-w-md" data-testid="rename-form">
                <div className="space-y-2">
                  <Label className="text-xs uppercase tracking-wider text-slate-500 font-semibold">Context name</Label>
                  <Input
                    value={contextName} onChange={(e) => setContextName(e.target.value)}
                    disabled={!isAdmin} className="rounded-sm h-10"
                    data-testid="context-name-input"
                  />
                </div>
                {isAdmin ? (
                  <Button
                    type="submit"
                    disabled={renaming || contextName === activeContext.name || !contextName.trim()}
                    className="bg-[var(--ink)] hover:bg-[#0E2958] rounded-sm h-9"
                    data-testid="rename-submit-btn"
                  >
                    {renaming ? "Saving…" : "Save changes"}
                  </Button>
                ) : (
                  <p className="text-xs text-slate-400">Only context admins can rename.</p>
                )}
              </form>
            </section>

            <section className="bg-white border border-[#E1E6ED] rounded-sm">
              <div className="px-6 py-4 border-b border-[#E1E6ED]">
                <p className="text-sm font-medium text-[var(--ink)]">Context detail</p>
              </div>
              <div className="p-6 grid grid-cols-2 md:grid-cols-4 gap-8 text-sm">
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-slate-400 mb-1">Type</p>
                  <p className="font-medium text-[var(--ink)]">{CONTEXT_TYPE_LABEL[activeContext.type] || activeContext.type}</p>
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-slate-400 mb-1">Your role</p>
                  <p className="font-medium text-[var(--ink)] capitalize">{activeContext.my_role}</p>
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-slate-400 mb-1">Provisioning</p>
                  <p className="font-medium text-[var(--ink)] capitalize">{activeContext.provisioning}</p>
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-slate-400 mb-1">Data ownership</p>
                  <p className="font-medium text-[var(--ink)] capitalize">{activeContext.data_ownership}</p>
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-slate-400 mb-1">Status</p>
                  <p className="font-medium text-[var(--ink)] capitalize">{activeContext.status}</p>
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-slate-400 mb-1">Created</p>
                  <p className="font-medium text-[var(--ink)]">{formatDate(activeContext.created_at)}</p>
                </div>
              </div>
            </section>

            <section className="bg-white border border-[#E1E6ED] rounded-sm">
              <div className="px-6 py-4 border-b border-[#E1E6ED] flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-[var(--ink)]">Export context data</p>
                  <p className="text-xs text-slate-500 mt-0.5">
                    JSON snapshot — context, members, invitations, audit, telemetry, consent decisions.
                  </p>
                </div>
                {isAdmin && (
                  <Button onClick={onExport} variant="outline" className="rounded-sm h-9 border-[#E1E6ED]" data-testid="export-context-btn">
                    <Download className="w-4 h-4 mr-2" /> Export JSON
                  </Button>
                )}
              </div>
            </section>

            <CommitteeManager />
          </TabsContent>

          {/* MEMBERS */}
          <TabsContent value="members" className="space-y-8">
            <section className="bg-white border border-[#E1E6ED] rounded-sm">
              <div className="px-6 py-4 border-b border-[#E1E6ED] flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-[var(--ink)]">Members <span className="text-slate-400 font-normal">({members.length})</span></p>
                  <p className="text-xs text-slate-500 mt-0.5">Admins manage this context; members contribute.</p>
                </div>
                {isAdmin && (
                  <Dialog open={inviteOpen} onOpenChange={setInviteOpen}>
                    <DialogTrigger asChild>
                      <Button className="bg-[var(--accent)] hover:bg-[var(--accent)] text-[var(--ink)] rounded-sm h-9 font-medium" data-testid="open-invite-dialog-btn">
                        <UserPlus className="w-4 h-4 mr-2" /> Invite member
                      </Button>
                    </DialogTrigger>
                    <DialogContent className="rounded-sm sm:max-w-md">
                      <DialogHeader>
                        <DialogTitle className="font-light tracking-tight text-xl text-[var(--ink)]">Invite to {activeContext.name}</DialogTitle>
                        <DialogDescription className="text-slate-500 text-sm">
                          The invitee will receive a context-scoped link. Invites expire in 7 days.
                        </DialogDescription>
                      </DialogHeader>
                      <form onSubmit={onInvite} className="space-y-4 py-2" data-testid="invite-form">
                        <div className="space-y-2">
                          <Label className="text-xs uppercase tracking-wider text-slate-500 font-semibold">Email</Label>
                          <Input
                            type="email" required value={inviteEmail}
                            onChange={(e) => setInviteEmail(e.target.value)}
                            className="rounded-sm h-10" placeholder="colleague@company.com"
                            data-testid="invite-email-input"
                          />
                        </div>
                        <div className="space-y-2">
                          <Label className="text-xs uppercase tracking-wider text-slate-500 font-semibold">Role</Label>
                          <Select value={inviteRole} onValueChange={setInviteRole}>
                            <SelectTrigger className="rounded-sm h-10" data-testid="invite-role-select"><SelectValue /></SelectTrigger>
                            <SelectContent className="rounded-sm">
                              <SelectItem value="executive">Executive</SelectItem>
                              <SelectItem value="ned">Non-Executive Director</SelectItem>
                              <SelectItem value="reportee">Reportee (M10)</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                        {lastInviteLink && (
                          <div className="border border-dashed border-[var(--accent)]/50 bg-amber-50/40 p-3 rounded-sm text-xs">
                            <p className="text-[10px] uppercase tracking-wider text-[var(--accent)] font-bold mb-1">Share link (stubbed email)</p>
                            <div className="flex items-center gap-2">
                              <code className="flex-1 text-[10px] text-slate-600 truncate">{lastInviteLink}</code>
                              <Button type="button" size="sm" variant="outline" className="h-7 rounded-sm"
                                onClick={() => { navigator.clipboard.writeText(lastInviteLink); toast.success("Copied"); }}
                                data-testid="copy-invite-link-btn">
                                <Copy className="w-3 h-3" />
                              </Button>
                            </div>
                          </div>
                        )}
                        <DialogFooter className="pt-2">
                          <Button type="submit" disabled={inviteBusy} className="bg-[var(--ink)] hover:bg-[#0E2958] rounded-sm h-9" data-testid="invite-submit-btn">
                            {inviteBusy ? "Sending…" : "Send invitation"}
                          </Button>
                        </DialogFooter>
                      </form>
                    </DialogContent>
                  </Dialog>
                )}
              </div>

              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="bg-slate-50 border-b border-[#E1E6ED]">
                      <th className="text-left px-6 py-3 text-[10px] font-semibold uppercase tracking-wider text-slate-500">Member</th>
                      <th className="text-left px-6 py-3 text-[10px] font-semibold uppercase tracking-wider text-slate-500">Email</th>
                      <th className="text-left px-6 py-3 text-[10px] font-semibold uppercase tracking-wider text-slate-500">Role</th>
                      <th className="text-left px-6 py-3 text-[10px] font-semibold uppercase tracking-wider text-slate-500">Joined</th>
                      <th className="text-right px-6 py-3 text-[10px] font-semibold uppercase tracking-wider text-slate-500"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {members.map((m) => {
                      const isMe = m.account_id === account?.id;
                      const isContextOwner = m.account_id === activeContext.owner_account_id;
                      return (
                        <tr key={m.account_id} className="border-b border-[#E1E6ED] hover:bg-slate-50/50" data-testid={`member-row-${m.account_id}`}>
                          <td className="px-6 py-3">
                            <div className="flex items-center gap-3">
                              <img src={avatarFor(m.email)} alt="" className="w-8 h-8 rounded-sm object-cover grayscale-[20%]" />
                              <div>
                                <p className="text-sm font-medium text-[var(--ink)]">
                                  {m.name || m.email} {isMe && <span className="text-[10px] font-normal text-slate-400 ml-1">(you)</span>}
                                </p>
                                {isContextOwner && <p className="text-[10px] uppercase tracking-wider text-[var(--accent)]">Context owner</p>}
                              </div>
                            </div>
                          </td>
                          <td className="px-6 py-3 text-sm text-slate-600">{m.email}</td>
                          <td className="px-6 py-3">
                            <span className={`inline-flex items-center px-2 py-1 rounded-sm text-[10px] font-medium uppercase tracking-wider ${m.sub_role === "admin" ? "bg-amber-50 text-[var(--accent)] border border-[var(--accent)]/30" : "bg-slate-100 text-slate-700 border border-slate-200"}`}>
                              {m.role}{m.sub_role === "admin" ? " · admin" : ""}
                            </span>
                          </td>
                          <td className="px-6 py-3 text-sm text-slate-500">{formatDate(m.joined_at)}</td>
                          <td className="px-6 py-3 text-right">
                            {isAdmin && !isContextOwner && (
                              <AlertDialog>
                                <AlertDialogTrigger asChild>
                                  <Button variant="ghost" size="sm" className="h-8 px-2 text-red-600 hover:bg-red-50 hover:text-red-700 rounded-sm" data-testid={`remove-member-${m.account_id}-btn`}>
                                    <Trash2 className="w-4 h-4" />
                                  </Button>
                                </AlertDialogTrigger>
                                <AlertDialogContent className="rounded-sm">
                                  <AlertDialogHeader>
                                    <AlertDialogTitle>Remove {m.name || m.email}?</AlertDialogTitle>
                                    <AlertDialogDescription>
                                      They'll lose access to this context immediately. You can re-invite them later.
                                    </AlertDialogDescription>
                                  </AlertDialogHeader>
                                  <AlertDialogFooter>
                                    <AlertDialogCancel className="rounded-sm">Cancel</AlertDialogCancel>
                                    <AlertDialogAction className="bg-red-600 hover:bg-red-700 rounded-sm" onClick={() => onRemoveMember(m.account_id)} data-testid={`confirm-remove-${m.account_id}`}>
                                      Remove
                                    </AlertDialogAction>
                                  </AlertDialogFooter>
                                </AlertDialogContent>
                              </AlertDialog>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </section>

            {invites.length > 0 && (
              <section className="bg-white border border-[#E1E6ED] rounded-sm">
                <div className="px-6 py-4 border-b border-[#E1E6ED]">
                  <p className="text-sm font-medium text-[var(--ink)]">Pending invitations <span className="text-slate-400 font-normal">({invites.length})</span></p>
                </div>
                <div>
                  {invites.map((inv) => (
                    <div key={inv.id} className="px-6 py-4 border-b last:border-b-0 border-[#E1E6ED] flex items-center justify-between" data-testid={`invite-row-${inv.id}`}>
                      <div className="flex items-center gap-3">
                        <Mail className="w-4 h-4 text-slate-400" />
                        <div>
                          <p className="text-sm text-[var(--ink)]">{inv.email}</p>
                          <p className="text-[10px] uppercase tracking-wider text-slate-400 flex items-center gap-2 mt-0.5">
                            <span>{inv.role}</span>
                            <span>·</span>
                            <span className="flex items-center gap-1"><Clock className="w-2.5 h-2.5" /> expires {formatDate(inv.expires_at)}</span>
                          </p>
                        </div>
                      </div>
                      {isAdmin && (
                        <Button variant="ghost" size="sm" className="text-red-600 hover:bg-red-50 rounded-sm" onClick={() => onRevokeInvite(inv.id)} data-testid={`revoke-invite-${inv.id}-btn`}>
                          <X className="w-4 h-4 mr-1" /> Revoke
                        </Button>
                      )}
                    </div>
                  ))}
                </div>
              </section>
            )}
          </TabsContent>

          {/* AUDIT */}
          <TabsContent value="audit">
            <section className="bg-white border border-[#E1E6ED] rounded-sm">
              <div className="px-6 py-4 border-b border-[#E1E6ED]">
                <p className="text-sm font-medium text-[var(--ink)]">Audit timeline</p>
                <p className="text-xs text-slate-500 mt-0.5">Every privileged action is logged. Reads are never recorded.</p>
              </div>
              <div className="p-6">
                {orderedAudit.length === 0 ? (
                  <p className="text-sm text-slate-500 py-6 text-center">No activity yet.</p>
                ) : (
                  <ol className="relative border-l border-[#E1E6ED] ml-2 space-y-6" data-testid="audit-timeline">
                    {orderedAudit.map((e) => (
                      <li key={e.id} className="pl-6 relative">
                        <span className="absolute -left-[5px] top-1 w-2 h-2 bg-[var(--accent)] rounded-full" />
                        <div className="flex items-baseline justify-between gap-4">
                          <div>
                            <p className="text-sm text-[var(--ink)] font-medium">
                              {ACTION_LABELS[e.action] || e.action}
                            </p>
                            <p className="text-xs text-slate-500 mt-0.5">
                              {e.actor_email || "system"} · {formatDate(e.created_at)}
                            </p>
                            {e.metadata && Object.keys(e.metadata).length > 0 && (
                              <p className="text-[10px] font-mono text-slate-400 mt-1">
                                {Object.entries(e.metadata).slice(0, 3).map(([k, v]) =>
                                  `${k}: ${typeof v === "string" ? v : JSON.stringify(v)}`).join(" · ")}
                              </p>
                            )}
                          </div>
                          <span className="text-[10px] uppercase tracking-wider text-slate-400 shrink-0">
                            {e.resource_type}
                          </span>
                        </div>
                      </li>
                    ))}
                  </ol>
                )}
              </div>
            </section>
          </TabsContent>

          {/* PRIVACY / TRUST — deep-linked via ?tab=trust from the global
              footer. Presents AKKI's data posture as four concrete promises
              the user can verify, above the existing Synisense + consent
              sections. */}
          <TabsContent value="privacy" className="space-y-6">
            <section className="bg-white border border-[#E1E6ED] rounded-sm" data-testid="trust-centre">
              <div className="px-6 py-4 border-b border-[#E1E6ED]">
                <p className="text-sm font-medium text-[var(--ink)] flex items-center gap-2">
                  <ShieldCheck className="w-4 h-4 text-[var(--chrome)]" /> Trust centre
                </p>
                <p className="text-xs text-slate-500 mt-1">
                  Four promises AKKI keeps. Each is enforced in code, not marketing.
                </p>
              </div>
              <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-6 text-sm text-slate-700">
                <div>
                  <p className="text-[10.5px] uppercase tracking-[0.2em] text-[var(--chrome)] font-bold mb-2">01 · Residency</p>
                  <p className="akki-serif text-[15px] text-[var(--ink)] mb-1.5">Your context never leaves this account.</p>
                  <p className="text-[12.5px] text-slate-600 leading-relaxed">
                    Documents, signals, briefings, and lens outputs are scoped to your active context and visible
                    only to its members. No cross-tenant leakage by construction — enforced at query time.
                  </p>
                </div>
                <div>
                  <p className="text-[10.5px] uppercase tracking-[0.2em] text-[var(--chrome)] font-bold mb-2">02 · Shielding</p>
                  <p className="akki-serif text-[15px] text-[var(--ink)] mb-1.5">Identities are masked before any LLM call.</p>
                  <p className="text-[12.5px] text-slate-600 leading-relaxed">
                    Synisense rewrites names, emails, and identifiers to opaque tokens before the prompt leaves
                    the server. Every response surfaces a <code className="text-[11px] bg-slate-100 px-1 py-0.5 rounded-sm">shielding</code> receipt.
                  </p>
                </div>
                <div>
                  <p className="text-[10.5px] uppercase tracking-[0.2em] text-[var(--chrome)] font-bold mb-2">03 · Provenance</p>
                  <p className="akki-serif text-[15px] text-[var(--ink)] mb-1.5">Every signal cites the exact page it came from.</p>
                  <p className="text-[12.5px] text-slate-600 leading-relaxed">
                    Briefings ship with a Receipts slide; lens runs expose Observation → Implication → Action; Ask answers carry <code className="text-[11px] bg-slate-100 px-1 py-0.5 rounded-sm">[doc:xxx]</code> citations. Nothing gets asserted without a source.
                  </p>
                </div>
                <div>
                  <p className="text-[10.5px] uppercase tracking-[0.2em] text-[var(--chrome)] font-bold mb-2">04 · Control</p>
                  <p className="akki-serif text-[15px] text-[var(--ink)] mb-1.5">You can export or delete everything, any time.</p>
                  <p className="text-[12.5px] text-slate-600 leading-relaxed">
                    The Audit log tab shows every action taken on this context. The Danger tab exports the full context as JSON or archives it. Sandbox data is hard-deleted on day 22 automatically.
                  </p>
                </div>
              </div>
            </section>

            <section className="bg-white border border-[#E1E6ED] rounded-sm">
              <div className="px-6 py-4 border-b border-[#E1E6ED]">
                <p className="text-sm font-medium text-[var(--ink)] flex items-center gap-2">
                  <ShieldCheck className="w-4 h-4 text-[var(--accent)]" /> Synisense identity shielding
                </p>
              </div>
              <div className="p-6 space-y-4 text-sm text-slate-700 leading-relaxed max-w-3xl">
                <p>
                  Every outbound LLM call is routed through Synisense first. Names, emails, organisation
                  identifiers and other identity tokens are replaced with opaque references before the
                  payload reaches any external model. Responses are rehydrated server-side so you
                  never see the masked refs.
                </p>
                <p>
                  The Lens is governed by strict framework guardrails — intellectual tools are
                  applied to ideas, never associated with individuals. You will never see an interpretation
                  that profiles a named person.
                </p>
                <div className="border border-[#E1E6ED] rounded-sm p-4 bg-slate-50/50">
                  <p className="text-[10px] uppercase tracking-[0.2em] text-[var(--accent)] font-bold mb-2">M1 status</p>
                  <p className="text-xs text-slate-600">
                    Running in <strong className="text-[var(--ink)]">mock-scaffolding</strong> mode. A live Synisense service
                    replaces the mock at M5. Your shielding contract is already enforced on every call.
                  </p>
                </div>
              </div>
            </section>

            <section className="bg-white border border-[#E1E6ED] rounded-sm">
              <div className="px-6 py-4 border-b border-[#E1E6ED]">
                <p className="text-sm font-medium text-[var(--ink)]">Consent decisions</p>
                <p className="text-xs text-slate-500 mt-0.5">
                  Immutable record of consent granted/withdrawn for sponsored contexts. Populated when someone sponsors a seat for you in M4.
                </p>
              </div>
              <div className="p-6">
                {consentLog.length === 0 ? (
                  <p className="text-sm text-slate-400 py-4 text-center italic">
                    No consent decisions recorded yet. This ledger will populate when an organisation sponsors a context for you.
                  </p>
                ) : (
                  <ul className="space-y-3" data-testid="consent-log">
                    {consentLog.map((d) => (
                      <li key={d.id} className="border-l-2 border-[var(--accent)] pl-4 py-1">
                        <p className="text-sm text-[var(--ink)]">{d.decision} · {d.scope}</p>
                        <p className="text-xs text-slate-500">{formatDate(d.decided_at)}</p>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </section>
          </TabsContent>

          {/* BILLING */}
          <TabsContent value="billing">
            <BillingTab />
          </TabsContent>

          {/* INTEGRATIONS */}
          <TabsContent value="integrations" className="space-y-6">
            <InboundEmailPanel
              contextId={activeContext?.id}
              contextName={activeContext?.name}
            />
          </TabsContent>

          {/* DANGER */}
          <TabsContent value="danger">
            <section className="border border-red-200 bg-red-50/40 rounded-sm">
              <div className="px-6 py-4 border-b border-red-200 bg-red-50/80 flex items-center gap-3">
                <AlertTriangle className="w-4 h-4 text-red-600" />
                <p className="text-sm font-medium text-red-700">Danger zone</p>
              </div>
              <div className="p-6 space-y-6">
                <div className="flex items-start justify-between gap-6">
                  <div>
                    <p className="text-sm font-medium text-[var(--ink)] mb-1">Archive this context</p>
                    <p className="text-xs text-slate-600 max-w-xl leading-relaxed">
                      Archiving marks the context inactive and schedules hard purge in 7 days.
                      Members lose access immediately. Admins can export data first.
                    </p>
                  </div>
                  {isAdmin && (
                    <AlertDialog>
                      <AlertDialogTrigger asChild>
                        <Button variant="outline" className="border-red-500 text-red-600 hover:bg-red-50 rounded-sm h-9 whitespace-nowrap" data-testid="archive-context-btn">
                          <ArchiveX className="w-4 h-4 mr-2" /> Archive context
                        </Button>
                      </AlertDialogTrigger>
                      <AlertDialogContent className="rounded-sm">
                        <AlertDialogHeader>
                          <AlertDialogTitle>Archive {activeContext.name}?</AlertDialogTitle>
                          <AlertDialogDescription>
                            This removes member access and schedules a 7-day purge window.
                            Export data first if needed. This action is logged.
                          </AlertDialogDescription>
                        </AlertDialogHeader>
                        <AlertDialogFooter>
                          <AlertDialogCancel className="rounded-sm">Cancel</AlertDialogCancel>
                          <AlertDialogAction className="bg-red-600 hover:bg-red-700 rounded-sm" onClick={onArchive} data-testid="confirm-archive-btn">
                            Archive
                          </AlertDialogAction>
                        </AlertDialogFooter>
                      </AlertDialogContent>
                    </AlertDialog>
                  )}
                </div>
              </div>
            </section>
          </TabsContent>
        </Tabs>
      </div>
    </AppShell>
  );
}
