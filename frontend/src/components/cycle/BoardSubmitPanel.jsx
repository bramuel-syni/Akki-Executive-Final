/**
 * BoardSubmitPanel — ship step UX for the brief assignment handoff.
 *
 * Flow:
 *  1. Brief has been compiled (Step 6 has output) → user clicks
 *     "Submit for board reporting" → calls submit-for-board endpoint.
 *  2. Confirm dialog explains: submitting locks the brief for board
 *     reporting; you can still assign to multiple NEDs after.
 *  3. After submit → reveals the assignment form (named NEDs OR cohort).
 *  4. After assign → reveals a roster table of assignments with status badges.
 *
 * Visual: v7 palette, parchment surface, oxblood lift on the submit CTA.
 * No hex literals; all colours resolve through CSS tokens.
 */
import React, { useEffect, useMemo, useState } from "react";
import { api, apiErrorMessage } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import {
  AlertDialog, AlertDialogContent, AlertDialogHeader,
  AlertDialogTitle, AlertDialogDescription, AlertDialogFooter,
  AlertDialogCancel, AlertDialogAction,
} from "@/components/ui/alert-dialog";
import { toast } from "sonner";
import { Send, Users, Loader2, Check, ShieldCheck } from "lucide-react";
import CycleStatusBadge from "./CycleStatusBadge";


function fmtDate(iso) {
  if (!iso) return "—";
  try { return new Date(iso).toLocaleDateString(); } catch { return iso; }
}


export default function BoardSubmitPanel({ cid, cycleId, briefId, briefStatus, onChange }) {
  const [status, setStatus] = useState(briefStatus || "draft");
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [assignBusy, setAssignBusy] = useState(false);
  const [assignments, setAssignments] = useState([]);
  const [showAssignForm, setShowAssignForm] = useState(false);
  const [nedIdsRaw, setNedIdsRaw] = useState("");
  const [note, setNote] = useState("");

  useEffect(() => { setStatus(briefStatus || "draft"); }, [briefStatus]);

  const loadAssignments = async () => {
    if (!cid || !cycleId || !briefId) return;
    try {
      const { data } = await api.get(
        `/contexts/${cid}/cycles/${cycleId}/briefs/${briefId}/assignments`,
      );
      setAssignments(data?.assignments || []);
    } catch (e) {
      // No assignments yet is the common case; silent fail.
    }
  };

  useEffect(() => {
    if (status === "submitted" || status === "shipped") loadAssignments();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status, cid, cycleId, briefId]);

  const submit = async () => {
    setSubmitting(true);
    try {
      const { data } = await api.post(
        `/contexts/${cid}/cycles/${cycleId}/briefs/${briefId}/submit-for-board`,
      );
      setStatus(data?.board_status || "submitted");
      setConfirmOpen(false);
      setShowAssignForm(true);
      onChange && onChange(data);
      toast.success("Brief submitted for board reporting.");
    } catch (e) {
      toast.error(apiErrorMessage(e));
    } finally { setSubmitting(false); }
  };

  const assign = async () => {
    const ids = nedIdsRaw.split(/[\s,]+/).filter(Boolean);
    if (!ids.length) {
      toast.error("Add at least one NED account id.");
      return;
    }
    setAssignBusy(true);
    try {
      const { data } = await api.post(
        `/contexts/${cid}/cycles/${cycleId}/briefs/${briefId}/assignments`,
        { ned_ids: ids, note: note || null },
      );
      const newly = data?.newly_created || 0;
      toast.success(`Assigned to ${data?.count || 0} NED(s)${newly ? ` · ${newly} new` : ""}.`);
      setNedIdsRaw("");
      setNote("");
      await loadAssignments();
    } catch (e) {
      toast.error(apiErrorMessage(e));
    } finally { setAssignBusy(false); }
  };

  const cancelAssignment = async (aid) => {
    try {
      await api.delete(`/contexts/${cid}/cycle-assignments/${aid}`);
      toast.success("Assignment cancelled.");
      await loadAssignments();
    } catch (e) { toast.error(apiErrorMessage(e)); }
  };

  const rollup = useMemo(() => {
    const r = { pending: 0, accepted: 0, declined: 0, cancelled: 0 };
    for (const a of assignments) {
      if (r[a.status] !== undefined) r[a.status] += 1;
    }
    return r;
  }, [assignments]);


  /* -------------------- not yet submitted -------------------- */
  if (status === "draft") {
    return (
      <div
        className="mt-5 border-t border-[var(--rule)] pt-5"
        data-testid="board-submit-panel-draft"
      >
        <div className="flex items-start gap-3">
          <ShieldCheck className="w-5 h-5 text-[color:var(--oxblood)] mt-0.5" />
          <div className="flex-1">
            <p className="akki-serif text-[14.5px] text-[var(--ink)]">
              Send this draft to the board.
            </p>
            <p className="akki-meta text-[12px] mt-1">
              Submitting locks the brief for board reporting. You can then assign one or more
              NEDs as recipients — each accepts or declines independently.
            </p>
          </div>
          <Button
            size="sm"
            onClick={() => setConfirmOpen(true)}
            disabled={!briefId}
            className="bg-[color:var(--oxblood)] hover:bg-[color:var(--oxblood-deep)] text-white text-[12.5px]"
            data-testid="board-submit-open-confirm"
          >
            <Send className="w-3.5 h-3.5 mr-1" /> Submit for board reporting
          </Button>
        </div>

        <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle className="akki-serif">Submit this brief for board reporting?</AlertDialogTitle>
              <AlertDialogDescription className="akki-meta">
                The brief moves to <span className="font-mono">SUBMITTED</span>. You'll be able to assign it to one or
                more NEDs. NEDs see only the approved Brief artefact — no agenda metadata,
                no contribution scores, no team internals.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel disabled={submitting} data-testid="board-submit-confirm-cancel">
                Cancel
              </AlertDialogCancel>
              <AlertDialogAction
                onClick={(e) => { e.preventDefault(); submit(); }}
                disabled={submitting}
                className="bg-[color:var(--oxblood)] hover:bg-[color:var(--oxblood-deep)] text-white"
                data-testid="board-submit-confirm-go"
              >
                {submitting ? <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" /> : null}
                Submit
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    );
  }


  /* -------------------- submitted / shipped -------------------- */
  return (
    <div
      className="mt-5 border-t border-[var(--rule)] pt-5"
      data-testid="board-submit-panel-active"
    >
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Check className="w-4 h-4 text-emerald-700" />
          <span className="akki-serif text-[14.5px] text-[var(--ink)]">Board reporting</span>
          <CycleStatusBadge status={status} testId="board-submit-status" />
        </div>
        <Button
          size="sm" variant="outline"
          onClick={() => setShowAssignForm((v) => !v)}
          className="text-[12.5px]"
          data-testid="board-submit-toggle-assign"
        >
          <Users className="w-3.5 h-3.5 mr-1" />
          {showAssignForm ? "Hide assign form" : "Assign to NEDs"}
        </Button>
      </div>

      {showAssignForm && (
        <div
          className="border border-[var(--rule)] bg-[var(--parchment)] rounded-sm px-4 py-3 mb-4"
          data-testid="board-assign-form"
        >
          <Label className="akki-meta text-[11px] uppercase tracking-[0.12em]">
            NED account ids (comma or whitespace separated)
          </Label>
          <Input
            value={nedIdsRaw}
            onChange={(e) => setNedIdsRaw(e.target.value)}
            placeholder="acc-ned-12345, acc-ned-67890"
            className="rounded-sm mt-1 font-mono text-[12.5px]"
            data-testid="board-assign-ned-ids"
          />
          <Label className="akki-meta text-[11px] uppercase tracking-[0.12em] mt-3 block">
            Note for the recipient (optional)
          </Label>
          <Textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            rows={2}
            placeholder="Pre-read for the Q1 board meeting on the 15th."
            className="rounded-sm mt-1 text-[13px]"
            data-testid="board-assign-note"
          />
          <div className="flex justify-end mt-3">
            <Button
              size="sm"
              onClick={assign}
              disabled={assignBusy || !nedIdsRaw.trim()}
              className="bg-[color:var(--oxblood)] hover:bg-[color:var(--oxblood-deep)] text-white text-[12.5px]"
              data-testid="board-assign-submit"
            >
              {assignBusy ? <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" /> : <Send className="w-3.5 h-3.5 mr-1" />}
              Assign
            </Button>
          </div>
        </div>
      )}

      {assignments.length > 0 ? (
        <div
          className="border border-[var(--rule)] bg-white rounded-sm"
          data-testid="board-assign-roster"
        >
          <div className="flex items-center gap-4 px-4 py-2 border-b border-[var(--rule)] text-[11px] uppercase tracking-[0.12em] text-[var(--muted)] font-mono">
            <span>Assignments</span>
            <span>· Pending {rollup.pending}</span>
            <span>· Accepted {rollup.accepted}</span>
            <span>· Declined {rollup.declined}</span>
          </div>
          <table className="w-full text-[13px]">
            <thead>
              <tr className="text-left text-[11px] uppercase tracking-[0.1em] text-[var(--muted)]">
                <th className="px-4 py-2 font-normal">NED</th>
                <th className="px-4 py-2 font-normal">Status</th>
                <th className="px-4 py-2 font-normal">Submitted</th>
                <th className="px-4 py-2 font-normal text-right">Action</th>
              </tr>
            </thead>
            <tbody>
              {assignments.map((a) => (
                <tr key={a.id} className="border-t border-[var(--rule)]">
                  <td className="px-4 py-2 font-mono text-[12.5px] text-[var(--ink)]">{a.ned_id}</td>
                  <td className="px-4 py-2">
                    <CycleStatusBadge status={a.status} testId={`roster-status-${a.id}`} />
                  </td>
                  <td className="px-4 py-2 text-[12.5px] text-[var(--muted)]">{fmtDate(a.submitted_at)}</td>
                  <td className="px-4 py-2 text-right">
                    {a.status === "pending" && (
                      <Button
                        size="sm" variant="ghost"
                        onClick={() => cancelAssignment(a.id)}
                        className="text-[11px] text-[var(--muted)] hover:text-[color:var(--oxblood)]"
                        data-testid={`roster-cancel-${a.id}`}
                      >
                        Cancel
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p
          className="akki-meta text-[12px]"
          data-testid="board-assign-empty"
        >
          No assignments yet. Use "Assign to NEDs" to send this brief to one or more recipients.
        </p>
      )}
    </div>
  );
}
