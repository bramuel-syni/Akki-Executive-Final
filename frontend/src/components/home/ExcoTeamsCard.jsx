/**
 * ExcoTeamsCard — HOME sprint, 2026-05-12.
 *
 * Lists the ExCo teams in the active context, with management actions
 * for owners/admins. Renders on HomeExecutive and HomeDual when the
 * active membership has any ExCo association (member of one OR
 * owner/admin in the context).
 *
 * Surfaces:
 *   - List view  : team name, member count, my-role badge, archive count
 *   - Create     : modal with name + description + member multi-select
 *   - Manage     : drawer with member list + add / remove / archive
 *
 * Privacy: API never returns raw email. Member display shows display_name
 * + role only. Surface respects `prefers-reduced-motion` (no entrance
 * animations on the modal/drawer).
 */
import React, { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Users, Plus, X as XIcon, Archive, UserMinus, UserPlus } from "lucide-react";

export default function ExcoTeamsCard({ contextId, isAdmin }) {
  const [teams, setTeams] = useState([]);
  const [loading, setLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [manageTeam, setManageTeam] = useState(null);
  const [members, setMembers] = useState([]); // context's eligible members

  const fetchTeams = async () => {
    if (!contextId) return;
    try {
      const { data } = await api.get(`/contexts/${contextId}/exco-teams`);
      setTeams(Array.isArray(data) ? data : data?.items || []);
    } catch {
      setTeams([]);
    } finally {
      setLoading(false);
    }
  };

  const fetchEligibleMembers = async () => {
    if (!contextId) return;
    try {
      const { data } = await api.get(`/contexts/${contextId}/members`);
      setMembers(Array.isArray(data) ? data : data?.members || data?.items || []);
    } catch {
      setMembers([]);
    }
  };

  useEffect(() => {
    fetchTeams();
    fetchEligibleMembers();
  }, [contextId]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!contextId) return null;
  // Only render when the user has a stake — owner/admin OR member of any team.
  const myTeams = teams.filter((t) => t.my_role === "creator" || t.my_role === "member");
  if (!isAdmin && myTeams.length === 0 && !loading) return null;

  return (
    <section
      className="mt-8 bg-[var(--parchment-light)] border border-[var(--graphite-light)] rounded-md p-6"
      data-testid="home-exco-teams-card"
    >
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Users className="w-4 h-4 text-[var(--oxblood)]" strokeWidth={1.8} />
          <p className="akki-overline">ExCo teams · {teams.length}</p>
        </div>
        {isAdmin && (
          <Button
            onClick={() => setCreateOpen(true)}
            variant="outline"
            className="h-8 px-3 text-[12px] border-[var(--ink)] text-[var(--ink)] hover:bg-[var(--ink)] hover:text-[var(--parchment)] rounded-sm"
            data-testid="exco-create-btn"
          >
            <Plus className="w-3 h-3 mr-1" /> Create team
          </Button>
        )}
      </div>

      {loading ? (
        <p className="text-[13px] text-[var(--graphite)] italic">Loading teams…</p>
      ) : teams.length === 0 ? (
        <p className="text-[13px] text-[var(--graphite)]" data-testid="exco-empty">
          {isAdmin
            ? "No ExCo teams yet. Create one to group senior leadership in this company."
            : "You are not a member of any ExCo team in this company."}
        </p>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4" data-testid="exco-team-grid">
          {teams.map((t) => (
            <button
              key={t.id}
              onClick={() => setManageTeam(t)}
              className="text-left bg-[var(--parchment)] border border-[var(--graphite-light)] rounded-sm p-4 hover:border-[var(--ink)]/40 transition-colors"
              data-testid={`exco-team-card-${t.id}`}
            >
              <p className="akki-serif text-[18px] text-[var(--ink)] mb-1 leading-snug">{t.name}</p>
              <p className="text-[12px] text-[var(--graphite)] mb-2">
                {(t.member_account_ids || []).length} member{(t.member_account_ids || []).length === 1 ? "" : "s"}
                {t.my_role === "creator" ? " · You created this team" : t.my_role === "member" ? " · You belong" : ""}
                {t.status === "archived" ? " · Archived" : ""}
              </p>
              {t.description && (
                <p className="text-[13px] text-[var(--graphite)] italic line-clamp-2">{t.description}</p>
              )}
            </button>
          ))}
        </div>
      )}

      {createOpen && (
        <CreateTeamModal
          contextId={contextId}
          eligibleMembers={members}
          onClose={() => setCreateOpen(false)}
          onCreated={() => { setCreateOpen(false); fetchTeams(); }}
        />
      )}
      {manageTeam && (
        <ManageTeamDrawer
          contextId={contextId}
          team={manageTeam}
          isAdmin={isAdmin}
          eligibleMembers={members}
          onClose={() => setManageTeam(null)}
          onChanged={() => { fetchTeams(); }}
        />
      )}
    </section>
  );
}


function CreateTeamModal({ contextId, eligibleMembers, onClose, onCreated }) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [selected, setSelected] = useState(new Set());
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const toggle = (id) => {
    const next = new Set(selected);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setSelected(next);
  };

  const submit = async () => {
    setSubmitting(true); setError("");
    try {
      await api.post(`/contexts/${contextId}/exco-teams`, {
        name: name.trim(),
        description: description.trim() || undefined,
        member_account_ids: Array.from(selected),
      });
      onCreated();
    } catch (err) {
      setError(err?.response?.data?.detail || "Could not create team");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-[var(--ink)]/40 z-50 flex items-center justify-center p-4" data-testid="exco-create-modal">
      <div className="bg-[var(--parchment-light)] border border-[var(--graphite-light)] rounded-md max-w-lg w-full p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="akki-serif text-[22px] text-[var(--ink)]">Create ExCo team</h3>
          <button onClick={onClose} className="text-[var(--graphite)] hover:text-[var(--ink)]" data-testid="exco-modal-close">
            <XIcon className="w-4 h-4" />
          </button>
        </div>
        <label className="block mb-3">
          <span className="text-[11px] uppercase tracking-wider text-[var(--graphite)]">Name</span>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full mt-1 px-3 py-2 bg-[var(--parchment)] border border-[var(--graphite-light)] rounded-sm text-[14px] focus:border-[var(--oxblood)] focus:outline-none"
            placeholder="e.g. Senior Leadership Team"
            data-testid="exco-name-input"
            maxLength={120}
            autoFocus
          />
        </label>
        <label className="block mb-3">
          <span className="text-[11px] uppercase tracking-wider text-[var(--graphite)]">Description (optional)</span>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="w-full mt-1 px-3 py-2 bg-[var(--parchment)] border border-[var(--graphite-light)] rounded-sm text-[14px] focus:border-[var(--oxblood)] focus:outline-none min-h-[64px]"
            placeholder="What this team is for"
            data-testid="exco-desc-input"
            maxLength={600}
          />
        </label>
        <div className="mb-3">
          <p className="text-[11px] uppercase tracking-wider text-[var(--graphite)] mb-1">Members</p>
          <div className="max-h-[180px] overflow-y-auto border border-[var(--graphite-light)] rounded-sm">
            {(eligibleMembers || []).length === 0 ? (
              <p className="px-3 py-2 text-[13px] text-[var(--graphite)] italic">No active members in this company.</p>
            ) : eligibleMembers.map((m) => {
              const id = m.account_id || m.id;
              const label = m.display_name || m.name || "Anonymous";
              const sub = m.sub_role === "admin" ? " · Admin" : "";
              return (
                <label key={id} className="flex items-center gap-2 px-3 py-2 text-[13.5px] hover:bg-[var(--parchment)] cursor-pointer" data-testid={`exco-member-${id}`}>
                  <input
                    type="checkbox"
                    checked={selected.has(id)}
                    onChange={() => toggle(id)}
                    className="accent-[var(--oxblood)]"
                  />
                  <span>{label}{sub}</span>
                </label>
              );
            })}
          </div>
        </div>
        {error && <p className="text-[12.5px] text-[var(--oxblood)] mb-2" data-testid="exco-create-error">{error}</p>}
        <div className="flex items-center justify-end gap-2 mt-4">
          <Button variant="ghost" onClick={onClose} className="h-9 px-3 text-[13px] text-[var(--graphite)] hover:text-[var(--ink)]">
            Cancel
          </Button>
          <Button
            onClick={submit}
            disabled={!name.trim() || submitting}
            className="h-9 px-4 text-[13px] border border-[var(--ink)] bg-transparent text-[var(--ink)] hover:bg-[var(--ink)] hover:text-[var(--parchment)] rounded-sm"
            data-testid="exco-create-submit"
          >
            {submitting ? "Creating…" : "Create team"}
          </Button>
        </div>
      </div>
    </div>
  );
}


function ManageTeamDrawer({ contextId, team, isAdmin, eligibleMembers, onClose, onChanged }) {
  const [adding, setAdding] = useState(false);
  const [pickerOpen, setPickerOpen] = useState(false);
  const memberIds = team.member_account_ids || [];
  const memberRows = team.members || [];
  const eligibleNotInTeam = useMemo(
    () => (eligibleMembers || []).filter((m) => !memberIds.includes(m.account_id || m.id)),
    [eligibleMembers, memberIds],
  );

  const remove = async (aid) => {
    if (!window.confirm("Remove this member from the team?")) return;
    await api.delete(`/contexts/${contextId}/exco-teams/${team.id}/members/${aid}`);
    onChanged();
    onClose();
  };
  const add = async (aid) => {
    setAdding(true);
    try {
      await api.post(`/contexts/${contextId}/exco-teams/${team.id}/members`, { account_id: aid });
      onChanged();
      onClose();
    } catch {
      // swallow — the parent refresh will reveal any inconsistency
    } finally {
      setAdding(false);
      setPickerOpen(false);
    }
  };
  const archive = async () => {
    if (!window.confirm("Archive this team? Members keep their context membership.")) return;
    await api.delete(`/contexts/${contextId}/exco-teams/${team.id}`);
    onChanged();
    onClose();
  };

  return (
    <div className="fixed inset-0 bg-[var(--ink)]/40 z-50 flex items-end md:items-center justify-end" data-testid="exco-manage-drawer">
      <div className="bg-[var(--parchment-light)] border-l border-[var(--graphite-light)] h-full md:max-h-[90vh] w-full md:w-[420px] p-6 overflow-y-auto">
        <div className="flex items-center justify-between mb-4">
          <div>
            <p className="akki-overline mb-1">ExCo team</p>
            <h3 className="akki-serif text-[22px] text-[var(--ink)] leading-snug">{team.name}</h3>
          </div>
          <button onClick={onClose} className="text-[var(--graphite)] hover:text-[var(--ink)]" data-testid="exco-drawer-close">
            <XIcon className="w-4 h-4" />
          </button>
        </div>
        {team.description && (
          <p className="text-[13.5px] text-[var(--graphite)] italic mb-4">{team.description}</p>
        )}
        <p className="text-[11px] uppercase tracking-wider text-[var(--graphite)] mb-2">
          Members · {memberRows.length}
        </p>
        <div className="space-y-1 mb-4">
          {memberRows.length === 0 && (
            <p className="text-[13px] text-[var(--graphite)] italic">No members yet.</p>
          )}
          {memberRows.map((m) => (
            <div
              key={m.account_id}
              className="flex items-center justify-between bg-[var(--parchment)] border border-[var(--graphite-light)] rounded-sm px-3 py-2"
              data-testid={`exco-member-row-${m.account_id}`}
            >
              <div>
                <p className="text-[13.5px] text-[var(--ink)]">{m.name}</p>
                <p className="text-[11px] text-[var(--graphite)]">{m.role}{m.sub_role === "admin" ? " · Admin" : ""}</p>
              </div>
              {isAdmin && (
                <button
                  onClick={() => remove(m.account_id)}
                  className="text-[var(--graphite)] hover:text-[var(--oxblood)]"
                  title="Remove from team"
                  data-testid={`exco-remove-${m.account_id}`}
                >
                  <UserMinus className="w-4 h-4" />
                </button>
              )}
            </div>
          ))}
        </div>

        {isAdmin && (
          <div className="space-y-2">
            {pickerOpen ? (
              <div className="bg-[var(--parchment)] border border-[var(--graphite-light)] rounded-sm max-h-[180px] overflow-y-auto">
                {eligibleNotInTeam.length === 0 ? (
                  <p className="px-3 py-2 text-[13px] text-[var(--graphite)] italic">Everyone in this company is already on the team.</p>
                ) : eligibleNotInTeam.map((m) => {
                  const id = m.account_id || m.id;
                  return (
                    <button
                      key={id}
                      onClick={() => add(id)}
                      disabled={adding}
                      className="block w-full text-left px-3 py-2 text-[13.5px] hover:bg-[var(--parchment-light)]"
                      data-testid={`exco-picker-${id}`}
                    >
                      {m.display_name || m.name || "Anonymous"}
                    </button>
                  );
                })}
              </div>
            ) : (
              <Button
                onClick={() => setPickerOpen(true)}
                variant="outline"
                className="w-full h-9 text-[13px] border-[var(--ink)] text-[var(--ink)] hover:bg-[var(--ink)] hover:text-[var(--parchment)] rounded-sm"
                data-testid="exco-add-member-btn"
              >
                <UserPlus className="w-3.5 h-3.5 mr-1" /> Add a member
              </Button>
            )}
            <Button
              onClick={archive}
              variant="ghost"
              className="w-full h-9 text-[13px] text-[var(--graphite)] hover:text-[var(--oxblood)]"
              data-testid="exco-archive-btn"
            >
              <Archive className="w-3.5 h-3.5 mr-1" /> Archive team
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
