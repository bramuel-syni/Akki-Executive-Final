/**
 * Manage — housekeeping surface. Two tabs:
 *   • Team      — invite / remove people from the active context
 *   • Companies — add / archive / switch into any of my contexts
 *
 * Meant to be the one place a board-secretary-type can do quick housekeeping
 * without getting lost in the full TenantSettings surface. For deeper
 * controls (committees, invitations history, exports) we link out.
 */
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import AppShell from "@/components/layout/AppShell";
import { useAuth } from "@/contexts/AuthContext";
import { api, apiErrorMessage } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { toast } from "sonner";
import {
  Users, Building2, UserPlus, Trash2, ArrowRight, Plus,
  Landmark, Briefcase, CheckCircle2, ExternalLink, ArchiveX, Layers,
} from "lucide-react";

const TYPE_LABEL = {
  ned_personal: "NED · Personal",
  ned_sponsored: "NED · Sponsored",
  executive_personal: "Executive · Personal",
  executive_enterprise: "Executive · Enterprise",
};

const TABS = [
  { key: "team",      label: "Manage my team",     icon: Users,     testid: "manage-tab-team" },
  { key: "companies", label: "Manage my companies", icon: Building2, testid: "manage-tab-companies" },
];

export default function Manage() {
  const [sp, setSp] = useSearchParams();
  const tabFromUrl = sp.get("tab");
  const initial = TABS.find((t) => t.key === tabFromUrl) ? tabFromUrl : "team";
  const [tab, setTab] = useState(initial);

  useEffect(() => {
    if (sp.get("tab") !== tab) {
      const next = new URLSearchParams(sp);
      next.set("tab", tab);
      setSp(next, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab]);

  return (
    <AppShell>
      <div className="max-w-[1100px] mx-auto px-8 py-10">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, ease: [0.2, 0.8, 0.2, 1] }}
          className="mb-8"
        >
          <p className="akki-overline mb-2">Housekeeping</p>
          <h1 className="akki-greeting mb-2">Your team and your companies.</h1>
          <p className="akki-meta max-w-2xl">
            Invite a colleague. Add a board. Archive one you've stepped off. Quiet, no ceremony.
          </p>
        </motion.div>

        {/* Tab strip */}
        <div className="flex items-center border-b border-[var(--rule)] mb-6" data-testid="manage-tabs">
          {TABS.map((t) => {
            const Icon = t.icon;
            const active = tab === t.key;
            return (
              <button
                key={t.key}
                onClick={() => setTab(t.key)}
                className={`relative flex items-center gap-2 px-5 py-3 text-[13.5px] transition-colors ${
                  active ? "text-[var(--ink)] font-medium" : "text-[var(--muted)] hover:text-[var(--deep)]"
                }`}
                data-testid={t.testid}
              >
                <Icon className={`w-4 h-4 ${active ? "text-[var(--accent)]" : ""}`} strokeWidth={1.8} />
                <span>{t.label}</span>
                {active && (
                  <motion.span
                    layoutId="manage-underline"
                    className="absolute left-0 right-0 -bottom-px h-[2px] bg-[var(--accent)]"
                    transition={{ type: "spring", stiffness: 380, damping: 30 }}
                  />
                )}
              </button>
            );
          })}
        </div>

        <AnimatePresence mode="wait">
          {tab === "team" ? (
            <motion.div
              key="team"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={{ duration: 0.25 }}
            >
              <TeamPanel />
            </motion.div>
          ) : (
            <motion.div
              key="companies"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={{ duration: 0.25 }}
            >
              <CompaniesPanel />
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </AppShell>
  );
}

// ---------------------------------------------------------------------------
// Team panel
// ---------------------------------------------------------------------------
function TeamPanel() {
  const { account, activeContext } = useAuth();
  const contextId = activeContext?.id;
  const imAdmin = activeContext?.my_sub_role === "admin";

  const [members, setMembers] = useState([]);
  const [invites, setInvites] = useState([]);
  const [loading, setLoading] = useState(true);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("executive");
  const [submitting, setSubmitting] = useState(false);

  const load = useCallback(async () => {
    if (!contextId) { setLoading(false); return; }
    setLoading(true);
    try {
      const [m, inv] = await Promise.all([
        api.get(`/contexts/${contextId}/members`),
        api.get(`/contexts/${contextId}/invitations`).catch(() => ({ data: [] })),
      ]);
      setMembers(m.data || []);
      setInvites(inv.data || []);
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setLoading(false); }
  }, [contextId]);

  useEffect(() => { load(); }, [load]);

  const onInvite = async () => {
    if (!inviteEmail.trim()) return toast.error("Enter an email.");
    setSubmitting(true);
    try {
      await api.post(`/contexts/${contextId}/invitations`, {
        email: inviteEmail.trim(), role: inviteRole,
      });
      toast.success(`Invitation sent to ${inviteEmail}`);
      setInviteEmail("");
      await load();
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setSubmitting(false); }
  };

  const onRemove = async (memberAccountId) => {
    try {
      await api.delete(`/contexts/${contextId}/members/${memberAccountId}`);
      toast.success("Member removed.");
      await load();
    } catch (e) { toast.error(apiErrorMessage(e)); }
  };

  const onRevoke = async (inv) => {
    try {
      await api.delete(`/contexts/${contextId}/invitations/${inv.id}`);
      toast.success("Invitation revoked.");
      await load();
    } catch (e) { toast.error(apiErrorMessage(e)); }
  };

  if (!activeContext) {
    return (
      <div className="bg-white border border-[var(--rule)] rounded-lg p-12 text-center">
        <p className="akki-lead mb-2">Pick a company first.</p>
        <p className="text-[13px] text-[var(--muted)]">Switch to the context whose team you want to manage.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Context breadcrumb */}
      <div className="flex items-center gap-2 text-[12px] text-[var(--muted)]" data-testid="team-active-context">
        <Layers className="w-3.5 h-3.5 text-[var(--accent)]" />
        <span>Managing the team for</span>
        <span className="text-[var(--ink)] font-medium">{activeContext.name}</span>
      </div>

      {/* Invite row */}
      {imAdmin && (
        <motion.div
          initial={{ opacity: 0 }} animate={{ opacity: 1 }}
          className="bg-white border border-[var(--rule)] rounded-lg p-5"
        >
          <p className="akki-overline mb-3">Invite a colleague</p>
          <div className="flex items-stretch gap-3">
            <Input
              value={inviteEmail}
              onChange={(e) => setInviteEmail(e.target.value)}
              placeholder="colleague@company.com"
              className="flex-1 rounded-md h-10 text-sm border-[var(--rule)] bg-[var(--cream)]"
              disabled={submitting}
              data-testid="manage-invite-email"
            />
            <Select value={inviteRole} onValueChange={setInviteRole}>
              <SelectTrigger className="w-[180px] rounded-md h-10 border-[var(--rule)] bg-[var(--cream)]" data-testid="manage-invite-role">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="executive">Executive</SelectItem>
                <SelectItem value="ned">Non-Executive Director</SelectItem>
                <SelectItem value="reportee">Reportee</SelectItem>
              </SelectContent>
            </Select>
            <Button
              onClick={onInvite}
              disabled={submitting}
              className="bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white rounded-md h-10 px-5 font-medium"
              data-testid="manage-invite-submit"
            >
              <UserPlus className="w-4 h-4 mr-2" /> Invite
            </Button>
          </div>
        </motion.div>
      )}

      {/* Pending invitations */}
      {invites.length > 0 && (
        <div className="bg-white border border-[var(--rule)] rounded-lg overflow-hidden">
          <div className="px-5 py-3 border-b border-[var(--rule)]">
            <p className="akki-overline">Pending invitations · {invites.length}</p>
          </div>
          <ul className="divide-y divide-[var(--rule)]">
            {invites.map((inv) => (
              <li key={inv.id} className="px-5 py-3 flex items-center gap-3" data-testid={`manage-invite-${inv.id}`}>
                <div className="w-8 h-8 rounded-full bg-[var(--cream-deep)] flex items-center justify-center">
                  <UserPlus className="w-3.5 h-3.5 text-[var(--muted)]" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-[13.5px] text-[var(--ink)] truncate">{inv.email}</p>
                  <p className="text-[11px] text-[var(--muted)] capitalize">{inv.role} · invited</p>
                </div>
                {imAdmin && (
                  <button
                    onClick={() => onRevoke(inv)}
                    className="text-[12px] text-[var(--muted)] hover:text-red-600 transition-colors"
                    data-testid={`manage-invite-revoke-${inv.id}`}
                  >
                    Revoke
                  </button>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Members */}
      <div className="bg-white border border-[var(--rule)] rounded-lg overflow-hidden">
        <div className="px-5 py-3 border-b border-[var(--rule)] flex items-center justify-between">
          <p className="akki-overline">Active members · {members.length}</p>
          <a
            href="/app/settings"
            className="text-[12px] text-[var(--muted)] hover:text-[var(--accent)] inline-flex items-center gap-1"
            data-testid="manage-deep-settings"
          >
            Full settings <ExternalLink className="w-3 h-3" />
          </a>
        </div>
        {loading ? (
          <p className="px-5 py-8 text-center text-[12px] uppercase tracking-widest text-[var(--muted)]">Loading…</p>
        ) : members.length === 0 ? (
          <p className="px-5 py-8 text-center text-sm text-[var(--muted)]">No members yet.</p>
        ) : (
          <ul className="divide-y divide-[var(--rule)]" data-testid="manage-members">
            {members.map((m, i) => {
              const initial = (m.name || m.email || "?").charAt(0).toUpperCase();
              const isMe = m.account_id === account?.id;
              const isOwner = m.account_id === activeContext.owner_account_id;
              return (
                <motion.li
                  key={m.account_id}
                  initial={{ opacity: 0, x: -6 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.03, duration: 0.25 }}
                  className="px-5 py-3 flex items-center gap-3"
                  data-testid={`manage-member-${m.account_id}`}
                >
                  <div className="w-8 h-8 rounded-full bg-[var(--navy)] text-white flex items-center justify-center text-xs font-bold">
                    {initial}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <p className="text-[13.5px] text-[var(--ink)] truncate">{m.name || m.email}</p>
                      {isMe && <span className="text-[9px] uppercase tracking-wider text-[var(--accent)]">you</span>}
                      {isOwner && <span className="text-[9px] uppercase tracking-wider text-[var(--muted)]">owner</span>}
                    </div>
                    <p className="text-[11px] text-[var(--muted)] truncate">
                      {m.email} · <span className="capitalize">{m.role}</span>
                      {m.sub_role && m.sub_role !== "member" && <> · <span className="capitalize">{m.sub_role}</span></>}
                    </p>
                  </div>
                  {imAdmin && !isMe && !isOwner && (
                    <AlertDialog>
                      <AlertDialogTrigger asChild>
                        <button
                          className="p-2 rounded-sm text-[var(--muted)] hover:text-red-600 hover:bg-red-50 transition-colors"
                          data-testid={`manage-member-remove-${m.account_id}`}
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </AlertDialogTrigger>
                      <AlertDialogContent className="rounded-sm">
                        <AlertDialogHeader>
                          <AlertDialogTitle>Remove {m.name || m.email}?</AlertDialogTitle>
                          <AlertDialogDescription>
                            They will lose access to {activeContext.name}. This does not delete their account.
                          </AlertDialogDescription>
                        </AlertDialogHeader>
                        <AlertDialogFooter>
                          <AlertDialogCancel>Cancel</AlertDialogCancel>
                          <AlertDialogAction onClick={() => onRemove(m.account_id)} className="bg-red-600 hover:bg-red-700">
                            Remove
                          </AlertDialogAction>
                        </AlertDialogFooter>
                      </AlertDialogContent>
                    </AlertDialog>
                  )}
                </motion.li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Companies panel
// ---------------------------------------------------------------------------
function CompaniesPanel() {
  const { contexts, activeContext, switchContext, refreshContexts } = useAuth();
  const navigate = useNavigate();
  const [archivingId, setArchivingId] = useState(null);

  const onArchive = async (c) => {
    setArchivingId(c.id);
    try {
      await api.delete(`/contexts/${c.id}`);
      toast.success(`${c.name} archived.`);
      if (refreshContexts) await refreshContexts();
    } catch (e) {
      toast.error(apiErrorMessage(e));
    } finally {
      setArchivingId(null);
    }
  };

  const onOpen = (c) => {
    if (c.id !== activeContext?.id) switchContext(c.id);
    navigate("/app");
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <p className="text-[13px] text-[var(--muted)]">
          <span className="akki-serif text-[var(--ink)] text-[15px] mr-1">{contexts.length}</span>
          {contexts.length === 1 ? "company" : "companies"} on your roster
        </p>
        <Button
          onClick={() => navigate("/app/contexts/new")}
          className="bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white rounded-md h-10 px-5 font-medium"
          data-testid="manage-add-company"
        >
          <Plus className="w-4 h-4 mr-2" /> Add company
        </Button>
      </div>

      {contexts.length === 0 ? (
        <div className="bg-white border border-dashed border-[var(--rule)] rounded-lg p-12 text-center">
          <Building2 className="w-10 h-10 text-[var(--muted)]/40 mx-auto mb-4" strokeWidth={1.3} />
          <p className="akki-lead mb-2">No companies yet.</p>
          <p className="text-[13px] text-[var(--muted)] mb-5 max-w-md mx-auto">
            Spin up your first board or executive context to start reading with receipts.
          </p>
          <Button
            onClick={() => navigate("/app/contexts/new")}
            className="bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white rounded-md h-10 px-5"
          >
            Add a company <ArrowRight className="w-4 h-4 ml-2" />
          </Button>
        </div>
      ) : (
        <motion.ul
          className="grid grid-cols-1 md:grid-cols-2 gap-4"
          initial="hidden" animate="show"
          variants={{
            hidden: {},
            show: { transition: { staggerChildren: 0.04 } },
          }}
          data-testid="manage-company-grid"
        >
          {contexts.map((c) => {
            const Icon = c.type?.startsWith("ned") ? Landmark : Briefcase;
            const active = c.id === activeContext?.id;
            const canArchive = c.my_sub_role === "admin";
            return (
              <motion.li
                key={c.id}
                variants={{
                  hidden: { opacity: 0, y: 8 },
                  show: { opacity: 1, y: 0, transition: { duration: 0.3 } },
                }}
                whileHover={{ y: -2 }}
                className={`relative bg-white border rounded-lg p-5 group transition-shadow hover:shadow-sm ${
                  active ? "border-[var(--accent)]" : "border-[var(--rule)]"
                }`}
                data-testid={`manage-company-${c.id}`}
              >
                <span className={`absolute left-0 top-0 bottom-0 w-[3px] rounded-l-lg transition-opacity ${
                  active ? "bg-[var(--accent)] opacity-100" : "bg-[var(--accent)] opacity-0 group-hover:opacity-60"
                }`} />
                <div className="flex items-start gap-3 mb-3">
                  <div className="w-9 h-9 bg-[var(--cream-deep)] rounded-md flex items-center justify-center shrink-0">
                    <Icon className="w-4 h-4 text-[var(--accent)]" strokeWidth={1.8} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-[10px] uppercase tracking-[0.18em] text-[var(--muted)] mb-0.5">
                      {TYPE_LABEL[c.type] || c.type}
                    </p>
                    <h3 className="akki-serif text-[18px] leading-snug text-[var(--ink)] truncate">{c.name}</h3>
                    <p className="text-[11.5px] text-[var(--muted)] truncate mt-0.5">
                      {c.industry ? `${c.industry}` : "—"}
                      {c.jurisdiction ? ` · ${c.jurisdiction}` : ""}
                    </p>
                  </div>
                  {active && <CheckCircle2 className="w-4 h-4 text-[var(--accent)] shrink-0 mt-1" />}
                </div>

                <div className="flex items-center gap-2 pt-3 border-t border-[var(--rule)]">
                  <button
                    onClick={() => onOpen(c)}
                    className="akki-gesture text-[13px]"
                    data-testid={`manage-company-open-${c.id}`}
                  >
                    {active ? "Open" : "Switch & open"} <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                  <div className="ml-auto" />
                  {canArchive && (
                    <AlertDialog>
                      <AlertDialogTrigger asChild>
                        <button
                          className="text-[12px] text-[var(--muted)] hover:text-red-600 inline-flex items-center gap-1 transition-colors"
                          data-testid={`manage-company-archive-${c.id}`}
                          disabled={archivingId === c.id}
                        >
                          <ArchiveX className="w-3.5 h-3.5" /> Archive
                        </button>
                      </AlertDialogTrigger>
                      <AlertDialogContent className="rounded-sm">
                        <AlertDialogHeader>
                          <AlertDialogTitle>Archive {c.name}?</AlertDialogTitle>
                          <AlertDialogDescription>
                            The company is hidden from your list. Signals, briefings and documents are preserved and can be restored by an admin.
                          </AlertDialogDescription>
                        </AlertDialogHeader>
                        <AlertDialogFooter>
                          <AlertDialogCancel>Cancel</AlertDialogCancel>
                          <AlertDialogAction onClick={() => onArchive(c)} className="bg-red-600 hover:bg-red-700">
                            Archive
                          </AlertDialogAction>
                        </AlertDialogFooter>
                      </AlertDialogContent>
                    </AlertDialog>
                  )}
                </div>
              </motion.li>
            );
          })}
        </motion.ul>
      )}
    </div>
  );
}
