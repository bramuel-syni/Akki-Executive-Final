/**
 * parchmentFold — Patch 12 Streaming v3 workspace transition helper.
 *
 * Coordinates the parchment-fold animation for workspace/role/company
 * transitions:
 *   • outgoing: vertical-shrink to 0 (origin top) + opacity → 0 (200ms)
 *   • hold:     100ms (skip if data already loaded)
 *   • incoming: vertical-expand 0→full + opacity 0→1 (240ms ease-out)
 *
 * If the swap is INSTANT (cached data, no network), skip the fold entirely.
 * If load > 600ms, hold the mid-state with an ink-bleed indicator at the
 * page top until data arrives.
 *
 * Public API:
 *   const fold = createParchmentFold({ outgoingEl, onMidpoint, onComplete });
 *   await fold.run(loadPromise);  // returns when fold completes
 *
 * This is a CSS-driven implementation — the helper applies classes from
 * `index.css` (akki-transition-fold-out / akki-transition-fold-in /
 * akki-transition-ink-bleed) and awaits transitionend.
 */

const OUTGOING_MS = 200;
const HOLD_MS = 100;
const INCOMING_MS = 240;
const HOLD_THRESHOLD_MS = 600;
const INSTANT_THRESHOLD_MS = 80;


function applyFoldOut(el) {
  if (!el) return Promise.resolve();
  el.classList.add("akki-transition-fold-out");
  return new Promise((res) => setTimeout(res, OUTGOING_MS));
}

function applyFoldIn(el) {
  if (!el) return Promise.resolve();
  el.classList.add("akki-transition-fold-in");
  return new Promise((res) => setTimeout(res, INCOMING_MS));
}


export function createParchmentFold({ outgoingEl, onMidpoint, onComplete } = {}) {
  let inkBleedEl = null;

  const installInkBleed = () => {
    if (inkBleedEl) return;
    inkBleedEl = document.createElement("div");
    inkBleedEl.className = "akki-transition-ink-bleed";
    inkBleedEl.setAttribute("data-testid", "transition-ink-bleed");
    document.body.appendChild(inkBleedEl);
  };
  const removeInkBleed = () => {
    if (inkBleedEl && inkBleedEl.parentNode) {
      inkBleedEl.parentNode.removeChild(inkBleedEl);
    }
    inkBleedEl = null;
  };

  const run = async (loadPromise) => {
    const t0 = performance.now();
    let loadResolved = false;
    let result;
    const wrapped = Promise.resolve(loadPromise).then((r) => {
      loadResolved = true;
      result = r;
      return r;
    });

    // Race load against the "instant" threshold — if data lands within
    // 80ms we skip the fold entirely.
    await Promise.race([
      wrapped,
      new Promise((res) => setTimeout(res, INSTANT_THRESHOLD_MS)),
    ]);
    if (loadResolved && (performance.now() - t0) < INSTANT_THRESHOLD_MS) {
      onComplete && onComplete(result);
      return result;
    }

    // Real fold path.
    await applyFoldOut(outgoingEl);
    onMidpoint && onMidpoint();

    // If the load is taking a while, install the ink-bleed indicator.
    const longHold = (performance.now() - t0) > HOLD_THRESHOLD_MS || !loadResolved;
    if (longHold) installInkBleed();
    await Promise.race([wrapped, new Promise((res) => setTimeout(res, HOLD_MS))]);
    if (!loadResolved) {
      installInkBleed();
      await wrapped;
    }
    removeInkBleed();

    await applyFoldIn(outgoingEl);
    onComplete && onComplete(result);
    return result;
  };

  return { run };
}
