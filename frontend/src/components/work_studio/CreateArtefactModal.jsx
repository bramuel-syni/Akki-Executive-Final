/**
 * CreateArtefactModal — Patch 2B.1 (initial scaffold) + Chunk 5
 * (2026-05-13) systemic fix.
 *
 * The Decks and Reports tabs each expose a "Create …" action chip in
 * Work Studio. This modal asks for a title, a creation source, and
 * (when the source needs it) a pointer to the brief or document the
 * draft is composed against. It then posts to the unified
 *   POST /api/contexts/{cid}/work-studio/artefacts
 * endpoint, which inserts a draft row in `db.decks` / `db.reports`
 * and returns a `redirect_url` pointing at the block composer.
 *
 * Three sources are supported per kind (deck × report = 6 paths total):
 *
 *   • blank              — empty body, user composes from scratch
 *   • brief              — references an existing Work Studio brief
 *                          (stripped of the `briefing::` aggregate
 *                          prefix before sending)
 *   • external_document  — references a document already uploaded to
 *                          this workspace (single `<select>` picker)
 *
 * Chunk 5 fixes WS-R09 / R10 / R11 / R13 / R14 — the modal previously
 * posted to non-existent backend routes and never bound an external
 * document.
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
  deck:   { title: "Create a new deck",   submit: "Create deck",   noun: "deck" },
  report: { title: "Create a new report", submit: "Create report", noun: "report" },
};

// The aggregates listing emits compound ids like `briefing::<uuid>`.
// The backend tolerates either form for defence-in-depth, but we
// strip here too so audit logs and ids in flight stay clean.
function stripAggPrefix(raw, expectedPrefix) {
  if (!raw || typeof raw !== "string") return "";
  const idx = raw.indexOf("::");
  if (idx < 0) return raw;
  const prefix = raw.slice(0, idx);
  if (prefix === expectedPrefix) return raw.slice(idx + 2);
  return raw;
}


export default function CreateArtefactModal({ open, onClose, kind, contextId, onCreated }) {
  const navigate = useNavigate();
  const [title, setTitle] = useState("");
  const [source, setSource] = useState("blank");
  const [briefs, setBriefs] = useState([]);
  const [selectedBriefId, setSelectedBriefId] = useState("");
  const [documents, setDocuments] = useState([]);
  const [selectedDocumentId, setSelectedDocumentId] = useState("");
  const [briefsLoading, setBriefsLoading] = useState(false);
  const [documentsLoading, setDocumentsLoading] = useState(false);
  const [busy, setBusy] = useState(false);

  // Briefs come from the Work Studio aggregates listing — same call
  // the Briefing tab already makes. We only refetch when the user
  // actually picks the brief source, to avoid surprising network
  // traffic on accounts that never use this path.
  useEffect(() => {
    if (!open || source !== "brief" || !contextId) return undefined;
    let dead = false;
    setBriefsLoading(true);
    api
      .get(`/contexts/${contextId}/briefings/aggregates`, { params: { kind: "briefing", page_size: 50 } })
      .then(({ data }) => { if (!dead) setBriefs(data?.items || []); })
      .catch(() => { if (!dead) setBriefs([]); })
      .finally(() => { if (!dead) setBriefsLoading(false); });
    return () => { dead = true; };
  }, [open, source, contextId]);

  // Documents — fetched lazily when the external-document source is
  // chosen. We keep it simple: list everything the workspace has and
  // let the user pick. Future polish can add a search input.
  useEffect(() => {
    if (!open || source !== "external_document" || !contextId) return undefined;
    let dead = false;
    setDocumentsLoading(true);
    api
      .get(`/contexts/${contextId}/documents`, { params: { limit: 200 } })
      .then(({ data }) => { if (!dead) setDocuments(Array.isArray(data) ? data : (data?.documents || [])); })
      .catch(() => { if (!dead) setDocuments([]); })
      .finally(() => { if (!dead) setDocumentsLoading(false); });
    return () => { dead = true; };
  }, [open, source, contextId]);

  useEffect(() => {
    if (!open) {
      setTitle("");
      setSource("blank");
      setSelectedBriefId("");
      setSelectedDocumentId("");
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
    if (source === "brief" && !selectedBriefId) {
      toast.error("Pick a brief or switch to Blank.");
      return;
    }
    if (source === "external_document" && !selectedDocumentId) {
      toast.error("Pick a document or switch to Blank.");
      return;
    }
    setBusy(true);
    try {
      const payload = {
        kind,
        title: t,
        source,
        source_brief_id: source === "brief"
          ? stripAggPrefix(selectedBriefId, "briefing")
          : null,
        source_document_id: source === "external_document"
          ? selectedDocumentId
          : null,
      };
      const { data } = await api.post(
        `/contexts/${contextId}/work-studio/artefacts`,
        payload,
      );
      const newId = data?.artefact_id;
      const redirect = data?.redirect_url || (newId ? `/app/studio/composer/${kind}/${newId}` : null);
      toast.success(`${label.noun.charAt(0).toUpperCase()}${label.noun.slice(1)} created.`);
      onCreated && onCreated(data);
      onClose && onClose();
      if (redirect) navigate(redirect);
    } catch (err) {
      toast.error(apiErrorMessage(err, `Could not create ${label.noun}.`));
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
            Give it a title. Pick a source. We&apos;ll land you in the editor.
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
                { key: "blank",              label: "Blank — I'll write it from scratch." },
                { key: "brief",              label: "An existing brief in this workspace." },
                { key: "external_document",  label: "An external document I've already uploaded." },
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
                data-testid="create-artefact-brief-select"
              >
                <option value="">— None selected —</option>
                {briefs.map((b) => (
                  <option key={b.id} value={b.id}>{b.name}</option>
                ))}
              </select>
              {!briefsLoading && briefs.length === 0 && (
                <p className="text-[11.5px] text-[var(--muted)] italic mt-1" data-testid="create-artefact-brief-empty">
                  No briefs in this workspace yet. Compose one through Solva, or pick &quot;Blank&quot;.
                </p>
              )}
              {briefsLoading && (
                <p className="text-[11.5px] text-[var(--muted)] italic mt-1 inline-flex items-center gap-1">
                  <Loader2 className="w-3 h-3 animate-spin" /> Loading briefs…
                </p>
              )}
            </div>
          )}

          {source === "external_document" && (
            <div data-testid="create-artefact-document-picker">
              <Label className="text-[12px]">Pick a document</Label>
              <select
                value={selectedDocumentId}
                onChange={(e) => setSelectedDocumentId(e.target.value)}
                className="mt-1 w-full border border-[var(--rule)] rounded-sm px-2 py-2 text-[13px] bg-white"
                data-testid="create-artefact-document-select"
              >
                <option value="">— None selected —</option>
                {documents.map((d) => (
                  <option key={d.id} value={d.id}>{d.name || d.original_name || d.id}</option>
                ))}
              </select>
              {!documentsLoading && documents.length === 0 && (
                <p className="text-[11.5px] text-[var(--muted)] italic mt-1" data-testid="create-artefact-document-empty">
                  No documents uploaded yet. Upload one via the &quot;+ Add document&quot; button, then re-open this dialog.
                </p>
              )}
              {documentsLoading && (
                <p className="text-[11.5px] text-[var(--muted)] italic mt-1 inline-flex items-center gap-1">
                  <Loader2 className="w-3 h-3 animate-spin" /> Loading documents…
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
