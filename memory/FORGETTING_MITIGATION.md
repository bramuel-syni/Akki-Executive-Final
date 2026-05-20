# Forgetting Mitigation — anti-ghost-ID + auto-compaction recovery

**Status:** Mandatory pre-read for every agent and every dispatch.
**Created:** 2026-05-18 (forgetting-mitigation patch).

## 1. Why this exists

On 2026-05-18 a dispatch asked the dev to fix QA findings `HP-01`, `DJ-R01`,
`DJ-R02`, `DJ-R04`, and `HP-02` — none of which existed on disk; the referenced
`/app/memory/sprints/QA_FINDINGS_15MAY.md` file was missing and `grep` across
the entire `/app` tree returned zero hits for those IDs. The corrective
forgetting-mitigation dispatch that followed was itself interrupted by an
auto-compaction event mid-flight, causing the resuming agent to re-ask the
original blocker question instead of resuming from disk. Both failures are the
same class: **working from memory / handoff briefs instead of from the
on-disk source of truth**.

## 2. Hard rules — every future agent

1. **Never invent finding IDs or feature codes.** If a brief references an ID and
   `grep -r '<ID>' /app/memory /app/backend /app/frontend` returns zero hits,
   **STOP** and ask the user. Do not guess a mapping from the ID to a visible
   row in any other table.
2. **Every user-uploaded artefact MUST be persisted to `/app/memory/<topic>/`
   BEFORE acting on it.** Front matter records: `source_url`,
   `original_filename`, `retrieved` (date), `parser`, `persisted_by`. No work
   begins until the artefact is on disk.
3. **Every dev dispatch must quote verbatim from the on-disk source file**, not
   from a session handoff brief. If the brief and the on-disk file disagree,
   **the file wins**. Update the brief, not the file.
4. **After every patch, append to `SYSTEM_STATE.md § 4`** (newest-at-top) with
   the QA-IDs touched and file paths changed. One sprint dispatch = one closeout
   entry, with anchor back to the QA backlog row.
5. **If auto-compaction interrupts a multi-deliverable dispatch**, the resume
   path is fixed: re-read `READ_FIRST.md` → `QA_BACKLOG.md` → check which
   deliverables exist on disk → continue from the first missing one. **Never
   re-ask the original blocker question if the user has since provided the
   artefact.** The blocker is resolved the moment the artefact lands on disk.

## 3. Pre-dispatch checklist (orchestrator must clear before sending a brief)

```
[ ] Every ID in this brief resolves via grep on /app/memory and /app/backend
    and /app/frontend (zero unmatched IDs)
[ ] Every requirement points to a file path or a QA backlog row
[ ] Quoting verbatim from on-disk source, not paraphrasing
[ ] If the user uploaded an artefact this turn, it has been persisted
    (with front-matter source URL + retrieval date) before dispatching
    work against it
```

## 4. Recovery procedure when protocol is violated

1. **Stop work.** Do not patch downstream files until the source is real.
2. **Persist the missing artefact.** Download from the user-provided URL (or
   ask for it), parse with the appropriate library (`python-docx`, `pypdf`,
   `openpyxl`, etc.), and write to `/app/memory/<topic>/` with the
   mandated front-matter.
3. **Rebuild the affected backlog row(s) from disk.** Update
   `QA_BACKLOG.md` (or the equivalent canonical tracker) so the on-disk
   table matches the persisted source.
4. **Resume from the verified on-disk state.** Never from the brief.
   Re-quote verbatim from the file when authoring the next sprint chunk.

## 5. References

- Ghost-ID dispatch closeout: `/app/memory/SYSTEM_STATE.md` § 4 entry
  *"Chunk 7 dispatch — BLOCKED on missing spec — 2026-05-18"*.
- Source of truth for the 16-May QA report: `/app/memory/qa_reports/QA_REPORT_16MAY2026.md`.
- Master tracker: `/app/memory/qa_reports/QA_BACKLOG.md`.
- Memory entry-point: `/app/memory/READ_FIRST.md` (rows 0 + 0.5 point here).
