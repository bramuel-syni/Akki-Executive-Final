/**
 * NedInboxTile — compact inbox-pending indicator for HomeNed.
 *
 * Calls GET /api/ned/inbox/assignments and surfaces the pending count.
 * Click → /app/ned/inbox.
 */
import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { Inbox, ChevronRight } from "lucide-react";


export default function NedInboxTile() {
  const [pending, setPending] = useState(null);
  const [accepted, setAccepted] = useState(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const { data } = await api.get("/ned/inbox/assignments");
        if (!alive) return;
        const items = data?.items || [];
        setPending(items.filter((i) => i.status === "pending").length);
        setAccepted(items.filter((i) => i.status === "accepted").length);
      } catch {
        if (!alive) return;
        setPending(0); setAccepted(0);
      }
    })();
    return () => { alive = false; };
  }, []);

  return (
    <Link
      to="/app/ned/inbox"
      data-testid="ned-home-inbox-tile"
      className="block mb-5 border border-[var(--rule)] bg-white rounded-md px-4 py-3 hover:border-[color:var(--oxblood)] transition-colors group"
    >
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Inbox className="w-4 h-4 text-[color:var(--oxblood)]" />
          <div>
            <p className="akki-serif text-[14.5px] text-[var(--ink)]">Inbox</p>
            <p className="akki-meta text-[11.5px] mt-0.5">
              {pending === null ? (
                "Loading…"
              ) : pending > 0 ? (
                <>
                  <span className="text-[color:var(--oxblood)] font-mono">{pending} pending</span>
                  {accepted > 0 && <> · {accepted} accepted</>}
                </>
              ) : (
                accepted > 0
                  ? <>No new. {accepted} previously accepted.</>
                  : "No assignments yet."
              )}
            </p>
          </div>
        </div>
        <ChevronRight className="w-4 h-4 text-[var(--muted)] group-hover:text-[color:var(--oxblood)]" />
      </div>
    </Link>
  );
}
