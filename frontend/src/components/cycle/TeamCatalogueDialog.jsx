/**
 * TeamCatalogueDialog — manage the team_catalogue (context-scoped
 * permanent identity store).
 *
 * Allows edit name/email and soft-delete. Does NOT touch historical
 * cycle_team rows.
 */
import React, { useEffect, useState } from "react";
import { apiErrorMessage } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  AlertDialog, AlertDialogContent, AlertDialogHeader,
  AlertDialogTitle, AlertDialogDescription, AlertDialogFooter, AlertDialogCancel,
} from "@/components/ui/alert-dialog";
import { Trash2, Check, X, Pencil, Loader2 } from "lucide-react";
import { toast } from "sonner";
import {
  listCatalogue, patchCatalogueMember, softDeleteCatalogueMember,
} from "@/lib/cycleApi";


export default function TeamCatalogueDialog({ open, onOpenChange, contextId }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [editName, setEditName] = useState("");
  const [editEmail, setEditEmail] = useState("");

  const load = async () => {
    if (!contextId) return;
    setLoading(true);
    try { const d = await listCatalogue(contextId); setRows(d.members || []); }
    catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setLoading(false); }
  };

  useEffect(() => { if (open) load(); /* eslint-disable-next-line */ }, [open, contextId]);

  const startEdit = (m) => {
    setEditingId(m.id); setEditName(m.name); setEditEmail(m.email);
  };
  const cancelEdit = () => { setEditingId(null); setEditName(""); setEditEmail(""); };
  const saveEdit = async () => {
    try {
      await patchCatalogueMember(contextId, editingId, { name: editName.trim(), email: editEmail.trim() });
      cancelEdit(); await load();
      toast.success("Updated.");
    } catch (e) { toast.error(apiErrorMessage(e)); }
  };
  const remove = async (id) => {
    try {
      await softDeleteCatalogueMember(contextId, id);
      await load();
      toast.success("Removed from catalogue. Historical cycle rows preserved.");
    } catch (e) { toast.error(apiErrorMessage(e)); }
  };

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent className="max-w-2xl" data-testid="team-catalogue-dialog">
        <AlertDialogHeader>
          <AlertDialogTitle className="akki-serif">Team Catalogue</AlertDialogTitle>
          <AlertDialogDescription className="akki-meta">
            Permanent member identity for this workspace. Removing a member here
            does NOT affect any cycle they have already contributed to.
          </AlertDialogDescription>
        </AlertDialogHeader>

        {loading ? (
          <div className="flex items-center justify-center py-8 text-[var(--muted)]">
            <Loader2 className="w-4 h-4 mr-2 animate-spin" /> Loading…
          </div>
        ) : rows.length === 0 ? (
          <p className="text-[12.5px] text-[var(--muted)] py-6 text-center" data-testid="team-catalogue-empty">
            No members yet. Use Add Team Member on the Team tab to populate this catalogue.
          </p>
        ) : (
          <div className="border border-[var(--rule)] rounded-sm divide-y divide-[var(--rule)] max-h-[400px] overflow-y-auto bg-white">
            {rows.map((m) => (
              <div key={m.id} className="px-3 py-2 flex items-center gap-3" data-testid={`catalogue-row-${m.id}`}>
                {editingId === m.id ? (
                  <>
                    <Input value={editName} onChange={(e) => setEditName(e.target.value)} className="rounded-sm text-[13px] flex-1" />
                    <Input value={editEmail} onChange={(e) => setEditEmail(e.target.value)} className="rounded-sm text-[13px] font-mono flex-1" />
                    <Button size="sm" variant="ghost" onClick={saveEdit} data-testid={`catalogue-save-${m.id}`}>
                      <Check className="w-3.5 h-3.5 text-emerald-700" />
                    </Button>
                    <Button size="sm" variant="ghost" onClick={cancelEdit}>
                      <X className="w-3.5 h-3.5 text-[var(--muted)]" />
                    </Button>
                  </>
                ) : (
                  <>
                    <div className="flex-1 min-w-0">
                      <p className="text-[13.5px] text-[var(--ink)] truncate">{m.name}</p>
                      <p className="text-[11.5px] text-[var(--muted)] font-mono truncate">{m.email}</p>
                    </div>
                    <Button size="sm" variant="ghost" onClick={() => startEdit(m)} data-testid={`catalogue-edit-${m.id}`}>
                      <Pencil className="w-3.5 h-3.5 text-[var(--muted)]" />
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => remove(m.id)} data-testid={`catalogue-remove-${m.id}`}>
                      <Trash2 className="w-3.5 h-3.5 text-[color:var(--oxblood)]" />
                    </Button>
                  </>
                )}
              </div>
            ))}
          </div>
        )}

        <AlertDialogFooter>
          <AlertDialogCancel data-testid="team-catalogue-close">Close</AlertDialogCancel>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
