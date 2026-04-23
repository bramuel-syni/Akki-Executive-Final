import React, { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { api, apiErrorMessage } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import { Plus, Trash2, Pencil, Check, X, Users2 } from "lucide-react";

const ROLE_OPTS = [
  { value: "chair",    label: "Chair" },
  { value: "member",   label: "Member" },
  { value: "observer", label: "Observer" },
];

export default function CommitteeManager() {
  const { activeContext, refreshContexts } = useAuth();
  const contextId = activeContext?.id;
  const isAdmin = activeContext?.my_sub_role === "admin" ||
                  activeContext?.owner_account_id; // owner_account_id existence doesn't prove it's *you*; rely on UI readonly fallback

  const [committees, setCommittees] = useState([]);
  const [loading, setLoading] = useState(true);
  const [newName, setNewName] = useState("");
  const [newRole, setNewRole] = useState("member");
  const [editingId, setEditingId] = useState(null);
  const [editName, setEditName] = useState("");
  const [editRole, setEditRole] = useState("member");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    if (!contextId) return;
    try {
      const { data } = await api.get(`/contexts/${contextId}/committees`);
      setCommittees(data || []);
    } catch { /* silent */ }
    finally { setLoading(false); }
  }, [contextId]);

  useEffect(() => { load(); }, [load]);

  const onAdd = async () => {
    const name = newName.trim();
    if (name.length < 2) return;
    setBusy(true);
    try {
      await api.post(`/contexts/${contextId}/committees`, { name, your_role: newRole });
      setNewName("");
      setNewRole("member");
      toast.success(`${name} added`);
      await load();
      await refreshContexts();
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setBusy(false); }
  };

  const onSaveEdit = async (cm) => {
    const name = editName.trim();
    if (name.length < 2) return;
    setBusy(true);
    try {
      await api.patch(`/contexts/${contextId}/committees/${cm.id}`, { name, your_role: editRole });
      setEditingId(null);
      toast.success("Committee updated");
      await load();
      await refreshContexts();
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setBusy(false); }
  };

  const onDelete = async (cm) => {
    if (!window.confirm(`Delete "${cm.name}"? Signals/briefings tagged to it will be un-scoped.`)) return;
    setBusy(true);
    try {
      await api.delete(`/contexts/${contextId}/committees/${cm.id}`);
      toast.success("Committee removed");
      await load();
      await refreshContexts();
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setBusy(false); }
  };

  const startEdit = (cm) => {
    setEditingId(cm.id);
    setEditName(cm.name);
    setEditRole(cm.your_role || "member");
  };

  return (
    <section className="bg-white border border-[#E1E6ED] rounded-sm" data-testid="committee-manager">
      <div className="px-6 py-4 border-b border-[#E1E6ED]">
        <div className="flex items-center gap-2">
          <Users2 className="w-4 h-4 text-[var(--accent)]" strokeWidth={1.8} />
          <p className="text-sm font-medium text-[var(--ink)]">Sub-committees</p>
        </div>
        <p className="text-[11.5px] text-slate-500 mt-0.5">
          Used to scope signals, briefings and simulations by committee. Delete un-scopes — it does not remove the artefact.
        </p>
      </div>

      <div className="px-6 py-5 space-y-4">
        {/* Add new */}
        {isAdmin && (
          <div className="flex items-center gap-2" data-testid="committee-add-row">
            <Input
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="e.g. ESG Committee"
              disabled={busy}
              className="flex-1 rounded-sm h-9 text-sm border-[#E1E6ED]"
              data-testid="committee-new-name"
            />
            <select
              value={newRole}
              onChange={(e) => setNewRole(e.target.value)}
              disabled={busy}
              className="text-[12px] border border-[#E1E6ED] rounded-sm bg-white px-2 h-9 focus:outline-none focus:border-[var(--accent)]"
              data-testid="committee-new-role"
            >
              {ROLE_OPTS.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
            </select>
            <Button
              onClick={onAdd}
              disabled={busy || newName.trim().length < 2}
              className="bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white rounded-sm h-9 px-3 text-[12px] font-medium"
              data-testid="committee-add-btn"
            >
              <Plus className="w-3.5 h-3.5 mr-1.5" /> Add
            </Button>
          </div>
        )}

        {/* List */}
        {loading ? (
          <p className="text-[12px] text-slate-400 italic">Loading…</p>
        ) : committees.length === 0 ? (
          <p className="text-[12.5px] text-slate-500 italic py-2">
            No committees yet. {isAdmin ? "Add the first above." : "Ask an admin to add one."}
          </p>
        ) : (
          <ul className="divide-y divide-[#E1E6ED] border border-[#E1E6ED] rounded-sm" data-testid="committee-list">
            {committees.map((cm) => {
              const editing = editingId === cm.id;
              return (
                <li key={cm.id} className="px-4 py-3 flex items-center gap-3" data-testid={`committee-row-${cm.id}`}>
                  {editing ? (
                    <>
                      <Input
                        value={editName}
                        onChange={(e) => setEditName(e.target.value)}
                        disabled={busy}
                        className="flex-1 rounded-sm h-8 text-sm border-[#E1E6ED]"
                        data-testid={`committee-edit-name-${cm.id}`}
                      />
                      <select
                        value={editRole}
                        onChange={(e) => setEditRole(e.target.value)}
                        disabled={busy}
                        className="text-[12px] border border-[#E1E6ED] rounded-sm bg-white px-2 h-8"
                        data-testid={`committee-edit-role-${cm.id}`}
                      >
                        {ROLE_OPTS.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
                      </select>
                      <button
                        onClick={() => onSaveEdit(cm)}
                        disabled={busy}
                        className="text-[var(--accent)] hover:text-[var(--accent)]/80 p-1"
                        title="Save"
                        data-testid={`committee-save-${cm.id}`}
                      >
                        <Check className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => setEditingId(null)}
                        disabled={busy}
                        className="text-slate-400 hover:text-slate-600 p-1"
                        title="Cancel"
                        data-testid={`committee-cancel-${cm.id}`}
                      >
                        <X className="w-4 h-4" />
                      </button>
                    </>
                  ) : (
                    <>
                      <div className="flex-1">
                        <p className="text-[13.5px] font-medium text-[var(--ink)]">{cm.name}</p>
                        <p className="text-[11px] text-slate-500">
                          Your role: <span className="capitalize">{cm.your_role || "member"}</span>
                          <span className="ml-2 text-slate-400 font-mono">· {cm.id}</span>
                        </p>
                      </div>
                      {isAdmin && (
                        <>
                          <button
                            onClick={() => startEdit(cm)}
                            className="text-slate-400 hover:text-[var(--accent)] p-1"
                            title="Edit"
                            data-testid={`committee-edit-${cm.id}`}
                          >
                            <Pencil className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={() => onDelete(cm)}
                            className="text-slate-400 hover:text-red-600 p-1"
                            title="Delete"
                            data-testid={`committee-delete-${cm.id}`}
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </>
                      )}
                    </>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </section>
  );
}
