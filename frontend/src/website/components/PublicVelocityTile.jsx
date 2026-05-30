/**
 * Website v7 — /trust public velocity tile (Sprint M.3, 2026-02 dispatch 18).
 *
 * Reads /api/public/observability/reasoning_velocity?window=30d.
 * Three-state copy locked verbatim:
 *   - 0 sessions     → "Solva is in a quiet patch. Reasoning velocity is reported when sessions have completed."
 *   - 1-4 sessions   → "Solva is warming up. Velocity reports once five sessions have completed in the window."
 *   - 5+ sessions    → "Akki delivers a fully-cited 16-slide diagnosis in <avg>s on average. p95 <p95>s."
 *
 * Public copy uses "Akki" (not "Solva") since prospects may not yet
 * know the product-internal names. The matching internal-surface
 * variant in TrustCenter.jsx::ReasoningVelocityTile (ZZ.4) uses
 * "Solva" because authenticated users know the internal name.
 */
import React, { useEffect, useState } from "react";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL || "";

export default function PublicVelocityTile() {
  const [data, setData] = useState(null);
  useEffect(() => {
    let cancel = false;
    (async () => {
      try {
        const r = await axios.get(
          `${API}/api/public/observability/reasoning_velocity?window=30d`,
        );
        if (!cancel) setData(r.data);
      } catch (_err) { /* fail silent — empty-state copy below covers the failure surface */ }
    })();
    return () => { cancel = true; };
  }, []);

  const sessions = data?.session_count ?? 0;
  let copy;
  let testidSuffix;
  if (sessions === 0) {
    copy = "Solva is in a quiet patch. Reasoning velocity is reported when sessions have completed.";
    testidSuffix = "quiet";
  } else if (sessions < 5) {
    copy = "Solva is warming up. Velocity reports once five sessions have completed in the window.";
    testidSuffix = "warming";
  } else {
    const avgS = Math.round(((data.avg_ms_per_slide || 0) * 16) / 1000);
    const p95S = Math.round((data.p95_ms || 0) / 1000);
    copy = `Akki delivers a fully-cited 16-slide diagnosis in ${avgS}s on average. p95 ${p95S}s.`;
    testidSuffix = "numeric";
  }
  return (
    <section className="website-section section-reveal" data-testid="trust-public-velocity">
      <p className="kicker">REASONING VELOCITY · LAST 30 DAYS</p>
      <p
        className="dek"
        data-testid={`trust-public-velocity-${testidSuffix}`}
        style={{ maxWidth: 70 + "ch" }}
      >
        {copy}
      </p>
    </section>
  );
}
