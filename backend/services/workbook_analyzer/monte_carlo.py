"""Phase P5.14 — Monte Carlo simulation.

Pure-numpy, deterministic-seed. Run shape:

  sample N iterations from the chosen distribution
  evaluate the formula on each sample (default: identity `=x`)
  compute percentile bands (P10/P25/P50/P75/P90)
  compute mean / stddev
  build a 50-bucket histogram

Determinism contract: given the same `(column, distribution,
params, formula, iterations, seed)` tuple, two runs MUST produce
byte-identical band values. The `reproducer_hash` is the sha256 of
that tuple — a separate test asserts the same inputs produce the
same outputs.

Distributions supported:

  normal:     params = {"mean": float, "stddev": float}
  lognormal:  params = {"mu": float, "sigma": float}      # underlying normal
  uniform:    params = {"low": float, "high": float}
  triangular: params = {"low": float, "mode": float, "high": float}

Formula support: v1 only evaluates the identity (`=x`) or a simple
linear transform of the form `=a*x + b` (`a` and `b` are numeric
literals). Anything richer raises ValueError. The spec calls out
column-reference formulas as advanced — we surface that as
future work in the memo, not in this MVP.
"""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from typing import Dict, Iterable, List, Optional

import numpy as np

from .schema import (
    DistributionKind,
    MonteCarloRun,
    NarrationBlock,
    WorkbookCitation,
)


_LINEAR_RE = re.compile(
    r"^=\s*(?P<a>-?\d+(?:\.\d+)?)\s*\*\s*x\s*([+\-]\s*\d+(?:\.\d+)?)?\s*$"
)


def _parse_formula(formula: str) -> tuple[float, float]:
    """Return `(a, b)` for `=a*x + b`. Default `=x` → (1.0, 0.0)."""
    if not formula or formula.strip().lower() in ("=x", "x"):
        return 1.0, 0.0
    m = _LINEAR_RE.match(formula.strip())
    if not m:
        raise ValueError(
            f"workbook_analyze.monte_carlo: unsupported formula {formula!r} "
            "(MVP supports identity '=x' or '=a*x+b' with numeric literals)"
        )
    a = float(m.group("a"))
    tail = (m.group(2) or "").replace(" ", "")
    b = float(tail) if tail else 0.0
    return a, b


def _sample(
    distribution: DistributionKind,
    params: Dict[str, float],
    iterations: int,
    seed: int,
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    if distribution == "normal":
        mu = float(params.get("mean", 0.0))
        sigma = float(params.get("stddev", 1.0))
        if sigma <= 0:
            raise ValueError("normal: stddev must be > 0")
        return rng.normal(loc=mu, scale=sigma, size=iterations)
    if distribution == "lognormal":
        mu = float(params.get("mu", 0.0))
        sigma = float(params.get("sigma", 0.5))
        if sigma <= 0:
            raise ValueError("lognormal: sigma must be > 0")
        return rng.lognormal(mean=mu, sigma=sigma, size=iterations)
    if distribution == "uniform":
        low = float(params.get("low", 0.0))
        high = float(params.get("high", 1.0))
        if high <= low:
            raise ValueError("uniform: high must be > low")
        return rng.uniform(low=low, high=high, size=iterations)
    if distribution == "triangular":
        low = float(params.get("low", 0.0))
        mode = float(params.get("mode", 0.5))
        high = float(params.get("high", 1.0))
        if not (low <= mode <= high) or high <= low:
            raise ValueError("triangular: require low <= mode <= high and high > low")
        return rng.triangular(left=low, mode=mode, right=high, size=iterations)
    raise ValueError(f"unsupported distribution: {distribution!r}")


def _reproducer_hash(
    column: str, distribution: str, params: Dict[str, float],
    formula: str, iterations: int, seed: int,
) -> str:
    payload = json.dumps({
        "column": column,
        "distribution": distribution,
        "params": {k: float(v) for k, v in sorted(params.items())},
        "formula": formula or "=x",
        "iterations": int(iterations),
        "seed": int(seed),
    }, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def run_monte_carlo(
    *,
    sheet: str,
    column: str,
    distribution: DistributionKind,
    params: Dict[str, float],
    iterations: int = 5000,
    formula: str = "=x",
    seed: int = 42,
    narration: Optional[NarrationBlock] = None,
    citations: Optional[Iterable[WorkbookCitation]] = None,
) -> MonteCarloRun:
    """Run a deterministic Monte Carlo simulation.

    Returns a fully-populated `MonteCarloRun` ready to persist to
    Mongo. Caller is responsible for resolving citations through
    `WorkbookCitationResolver` BEFORE calling this function.
    """
    if iterations < 1000 or iterations > 10_000:
        raise ValueError(f"iterations must be in [1000, 10000], got {iterations}")

    a, b = _parse_formula(formula)
    raw = _sample(distribution, params, iterations, seed)
    transformed = a * raw + b

    p10, p25, p50, p75, p90 = np.percentile(transformed, [10, 25, 50, 75, 90])
    mean = float(np.mean(transformed))
    stddev = float(np.std(transformed))

    counts, edges = np.histogram(transformed, bins=50)

    return MonteCarloRun(
        id="mc-" + uuid.uuid4().hex[:12],
        sheet=sheet,
        column=column,
        distribution=distribution,
        params={k: float(v) for k, v in params.items()},
        formula=formula or "=x",
        iterations=int(iterations),
        seed=int(seed),
        p10=float(p10),
        p25=float(p25),
        p50=float(p50),
        p75=float(p75),
        p90=float(p90),
        mean=mean,
        stddev=stddev,
        histogram_bins=[float(c) for c in counts.tolist()],
        histogram_edges=[float(e) for e in edges.tolist()],
        reproducer_hash=_reproducer_hash(
            column, distribution, params, formula, iterations, seed,
        ),
        narration=narration,
        citations=list(citations) if citations else [],
    )


__all__ = ["run_monte_carlo"]
