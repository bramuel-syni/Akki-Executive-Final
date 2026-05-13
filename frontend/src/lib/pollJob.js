/**
 * Async-job polling helper (Chunk 2, 2026-05-13).
 *
 * The three long-running endpoints (signals generate, briefing
 * create, cycle draft-compilation) now return 202 + { job_id }
 * immediately and run the heavy work in the background. The frontend
 * polls `GET /api/jobs/{id}` until the job reaches a terminal state
 * (`completed` | `failed`).
 *
 * This helper keeps the call-site simple:
 *
 *     const { data } = await api.post("/contexts/123/signals/generate", {});
 *     const job = await pollJob(data.job_id, {
 *       onProgress: (status, elapsedS) => setBusyMessage(`Working… ${elapsedS}s`),
 *     });
 *     if (job.status === "failed") throw new Error(job.error);
 *     const payload = job.result;
 *
 * Polling cadence: 1.5 s for the first 30 s, then exponential
 * backoff up to a 5 s cap, with a hard 6-minute ceiling.
 */
import { api } from "@/lib/api";

const FAST_INTERVAL_MS = 1500;
const SLOW_INTERVAL_CAP_MS = 5000;
const FAST_PHASE_S = 30;
const TIMEOUT_S = 360; // 6 minutes — generous; the worker has its own LLM timeouts

/**
 * @param {string} jobId
 * @param {object} [opts]
 * @param {(status: string, elapsedS: number) => void} [opts.onProgress]
 * @param {() => boolean} [opts.cancelled] return true to abort polling
 * @returns {Promise<{status: "completed"|"failed", result?: any, error?: string|null, [k:string]: any}>}
 */
export async function pollJob(jobId, opts = {}) {
  const { onProgress, cancelled } = opts;
  const startedAt = Date.now();
  let interval = FAST_INTERVAL_MS;
  while (true) {
    if (cancelled && cancelled()) {
      return { status: "failed", error: "Cancelled by user" };
    }
    const elapsedS = Math.floor((Date.now() - startedAt) / 1000);
    if (elapsedS > TIMEOUT_S) {
      return { status: "failed", error: "Timed out after 6 minutes" };
    }
    let row;
    try {
      const { data } = await api.get(`/jobs/${jobId}`);
      row = data;
    } catch (e) {
      // Transient poll error — give the worker time and retry. Three
      // network errors in a row break out of the loop, with the last
      // error reported to the caller.
      if ((opts._retries = (opts._retries || 0) + 1) >= 3) {
        return { status: "failed", error: e?.message || "Polling failed" };
      }
      await sleep(interval);
      continue;
    }
    opts._retries = 0;
    onProgress?.(row.status, elapsedS);
    if (row.status === "completed" || row.status === "failed") {
      return row;
    }
    await sleep(interval);
    if (elapsedS > FAST_PHASE_S) {
      interval = Math.min(SLOW_INTERVAL_CAP_MS, Math.floor(interval * 1.4));
    }
  }
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}
