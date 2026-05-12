/**
 * CreateArtefactModal — Patch 2B.1.
 *
 * Minimal "create a new artefact" surface used by the Decks and Reports
 * tabs' contextual action rows. Asks for a title and a source
 * (existing brief / blank / upload), creates an empty row in the
 * target collection with status `draft`, and navigates the user to
 * the existing editor surface for that artefact kind.
 *
 * Scope (Patch 2B.1 — locked):
 *   • Two artefact kinds: "deck" and "report".
 *   • Source picker is wired but minimal — source_brief_id is forwarded
 *     to the backend; "blank" and "upload" leave the artefact empty and
 *     the user lands in the editor with a blank slate.
 *   • We DO NOT build a new editor in this patch. The router redirect
 *     uses the existing detail surfaces:
 *       deck   → /app/decks/{id}
 *       report → /app/cycle?tab=overview&report={id}
 */
import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, apiErrorMessage } from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import { Loader2 } from "lucide-react";


const KIND_LABEL = {
  deck:   { title: "Create a new deck",   submit: "Create deck",   route: (id) => `/app/decks/${id}` },
  report: { title: "Create a new report", submit: "Create report", route: (id) => `/app/cycle?tab=overview&report=${id}` },
};


export default function CreateArtefactModal({ open, onClose, kind, contextId, onCreated }) {
  const navigate = useNavigate();
  const [title, setTitle] = useState("");
  const [source, setSource] = useState("blank");
  const [briefs, setBriefs] = useState([]);
  const [selectedBriefId, setSelectedBriefId] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open || source !== "brief" || !contextId) return undefined;
    let dead = false;
    api
      .get(`/contexts/${contextId}/briefings/aggregates`, { params: { kind: "briefing", page_size: 50 } })
      .then(({ data }) => { if (!dead) setBriefs(data?.items || []); })
      .catch(() => { if (!dead) setBriefs([]); });
    return () => { dead = true; };
  }, [open, source, contextId]);

  useEffect(() => {
    if (!open) {
      setTitle("");
      setSource("blank");
      setSelectedBriefId("");
    }
  }, [open]);

  const label = KIND_LABEL[kind] || KIND_LABEL.deck;

  const submit = async (e) => {
    e?.preventDefault?.();
    const t = title.trim();
    if (!t) {
      toast.error("Title is required.");
      return;
    }
    setBusy(true);
    try {
      const body = {
        title: t,
        source,
        source_brief_id: source === "brief" ? selectedBriefId || null : null,
      };
      const path = kind === "report"
        ? `/contexts/${contextId}/cycle/reports/compose`
        : `/contexts/${contextId}/decks`;
      const { data } = await api.post(path, body);
      const newId = data?.id || data?.report?.id || data?.deck?.id;
      toast.success(`${kind === "report" ? "Report" : "Deck"} created.`);
      onCreated && onCreated(data);
      onClose && onClose();
      if (newId) navigate(label.route(newId));
    } catch (err) {
      toast.error(apiErrorMessage(err, `Could not create ${kind}.`));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(v) => !v && !busy && onClose && onClose()}>
      <DialogContent className="max-w-lg bg-[var(--parchment)]" data-testid={`create-artefact-modal-${kind}`}>
        <DialogHeader>
          <DialogTitle className="akki-serif text-[18px] text-[var(--ink)]">{label.title}</DialogTitle>
          <DialogDescription className="text-[12.5px] text-[var(--muted)]">
            Give it a title. Pick a source. We'll land you in the editor.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={submit} className="space-y-4">
          <div>
            <Label className="text-[12px]" htmlFor="create-artefact-title">Title</Label>
            <Input
              id="create-artefact-title"
              autoFocus
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder={kind === "report" ? "e.g. Q1 Board Report" : "e.g. April ExCo Read-out"}
              className="rounded-sm text-[13.5px] mt-1"
              data-testid={`create-artefact-title-${kind}`}
            />
          </div>

          <fieldset>
            <legend className="text-[12px] text-[var(--muted)] mb-2">Start from</legend>
            <div className="space-y-1.5">
              {[
                { key: "blank",  label: "Blank — I'll write it from scratch." },
                { key: "brief",  label: "An existing brief in this context." },
                { key: "upload", label: "An external document I'll attach later." },
              ].map((opt) => (
                <label
                  key={opt.key}
                  className={[
                    "flex items-start gap-2 px-3 py-2 border rounded-sm cursor-pointer",
                    source === opt.key
                      ? "border-[var(--ink)] bg-white"
                      : "border-[var(--rule)] hover:border-[var(--ink)]/40",
                  ].join(" ")}
                >
                  <input
                    type="radio"
                    name="source"
                    checked={source === opt.key}
                    onChange={() => setSource(opt.key)}
                    className="mt-1"
                    data-testid={`create-artefact-source-${opt.key}`}
                  />
                  <span className="text-[13px] text-[var(--ink)]">{opt.label}</span>
                </label>
              ))}
            </div>
          </fieldset>

          {source === "brief" && (
            <div data-testid="create-artefact-brief-picker">
              <Label className="text-[12px]">Pick a brief</Label>
              <select
                value={selectedBriefId}
                onChange={(e) => setSelectedBriefId(e.target.value)}
                className="mt-1 w-full border border-[var(--rule)] rounded-sm px-2 py-2 text-[13px] bg-white"
              >
                <option value="">— None selected —</option>
                {briefs.map((b) => (
                  <option key={b.id} value={b.id}>{b.name}</option>
                ))}
              </select>
              {briefs.length === 0 && (
                <p className="text-[11.5px] text-[var(--muted)] italic mt-1">
                  No briefs in this context yet. Pick "Blank" instead.
                </p>
              )}
            </div>
          )}

          <DialogFooter>
            <Button type="button" variant="ghost" onClick={onClose} disabled={busy}>Cancel</Button>
            <Button
              type="submit"
              disabled={busy || !title.trim()}
              className="bg-[var(--ink)] hover:bg-[var(--ink)]/90 text-[var(--parchment)] rounded-sm"
              data-testid={`create-artefact-submit-${kind}`}
            >
              {busy && <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" />}
              {label.submit}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
