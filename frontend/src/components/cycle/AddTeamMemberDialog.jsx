/**
 * AddTeamMemberDialog — two-tab "Add Team Member" UI.
 *
 *   • Select from Catalogue — searchable list of context-scoped
 *     team_catalogue rows; click to pre-fill name + email; role,
 *     contribution_description and agenda_assignments are blank for
 *     the current cycle.
 *   • Add New Member — the existing free-form add path.
 *
 * Both paths upsert into team_catalogue first, then call the per-cycle
 * /cycle/team endpoint to create the cycle-scoped row.
 *
 * Optional duplicate detection: if `agendaItemId` is provided, on Add
 * we first call check-team-duplicate. If 409-shaped (warning) we surface
 * an inline acknowledgement; user must click "Add anyway" to confirm.
 */
import React, { useEffect, useMemo, useState } from "react";
import { api, apiErrorMessage } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import {
  AlertDialog, AlertDialogContent, AlertDialogHeader,
  AlertDialogTitle, AlertDialogFooter, AlertDialogCancel,
} from "@/components/ui/alert-dialog";
import { Search, Loader2, UserPlus, BookUser } from "lucide-react";
import { toast } from "sonner";
import {
  listCatalogue, addCatalogueMember, checkTeamDuplicate,
} from "@/lib/cycleApi";


function Tabs({ value, onChange }) {
  const tabs = [
    { id: "catalogue", icon: BookUser,  label: "Select from Catalogue" },
    { id: "new",       icon: UserPlus,  label: "Add New Member" },
  ];
  return (
    <div className="flex items-center border-b border-[var(--rule)] mb-4">
      {tabs.map((t) => (
        <button
          key={t.id}
          type="button"
          onClick={() => onChange(t.id)}
          className={[
            "py-2 px-3 text-[12px] uppercase tracking-[0.12em] font-mono transition-colors flex items-center gap-1.5",
            value === t.id
              ? "text-[var(--ink)] border-b-2 border-[color:var(--oxblood)] -mb-px"
              : "text-[var(--muted)] hover:text-[var(--ink)] border-b-2 border-transparent -mb-px",
          ].join(" ")}
          data-testid={`add-member-tab-${t.id}`}
        >
          <t.icon className="w-3.5 h-3.5" /> {t.label}
        </button>
      ))}
    </div>
  );
}


export default function AddTeamMemberDialog({
  open, onOpenChange, contextId, cycleId, agendaItemId, agendaItems = [],
  onAdded,
}) {
  const [tab, setTab] = useState("catalogue");
  const [catalogue, setCatalogue] = useState([]);
  const [search, setSearch] = useState("");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("");
  const [desc, setDesc] = useState("");
  const [ownsIds, setOwnsIds] = useState([]);
  const [busy, setBusy] = useState(false);
  const [duplicate, setDuplicate] = useState(null);

  useEffect(() => {
    if (!open) return;
    setTab("catalogue"); setSearch("");
    setName(""); setEmail(""); setRole(""); setDesc(""); setOwnsIds([]);
    setDuplicate(null);
    (async () => {
      try { const d = await listCatalogue(contextId); setCatalogue(d.members || []); }
      catch { /* silent */ }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const filtered = useMemo(() => {
    if (!search.trim()) return catalogue;
    const s = search.toLowerCase();
    return catalogue.filter(
      (m) => (m.name || "").toLowerCase().includes(s)
          || (m.email || "").toLowerCase().includes(s),
    );
  }, [catalogue, search]);

  const pickFromCatalogue = (m) => {
    setName(m.name || "");
    setEmail(m.email || "");
    setTab("new");
  };

  const submit = async (force = false) => {
    if (!name.trim() || !email.trim()) {
      toast.error("Name and email are required."); return;
    }
    setBusy(true);
    try {
      // Step 1 — upsert into the catalogue.
      await addCatalogueMember(contextId, {
        name: name.trim(), email: email.trim(),
      });
      // Step 2 — duplicate check on this agenda item if applicable.
      const targetItemId = ownsIds.length === 1 ? ownsIds[0] : agendaItemId;
      if (!force && targetItemId) {
        try {
          const d = await checkTeamDuplicate(contextId, cycleId, targetItemId, {
            name: name.trim(), email: email.trim(),
          });
          if (d.duplicate) {
            setDuplicate(d);
            setBusy(false);
            return;
          }
        } catch { /* silent — proceed to create */ }
      }
      // Step 3 — create per-cycle team row.
      await api.post(
        `/contexts/${contextId}/cycle/team?cycle_id=${encodeURIComponent(cycleId)}`,
        {
          name: name.trim(), email: email.trim(),
          role: role.trim() || null,
          contribution_description: desc.trim() || "—",
          owns_item_ids: ownsIds,
        },
      );
      toast.success("Member added.");
      onOpenChange(false);
      onAdded && onAdded();
    } catch (e) {
      toast.error(apiErrorMessage(e));
    } finally { setBusy(false); }
  };

  const toggleItem = (id) => {
    setOwnsIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent className="max-w-2xl" data-testid="add-team-member-dialog">
        <AlertDialogHeader>
          <AlertDialogTitle className="akki-serif">Add Team Member</AlertDialogTitle>
        </AlertDialogHeader>
        <Tabs value={tab} onChange={setTab} />

        {tab === "catalogue" ? (
          <div data-testid="add-member-tab-pane-catalogue">
            <div className="relative mb-3">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--muted)]" />
              <Input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search catalogue by name or email…"
                className="pl-9 rounded-sm text-[13.5px]"
                data-testid="add-member-search"
              />
            </div>
            <div className="border border-[var(--rule)] rounded-sm divide-y divide-[var(--rule)] max-h-[300px] overflow-y-auto bg-white">
              {filtered.length === 0 ? (
                <p className="px-4 py-6 text-[12.5px] text-[var(--muted)] text-center">
                  {search ? "No matches." : "No catalogue entries yet — switch to the New Member tab to add one."}
                </p>
              ) : filtered.map((m) => (
                <button
                  key={m.id} type="button"
                  onClick={() => pickFromCatalogue(m)}
                  className="block w-full text-left px-4 py-2 hover:bg-[var(--parchment)]"
                  data-testid={`catalogue-pick-${m.id}`}
                >
                  <p className="text-[13.5px] text-[var(--ink)]">{m.name}</p>
                  <p className="text-[11.5px] text-[var(--muted)] font-mono">{m.email}</p>
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div data-testid="add-member-tab-pane-new">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="akki-meta text-[11px] uppercase tracking-[0.12em]">Name</Label>
                <Input
                  value={name} onChange={(e) => setName(e.target.value)}
                  placeholder="Full name"
                  className="rounded-sm mt-1 text-[13.5px]"
                  data-testid="add-member-name"
                />
              </div>
              <div>
                <Label className="akki-meta text-[11px] uppercase tracking-[0.12em]">Email</Label>
                <Input
                  value={email} onChange={(e) => setEmail(e.target.value)}
                  placeholder="name@example.com"
                  className="rounded-sm mt-1 text-[13.5px] font-mono"
                  data-testid="add-member-email"
                />
              </div>
            </div>
            <div className="mt-3">
              <Label className="akki-meta text-[11px] uppercase tracking-[0.12em]">Role (optional)</Label>
              <Input
                value={role} onChange={(e) => setRole(e.target.value)}
                placeholder="e.g. CFO, Head of Strategy"
                className="rounded-sm mt-1 text-[13.5px]"
                data-testid="add-member-role"
              />
            </div>
            <div className="mt-3">
              <Label className="akki-meta text-[11px] uppercase tracking-[0.12em]">Contribution description</Label>
              <Textarea
                value={desc} onChange={(e) => setDesc(e.target.value)}
                rows={2}
                placeholder="What will they bring to this cycle?"
                className="rounded-sm mt-1 text-[13px]"
                data-testid="add-member-desc"
              />
            </div>
            {agendaItems.length > 0 && (
              <div className="mt-3">
                <Label className="akki-meta text-[11px] uppercase tracking-[0.12em]">Assign to agenda items</Label>
                <div className="flex flex-wrap gap-2 mt-2">
                  {agendaItems.map((it) => {
                    const on = ownsIds.includes(it.id);
                    return (
                      <button
                        key={it.id} type="button"
                        onClick={() => toggleItem(it.id)}
                        className={[
                          "px-2.5 py-1 rounded-sm border text-[12px]",
                          on
                            ? "bg-[color:var(--oxblood)] border-[color:var(--oxblood)] text-white"
                            : "bg-white border-[var(--rule)] text-[var(--ink)] hover:border-[color:var(--oxblood)]",
                        ].join(" ")}
                        data-testid={`add-member-item-${it.id}`}
                      >
                        {it.label}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            {duplicate && (
              <div
                className="mt-3 border border-amber-200 bg-amber-50 rounded-sm px-3 py-2 text-[12.5px]"
                data-testid="add-member-duplicate-warning"
              >
                <p className="text-amber-900">{duplicate.warning}</p>
                <div className="mt-2 flex gap-2">
                  <Button size="sm" variant="ghost" onClick={() => setDuplicate(null)} className="text-[11.5px]">
                    Cancel
                  </Button>
                  <Button
                    size="sm" onClick={() => submit(true)}
                    className="text-[11.5px] bg-[color:var(--oxblood)] hover:bg-[color:var(--oxblood-deep)] text-white"
                    data-testid="add-member-duplicate-add-anyway"
                  >
                    Add anyway
                  </Button>
                </div>
              </div>
            )}
          </div>
        )}

        <AlertDialogFooter>
          <AlertDialogCancel disabled={busy} data-testid="add-member-cancel">Cancel</AlertDialogCancel>
          <Button
            size="sm"
            onClick={() => submit(false)}
            disabled={busy || !name.trim() || !email.trim() || tab === "catalogue"}
            className="bg-[color:var(--oxblood)] hover:bg-[color:var(--oxblood-deep)] text-white"
            data-testid="add-member-submit"
          >
            {busy ? <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" /> : <UserPlus className="w-3.5 h-3.5 mr-1" />}
            Add
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
