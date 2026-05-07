/**
 * AllDocumentsButton — Phase E (MEMO Item 1, decision D-006).
 *
 * Single visible-on-every-homepage CTA that takes the user to the
 * Documents Journal listing. Replaces the old "Document Journal"
 * top-nav slot, which collapses to whitespace per D-006. The button
 * carries a count badge fetched from
 * `GET /api/contexts/{cid}/documents` so the user sees how many
 * documents the active context holds without leaving Home.
 *
 * Layout-only — restraint copy, single accent on the icon, no busy
 * detail. Used identically on HomeExecutive / HomeNed / HomeDual /
 * HomeUndeclared.
 */
import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import { FolderOpen, ArrowRight } from "lucide-react";

export default function AllDocumentsButton() {
  const { activeContext } = useAuth();
  const cid = activeContext?.id;
  const [count, setCount] = useState(null);

  useEffect(() => {
    if (!cid) return;
    let cancelled = false;
    (async () => {
      try {
        const { data } = await api.get(`/contexts/${cid}/documents`, { params: { limit: 500 } });
        if (cancelled) return;
        setCount(Array.isArray(data) ? data.length : 0);
      } catch {
        if (!cancelled) setCount(0);
      }
    })();
    return () => { cancelled = true; };
  }, [cid]);

  return (
    <Link
      to="/app/workspace"
      data-testid="home-all-documents-btn"
      className="
        inline-flex items-center gap-3 px-4 py-3 border border-[var(--rule)]
        bg-white rounded-md hover:bg-[var(--cream-deep)]/40
        hover:border-[var(--accent)] transition-colors
        no-underline
      "
    >
      <FolderOpen className="w-4 h-4 text-[var(--accent)]" strokeWidth={1.7} />
      <span className="akki-serif text-[15px] text-[var(--ink)] leading-none">
        All documents
      </span>
      {count !== null && (
        <span
          className="
            ml-1 inline-flex items-center justify-center min-w-[26px] h-[22px]
            text-[11.5px] font-mono text-[var(--ink)] bg-[var(--cream-deep)]
            border border-[var(--rule)] rounded-full px-2
          "
          data-testid="home-all-documents-count"
        >
          {count}
        </span>
      )}
      <ArrowRight className="w-3.5 h-3.5 text-[var(--muted)] ml-1" strokeWidth={1.7} />
    </Link>
  );
}
