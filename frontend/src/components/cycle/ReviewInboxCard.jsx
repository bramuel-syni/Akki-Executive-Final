import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { Clock, ArrowRight } from "lucide-react";

/**
 * ReviewInboxCard — surfaces every report (across every context) where the
 * signed-in user is the current pending reviewer. Rendered on Home only when
 * there's at least one. Cross-context by design: a CFO sitting on three
 * boards sees a single card with all three pending reviews stacked.
 */
export default function ReviewInboxCard() {
  const [items, setItems] = useState([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get("/reports/inbox");
        setItems(data.reports || []);
      } catch { /* silent — non-critical */ }
      finally { setLoaded(true); }
    })();
  }, []);

  if (!loaded || items.length === 0) return null;

  return (
    <div
      className="bg-amber-50 border-l-4 border-amber-400 border border-amber-200 rounded-r-md p-4 mb-5"
      data-testid="review-inbox-card"
    >
      <div className="flex items-center gap-2 mb-2.5">
        <Clock className="w-3.5 h-3.5 text-amber-700" strokeWidth={2} />
        <p className="akki-overline text-amber-800">
          {items.length === 1 ? "1 report awaiting your review" : `${items.length} reports awaiting your review`}
        </p>
      </div>
      <ul className="space-y-1.5">
        {items.slice(0, 5).map((r) => (
          <li key={r.id} className="flex items-baseline gap-2">
            <Link
              to={`/app/cycle?report=${r.id}`}
              className="akki-serif text-[14.5px] text-[var(--ink)] hover:text-[var(--accent)] transition-colors flex-1 min-w-0"
              data-testid={`review-inbox-item-${r.id}`}
            >
              <span className="truncate">{r.title}</span>
              <span className="text-[12px] text-amber-700/80 ml-2">— from {r.author_name}</span>
            </Link>
            <ArrowRight className="w-3.5 h-3.5 text-amber-700/60" />
          </li>
        ))}
      </ul>
    </div>
  );
}
