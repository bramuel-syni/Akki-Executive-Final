"""Phase F.3 — Task-level intelligence service.

Mirrors the document-level pattern from `services/documents/intelligence_service.py`:
async, Shield-bounded, cached on `db.task_intelligence` keyed by
`(task_id, task_hash)` so the cache invalidates whenever the task
spec changes.

Surfaces 4 sections on the Intelligence tab:
  1. Readiness breakdown — numeric contribution of the 60/25/15 split.
  2. Blockers — overdue contributions, missing approvals, low-adherence
     contributions. RULE-BASED (no LLM needed).
  3. Gaps — output-spec items not yet covered. RULE-BASED.
  4. Completion roadmap — bullet list of remaining steps to reach
     100% readiness. RULE-BASED.
  5. Recommendations — Shield-bounded LLM-voiced advice. Falls back to
     rule-derived prose when Shield is down so the tab is never empty.
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


log = logging.getLogger("akki.tasks.intel")


# ═════════════════════════════════════════════════════════════════════
# Cache key
# ═════════════════════════════════════════════════════════════════════
def task_hash(task: Dict[str, Any]) -> str:
    """Deterministic hash over the fields that affect the intelligence
    output. Excludes mutable timestamps (`updated_at`, `created_at`)."""
    bits = json.dumps({
        "name":             task.get("name"),
        "objective":        task.get("objective"),
        "success_criteria": task.get("success_criteria"),
        "output_spec":      task.get("output_spec"),
        "team":             task.get("team"),
        "state":            task.get("state"),
        "due_date":         task.get("due_date"),
    }, sort_keys=True, default=str)
    return hashlib.sha256(bits.encode("utf-8")).hexdigest()[:32]


# ═════════════════════════════════════════════════════════════════════
# Rule-based analysis (no LLM)
# ═════════════════════════════════════════════════════════════════════
_READINESS_WEIGHTS = {"approved": 0.60, "submitted": 0.25, "adherence": 0.15}


def readiness_breakdown(task: Dict[str, Any]) -> Dict[str, Any]:
    """Compute readiness via the orchestrator-locked formula:
    60% approved + 25% submitted + 15% avg objective-adherence."""
    team = task.get("team") or []
    n = max(1, len(team))
    n_approved = sum(1 for m in team if m.get("status") == "approved")
    n_submitted = sum(1 for m in team if m.get("status") in ("submitted", "approved"))
    adherences = [m.get("adherence_score", 0) for m in team if m.get("adherence_score") is not None]
    avg_adherence = (sum(adherences) / len(adherences)) if adherences else 0
    approved_pct  = (n_approved  / n) * 100
    submitted_pct = (n_submitted / n) * 100
    score = round(
        approved_pct  * _READINESS_WEIGHTS["approved"]
      + submitted_pct * _READINESS_WEIGHTS["submitted"]
      + avg_adherence * _READINESS_WEIGHTS["adherence"],
    )
    return {
        "score": max(0, min(100, int(score))),
        "components": [
            {"key": "approved",  "weight": 60, "value": round(approved_pct),
             "label": f"{n_approved}/{n} contributors approved"},
            {"key": "submitted", "weight": 25, "value": round(submitted_pct),
             "label": f"{n_submitted}/{n} contributors submitted"},
            {"key": "adherence", "weight": 15, "value": round(avg_adherence),
             "label": f"Avg objective-adherence score: {round(avg_adherence)}"},
        ],
    }


def _days_until(iso_str: Optional[str]) -> Optional[int]:
    if not iso_str:
        return None
    try:
        # Accept date-only ("2026-12-31") and full ISO
        if len(iso_str) == 10:
            dt = datetime.fromisoformat(iso_str + "T00:00:00+00:00")
        else:
            dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return (dt.date() - datetime.now(timezone.utc).date()).days
    except (ValueError, TypeError):
        return None


def blockers(task: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Concrete items blocking compile. Each blocker has:
      `kind` ∈ {overdue, missing_approval, low_adherence}
      `severity` ∈ {high, medium, low}
      `message` — human prose
      `target` — actionable jump target (e.g., contributor id)"""
    out: List[Dict[str, Any]] = []
    for m in (task.get("team") or []):
        d = _days_until(m.get("due_date"))
        if d is not None and d < 0 and m.get("status") not in ("submitted", "approved"):
            out.append({
                "kind":     "overdue",
                "severity": "high",
                "message":  f"{m.get('name') or m.get('email') or 'A contributor'} is {abs(d)} day{'s' if abs(d) != 1 else ''} overdue.",
                "target":   {"type": "contributor", "id": m.get("email") or m.get("name")},
            })
        elif m.get("status") == "submitted":
            out.append({
                "kind":     "missing_approval",
                "severity": "medium",
                "message":  f"{m.get('name') or m.get('email') or 'A contributor'}'s submission is awaiting approval.",
                "target":   {"type": "contributor", "id": m.get("email") or m.get("name")},
            })
        elif m.get("status") == "needs_revision":
            out.append({
                "kind":     "low_adherence",
                "severity": "medium",
                "message":  f"{m.get('name') or m.get('email') or 'A contributor'}'s submission needs revision.",
                "target":   {"type": "contributor", "id": m.get("email") or m.get("name")},
            })
    return out


def gaps(task: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Output-spec items not yet covered."""
    out: List[Dict[str, Any]] = []
    spec = task.get("output_spec") or {}
    team = task.get("team") or []
    if not spec.get("template_id") and not spec.get("free_text"):
        out.append({
            "kind": "output_spec_missing",
            "message": "Output specification is missing. Set a template or free-text description in Step 2 of the wizard.",
        })
    if not team:
        out.append({
            "kind": "no_contributors",
            "message": "No contributors are assigned yet. Add at least one team member to begin tracking progress.",
        })
    # Per-format completion check.
    formats = spec.get("formats") or []
    for fmt in formats:
        if not any((m.get("contribution") or "").lower().find(fmt) >= 0 for m in team):
            # Heuristic — not authoritative, just surfaces hint.
            pass
    return out


def roadmap(task: Dict[str, Any], rb: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Bullet list of remaining steps to reach 100% readiness."""
    steps: List[Dict[str, Any]] = []
    team = task.get("team") or []
    for m in team:
        status = m.get("status") or "not_started"
        if status == "not_started":
            steps.append({
                "kind":   "kickoff_contribution",
                "label":  f"Kick off {m.get('name') or m.get('email') or 'this contribution'} — {m.get('contribution') or 'their contribution'}.",
                "target": {"type": "contributor", "id": m.get("email") or m.get("name")},
            })
        elif status == "in_progress":
            steps.append({
                "kind":   "follow_up_contribution",
                "label":  f"Follow up with {m.get('name') or m.get('email') or 'the contributor'} on their in-progress section.",
                "target": {"type": "contributor", "id": m.get("email") or m.get("name")},
            })
        elif status == "submitted":
            steps.append({
                "kind":   "approve_contribution",
                "label":  f"Review and approve {m.get('name') or m.get('email') or 'this contribution'}'s submission.",
                "target": {"type": "contributor", "id": m.get("email") or m.get("name")},
            })
        elif status == "needs_revision":
            steps.append({
                "kind":   "revise_contribution",
                "label":  f"{m.get('name') or m.get('email') or 'The contributor'} needs to revise before this can land.",
                "target": {"type": "contributor", "id": m.get("email") or m.get("name")},
            })
    if rb["score"] == 100 and (task.get("output_spec") or {}).get("template_id"):
        steps.append({
            "kind":   "ready_to_compile",
            "label":  "All contributions approved. Ready to compile.",
            "target": None,
        })
    return steps


def _fallback_recommendations(task: Dict[str, Any], bl: List[Dict[str, Any]], gp: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Rule-derived prose used when the LLM call fails or is bypassed.
    Keeps the tab non-empty so the user sees something honest."""
    out: List[Dict[str, Any]] = []
    for b in bl[:3]:
        out.append({
            "id":     f"rec-{b['kind']}-{(b.get('target') or {}).get('id') or 'global'}",
            "kind":   "rule_based",
            "title":  b["message"],
            "action": "Open the Contributions tab to act on this.",
            "source": "rule",
        })
    for g in gp[:2]:
        out.append({
            "id":     f"rec-{g['kind']}",
            "kind":   "rule_based",
            "title":  g["message"],
            "action": "Open the Plan tab to update the spec.",
            "source": "rule",
        })
    if not out:
        out.append({
            "id":     "rec-on-track",
            "kind":   "rule_based",
            "title":  "No active blockers detected. Task is on track.",
            "action": "Keep momentum — check in with contributors via the Contributions tab.",
            "source": "rule",
        })
    return out


async def _llm_recommendations(task: Dict[str, Any], rb: Dict[str, Any], bl: List[Dict[str, Any]], gp: List[Dict[str, Any]], user_id: str) -> Optional[List[Dict[str, Any]]]:
    """Best-effort Shield call for LLM-voiced recommendations. Returns
    None on any failure — caller substitutes the rule-based fallback."""
    try:
        from services.synisense.shield.client import invoke as shield_invoke
    except Exception:
        return None
    prompt = (
        "You are a senior executive coach reviewing the status of a task. "
        "Given the task spec, readiness breakdown, blockers, and gaps "
        "below, propose 2-3 specific recommendations the owner should "
        "act on. Return strict JSON only — shape:\n"
        '[{"id":"...","title":"<≤120 chars>","action":"<one sentence>"}, ...]\n\n'
        f"TASK NAME: {task.get('name')}\n"
        f"OBJECTIVE: {task.get('objective')}\n"
        f"SUCCESS CRITERIA: {task.get('success_criteria')}\n"
        f"READINESS: {rb['score']}%\n"
        f"BLOCKERS: {json.dumps([b['message'] for b in bl])}\n"
        f"GAPS: {json.dumps([g['message'] for g in gp])}\n"
    )
    try:
        result = await shield_invoke(
            purpose="task_manager.intelligence.recommendations",
            content=prompt,
            tenant_id=user_id,
            consumer_id="tasks",
            user_id=user_id,
            model_preference="balanced",
        )
    except Exception as e:  # noqa: BLE001
        log.warning("task intel shield failed: %s", e)
        return None
    raw = (result.get("response") or "").strip()
    import re
    m = re.search(r"\[[\s\S]*\]", raw)
    if not m:
        return None
    try:
        parsed = json.loads(m.group(0))
    except (ValueError, json.JSONDecodeError):
        return None
    if not isinstance(parsed, list):
        return None
    out: List[Dict[str, Any]] = []
    for i, item in enumerate(parsed[:4]):
        if not isinstance(item, dict):
            continue
        title  = (item.get("title")  or "").strip()
        action = (item.get("action") or "").strip()
        if not title:
            continue
        out.append({
            "id":     item.get("id") or f"llm-rec-{i}",
            "kind":   "llm_voiced",
            "title":  title[:200],
            "action": action[:300] if action else "",
            "source": "llm",
        })
    return out or None


# ═════════════════════════════════════════════════════════════════════
# Orchestrator — full intelligence payload
# ═════════════════════════════════════════════════════════════════════
async def build_intelligence(task: Dict[str, Any], user_id: str, allow_llm: bool = True) -> Dict[str, Any]:
    """Run all 5 sections. LLM is optional — recommendations fall back
    to rule-derived prose."""
    rb = readiness_breakdown(task)
    bl = blockers(task)
    gp = gaps(task)
    rm = roadmap(task, rb)
    recs: Optional[List[Dict[str, Any]]] = None
    if allow_llm:
        recs = await _llm_recommendations(task, rb, bl, gp, user_id)
    if not recs:
        recs = _fallback_recommendations(task, bl, gp)
    return {
        "task_id":         task.get("id"),
        "task_hash":       task_hash(task),
        "generated_at":    datetime.now(timezone.utc).isoformat(),
        "readiness":       rb,
        "blockers":        bl,
        "gaps":            gp,
        "roadmap":         rm,
        "recommendations": recs,
    }
