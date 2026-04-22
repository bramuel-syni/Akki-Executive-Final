import React, { useCallback, useEffect, useMemo, useState } from "react";
import AppShell from "@/components/layout/AppShell";
import { useAuth } from "@/contexts/AuthContext";
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
import { useNavigate } from "react-router-dom";
import {
  UserPlus, Trash2, Download, AlertTriangle, X, Copy, History, Users,
  UserCog, ArchiveX, Mail, Clock, CreditCard, Plug, ShieldCheck, Lock,
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
  "invitation.revoked": "Invitation revoked",
  "account.role_declared": "Role declared",
};

const CONTEXT_TYPE_LABEL = {
  ned_personal: "NED · Personal",
  ned_sponsored: "NED · Sponsored",
  executive_personal: "Executive · Personal",
  executive_enterprise: "Executive · Enterprise",
};

export default function Settings() {
  const { account, activeContext, refreshContexts } = useAuth();
  const navigate = useNavigate();
  const contextId = activeContext?.id;
  const isAdmin = activeContext?.my_sub_role === "admin";

  const [contextName, setContextName] = useState(activeContext?.name || "");
  const [renaming, setRenaming] = useState(false);

  const [members, setMembers] = useState([]);
  const [invites, setInvites] = useState([]);
  const [audit, setAudit] = useState([]);

  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("executive");
  const [inviteOpen, setInviteOpen] = useState(false);
  const [inviteBusy, setInviteBusy] = useState(false);
  const [lastInviteLink, setLastInviteLink] = useState("");

  useEffect(() => { setContextName(activeContext?.name || ""); },
    [activeContext?.id, activeContext?.name]);

  const loadAll = useCallback(async () => {
    if (!contextId) return;
    try {
      const [m, i, a] = await Promise.all([
        api.get(`/contexts/${contextId}/members`),
        api.get(`/contexts/${contextId}/invitations`),
        api.get(`/contexts/${contextId}/audit-log`),
      ]);
      setMembers(m.data); setInvites(i.data); setAudit(a.data);
    } catch (e) { toast.error(apiErrorMessage(e, "Failed to load settings")); }
  }, [contextId]);

  useEffect(() => { loadAll(); }, [loadAll]);

  const onRename = async (e) => {
    e.preventDefault();
    if (!contextName.trim() || contextName === activeContext.name) return;
    setRenaming(true);
    try {
      await api.patch(`/contexts/${contextId}`, { name: contextName.trim() });
      await refreshContexts(); await loadAll();
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
      await loadAll();
      toast.success(`Invitation sent to ${data.email}`);
    } catch (err) { toast.error(apiErrorMessage(err)); }
    finally { setInviteBusy(false); }
  };

  const onRemoveMember = async (accountId) => {
    try {
      await api.delete(`/contexts/${contextId}/members/${accountId}`);
      await loadAll(); toast.success("Member removed");
    } catch (e) { toast.error(apiErrorMessage(e)); }
  };

  const onRevokeInvite = async (inviteId) => {
    try {
      await api.delete(`/contexts/${contextId}/invitations/${inviteId}`);
      await loadAll(); toast.success("Invitation revoked");
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
      await loadAll(); toast.success("Export downloaded");
    } catch (e) { toast.error(e.message || "Export failed"); }
  };

  const onArchive = async () => {
    try {
      await api.delete(`/contexts/${contextId}`);
      toast.success("Context archived");
      await refreshContexts(); navigate("/app");
    } catch (e) { toast.error(apiErrorMessage(e)); }
  };

  const orderedAudit = useMemo(() => audit.slice().sort((a, b) =>
    (b.created_at || "").localeCompare(a.created_at || "")), [audit]);

  if (!activeContext) {
    return <AppShell><div className="p-12 text-center text-slate-500 text-sm">No context selected.</div></AppShell>;
  }

  return (
    <AppShell>
      <div className="p-8 max-w-6xl mx-auto">
        <div className="mb-8">
          <p className="akki-overline mb-2">Administration · Module M0</p>
          <h1 className="text-3xl font-light tracking-tight text-[#0A1F44]">Settings</h1>
          <p className="text-sm text-slate-500 mt-2">
            Manage your account, contexts, and audit trail. Billing, Integrations, and Enterprise Admin unlock in later modules.
          </p>
        </div>

        <Tabs defaultValue="context" className="w-full">
          <TabsList className="bg-transparent border-b border-[#E1E6ED] w-full justify-start h-auto p-0 rounded-none mb-8 overflow-x-auto">
            {[
              ["context", "Context", UserCog],
              ["members", "Members", Users],
              ["audit", "Audit log", History],
              ["billing", "Billing", CreditCard, "M4"],
              ["integrations", "Integrations", Plug, "M6"],
              ["privacy", "Privacy", ShieldCheck, "M9"],
              ["danger", "Danger zone", AlertTriangle],
            ].map(([v, l, I, lock]) => (
              <TabsTrigger
                key={v} value={v}
                disabled={!!lock}
                className="relative bg-transparent data-[state=active]:shadow-none data-[state=active]:bg-transparent rounded-none text-sm text-slate-500 data-[state=active]:text-[#0A1F44] py-3 px-5 border-b-2 border-transparent data-[state=active]:border-[#C9A961] disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap"
                data-testid={`settings-tab-${v}`}
              >
                <I className="w-4 h-4 mr-2" strokeWidth={1.7} />
                {l}
                {lock && <span className="ml-2 text-[9px] uppercase tracking-wider text-slate-400 bg-slate-100 px-1.5 py-0.5 rounded-sm">{lock}</span>}
              </TabsTrigger>
            ))}
          </TabsList>

          {/* CONTEXT (was General) */}
          <TabsContent value="context" className="space-y-8">
            <section className="bg-white border border-[#E1E6ED] rounded-sm">
              <div className="px-6 py-4 border-b border-[#E1E6ED]">
                <p className="text-sm font-medium text-[#0A1F44]">Context identity</p>
                <p className="text-xs text-slate-500 mt-0.5">
                  Visible to every member. Context type affects data isolation and ownership rules.
                </p>
              </div>
              <form onSubmit={onRename} className="p-6 space-y-4 max-w-md" data-testid="rename-form">
                <div className="space-y-2">
                  <Label className="text-xs uppercase tracking-wider text-slate-500 font-semibold">Context name</Label>
                  <Input
                    value={contextName}
                    onChange={(e) => setContextName(e.target.value)}
                    disabled={!isAdmin}
                    className="rounded-sm h-10"
                    data-testid="context-name-input"
                  />
                </div>
                {isAdmin ? (
                  <Button
                    type="submit"
                    disabled={renaming || contextName === activeContext.name || !contextName.trim()}
                    className="bg-[#0A1F44] hover:bg-[#0E2958] rounded-sm h-9"
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
                <p className="text-sm font-medium text-[#0A1F44]">Context detail</p>
              </div>
              <div className="p-6 grid grid-cols-2 md:grid-cols-4 gap-8 text-sm">
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-slate-400 mb-1">Type</p>
                  <p className="font-medium text-[#0A1F44]">{CONTEXT_TYPE_LABEL[activeContext.type] || activeContext.type}</p>
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-slate-400 mb-1">Your role</p>
                  <p className="font-medium text-[#0A1F44] capitalize">{activeContext.my_role}</p>
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-slate-400 mb-1">Provisioning</p>
                  <p className="font-medium text-[#0A1F44] capitalize">{activeContext.provisioning}</p>
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-slate-400 mb-1">Data ownership</p>
                  <p className="font-medium text-[#0A1F44] capitalize">{activeContext.data_ownership}</p>
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-slate-400 mb-1">Status</p>
                  <p className="font-medium text-[#0A1F44] capitalize">{activeContext.status}</p>
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-slate-400 mb-1">MFA</p>
                  <p className="font-medium text-[#0A1F44] flex items-center gap-1">
                    {account?.mfa_enabled
                      ? <><Lock className="w-3 h-3 text-emerald-600" /> Enabled</>
                      : <span className="text-amber-600">Off</span>}
                  </p>
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-slate-400 mb-1">Created</p>
                  <p className="font-medium text-[#0A1F44]">{formatDate(activeContext.created_at)}</p>
                </div>
              </div>
            </section>

            <section className="bg-white border border-[#E1E6ED] rounded-sm">
              <div className="px-6 py-4 border-b border-[#E1E6ED] flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-[#0A1F44]">Export context data</p>
                  <p className="text-xs text-slate-500 mt-0.5">
                    JSON snapshot of context, members, invitations, audit log, telemetry, and consent decisions.
                  </p>
                </div>
                {isAdmin && (
                  <Button onClick={onExport} variant="outline" className="rounded-sm h-9 border-[#E1E6ED]" data-testid="export-context-btn">
                    <Download className="w-4 h-4 mr-2" /> Export JSON
                  </Button>
                )}
              </div>
            </section>
          </TabsContent>

          {/* MEMBERS */}
          <TabsContent value="members" className="space-y-8">
            <section className="bg-white border border-[#E1E6ED] rounded-sm">
              <div className="px-6 py-4 border-b border-[#E1E6ED] flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-[#0A1F44]">Members <span className="text-slate-400 font-normal">({members.length})</span></p>
                  <p className="text-xs text-slate-500 mt-0.5">Admins manage context settings; members contribute.</p>
                </div>
                {isAdmin && (
                  <Dialog open={inviteOpen} onOpenChange={setInviteOpen}>
                    <DialogTrigger asChild>
                      <Button className="bg-[#C9A961] hover:bg-[#B39556] text-[#0A1F44] rounded-sm h-9 font-medium" data-testid="open-invite-dialog-btn">
                        <UserPlus className="w-4 h-4 mr-2" /> Invite member
                      </Button>
                    </DialogTrigger>
                    <DialogContent className="rounded-sm sm:max-w-md">
                      <DialogHeader>
                        <DialogTitle className="font-light tracking-tight text-xl text-[#0A1F44]">Invite to {activeContext.name}</DialogTitle>
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
                            className="rounded-sm h-10"
                            placeholder="colleague@company.com"
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
                          <div className="border border-dashed border-[#C9A961]/50 bg-amber-50/40 p-3 rounded-sm text-xs">
                            <p className="text-[10px] uppercase tracking-wider text-[#C9A961] font-bold mb-1">Share link (stubbed email)</p>
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
                          <Button type="submit" disabled={inviteBusy} className="bg-[#0A1F44] hover:bg-[#0E2958] rounded-sm h-9" data-testid="invite-submit-btn">
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
                                <p className="text-sm font-medium text-[#0A1F44]">
                                  {m.name || m.email} {isMe && <span className="text-[10px] font-normal text-slate-400 ml-1">(you)</span>}
                                </p>
                                {isContextOwner && <p className="text-[10px] uppercase tracking-wider text-[#C9A961]">Context owner</p>}
                              </div>
                            </div>
                          </td>
                          <td className="px-6 py-3 text-sm text-slate-600">{m.email}</td>
                          <td className="px-6 py-3">
                            <span className={`inline-flex items-center px-2 py-1 rounded-sm text-[10px] font-medium uppercase tracking-wider ${m.sub_role === "admin" ? "bg-amber-50 text-[#C9A961] border border-[#C9A961]/30" : "bg-slate-100 text-slate-700 border border-slate-200"}`}>
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
                  <p className="text-sm font-medium text-[#0A1F44]">Pending invitations <span className="text-slate-400 font-normal">({invites.length})</span></p>
                </div>
                <div>
                  {invites.map((inv) => (
                    <div key={inv.id} className="px-6 py-4 border-b last:border-b-0 border-[#E1E6ED] flex items-center justify-between" data-testid={`invite-row-${inv.id}`}>
                      <div className="flex items-center gap-3">
                        <Mail className="w-4 h-4 text-slate-400" />
                        <div>
                          <p className="text-sm text-[#0A1F44]">{inv.email}</p>
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
                <p className="text-sm font-medium text-[#0A1F44]">Audit timeline</p>
                <p className="text-xs text-slate-500 mt-0.5">Every privileged action is logged. Reads are never recorded.</p>
              </div>
              <div className="p-6">
                {orderedAudit.length === 0 ? (
                  <p className="text-sm text-slate-500 py-6 text-center">No activity yet.</p>
                ) : (
                  <ol className="relative border-l border-[#E1E6ED] ml-2 space-y-6" data-testid="audit-timeline">
                    {orderedAudit.map((e) => (
                      <li key={e.id} className="pl-6 relative">
                        <span className="absolute -left-[5px] top-1 w-2 h-2 bg-[#C9A961] rounded-full" />
                        <div className="flex items-baseline justify-between gap-4">
                          <div>
                            <p className="text-sm text-[#0A1F44] font-medium">
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
                    <p className="text-sm font-medium text-[#0A1F44] mb-1">Archive this context</p>
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
