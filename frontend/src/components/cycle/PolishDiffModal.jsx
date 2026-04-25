import React, { useMemo } from "react";
import {
  Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Sparkles, CheckCircle2, X } from "lucide-react";

/**
 * Tiny, dependency-free word-level diff. Marks unchanged words plain,
 * removed words with strikethrough red, and added words highlighted green.
 * Algorithm: longest-common-subsequence on whitespace-tokenised input.
 * Good enough for board-paper-length bodies (≤ 4k words).
 */
function wordDiff(a, b) {
  const A = (a || "").split(/(\s+)/);
  const B = (b || "").split(/(\s+)/);
  const m = A.length, n = B.length;
  // LCS DP table
  const dp = Array.from({ length: m + 1 }, () => new Uint16Array(n + 1));
  for (let i = m - 1; i >= 0; i--) {
    for (let j = n - 1; j >= 0; j--) {
      dp[i][j] = A[i] === B[j] ? 1 + dp[i + 1][j + 1] : Math.max(dp[i + 1][j], dp[i][j + 1]);
    }
  }
  const out = [];
  let i = 0, j = 0;
  while (i < m && j < n) {
    if (A[i] === B[j]) { out.push({ t: "eq", v: A[i] }); i++; j++; }
    else if (dp[i + 1][j] >= dp[i][j + 1]) { out.push({ t: "rem", v: A[i] }); i++; }
    else { out.push({ t: "add", v: B[j] }); j++; }
  }
  while (i < m) out.push({ t: "rem", v: A[i++] });
  while (j < n) out.push({ t: "add", v: B[j++] });
  // Collapse adjacent same-type tokens for cleaner rendering
  const collapsed = [];
  for (const tok of out) {
    if (collapsed.length && collapsed[collapsed.length - 1].t === tok.t) {
      collapsed[collapsed.length - 1].v += tok.v;
    } else { collapsed.push({ ...tok }); }
  }
  return collapsed;
}

/**
 * PolishDiffModal — surfaces the AKKI-polished body with a word-level diff
 * before the executive accepts the change. Acceptance triggers `onAccept`
 * which the parent uses to `setBody(polished)`. Reject closes without
 * changing the body.
 */
export default function PolishDiffModal({ open, onClose, original, polished, onAccept }) {
  const diff = useMemo(
    () => (open && original !== undefined && polished !== undefined ? wordDiff(original, polished) : []),
    [open, original, polished],
  );
  const stats = useMemo(() => {
    let added = 0, removed = 0;
    for (const t of diff) {
      const wc = t.v.trim().split(/\s+/).filter(Boolean).length;
      if (t.t === "add") added += wc;
      else if (t.t === "rem") removed += wc;
    }
    return { added, removed };
  }, [diff]);

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-4xl max-h-[88vh] bg-[var(--cream)] border border-[var(--rule)] flex flex-col" data-testid="polish-diff-modal">
        <DialogHeader>
          <DialogTitle className="akki-serif text-[22px] font-normal flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-[var(--accent)]" /> AKKI's polish — review the change
          </DialogTitle>
          <DialogDescription className="text-[12.5px] text-[var(--muted)]">
            <span className="text-emerald-700 font-medium">+{stats.added} added</span>
            {" · "}
            <span className="text-red-700 font-medium">−{stats.removed} removed</span>
            {" · "}
            Accept the polish to replace your draft, or reject to keep what you had.
          </DialogDescription>
        </DialogHeader>

        <div
          className="flex-1 overflow-y-auto bg-white border border-[var(--rule)] rounded-md p-5 text-[13.5px] leading-[1.7] font-mono whitespace-pre-wrap"
          data-testid="polish-diff-body"
        >
          {diff.map((tok, i) => {
            if (tok.t === "eq") return <span key={i} className="text-[var(--deep)]">{tok.v}</span>;
            if (tok.t === "add") return <span key={i} className="bg-emerald-100 text-emerald-900 rounded-sm px-0.5">{tok.v}</span>;
            return <span key={i} className="bg-red-100 text-red-800 line-through rounded-sm px-0.5">{tok.v}</span>;
          })}
        </div>

        <div className="flex justify-end gap-2 pt-3 border-t border-[var(--rule)]">
          <Button variant="outline" onClick={onClose} className="border-[var(--rule)]" data-testid="polish-diff-reject">
            <X className="w-3.5 h-3.5 mr-1.5" /> Reject — keep my draft
          </Button>
          <Button onClick={onAccept} className="bg-[var(--chrome)] text-white" data-testid="polish-diff-accept">
            <CheckCircle2 className="w-3.5 h-3.5 mr-1.5" /> Accept polish
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
