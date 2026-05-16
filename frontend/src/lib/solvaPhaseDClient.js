/**
 * Phase D Solva session API client.
 *
 * Talks to the new context-scoped endpoints at
 *   /api/contexts/{cid}/solva/v2/*
 * and exposes a small surface the new SolvaPhaseDSession page consumes.
 *
 * Response normalisation happens here — pages get a clean shape:
 *   { sessionId, layerState, status, nextQuestion, acknowledgement,
 *     synthesisText, refusalRendering, refusalReason, auditIdsCount }
 */
import { api } from "@/lib/api";

function normalize(session) {
  if (!session) return null;
  const l3 = session.layer_3 || {};
  return {
    raw: session,
    sessionId: session.session_id,
    contextId: session.context_id,
    layerState: session.layer_state,
    status: session.status,
    subModule: session.sub_module,
    nextQuestion: session.next_question || null,
    acknowledgement: session.acknowledgement || null,
    initialFraming: session.initial_framing || "",
    auditIdsCount: (session.synisense_audit_ids || []).length,
    synthesisText: l3.rendered_synthesis || null,
    primaryDiagnosis: l3.primary_diagnosis_prose || null,
    refusalRendering: l3.refusal_rendering || null,
    refusalReason: l3.refusal_reason || null,
    refusalFlag: !!l3.refusal_flag,
    scenarios: l3.scenarios || [],
    sensitivityDrivers: l3.sensitivity_drivers || [],
    surfacedTensions: l3.surfaced_tensions || [],
    layer4Answers: (session.layer_4 || {}).answers || [],
    // Phase E.5 (2026-05-16) — seed-handoff provenance + Layer 0 anchors.
    sourceHandoff: session.source_handoff || null,
    seedAttachedReferences: session.seed_attached_references || [],
  };
}

export async function createPhaseDSession({ contextId, subModule, seedPayload }) {
  const body = { sub_module: subModule };
  if (seedPayload) body.seed_payload = seedPayload;
  const { data } = await api.post(
    `/contexts/${contextId}/solva/v2/sessions`,
    body,
  );
  return normalize(data);
}

export async function getPhaseDSession({ contextId, sessionId }) {
  const { data } = await api.get(
    `/contexts/${contextId}/solva/v2/sessions/${sessionId}`,
  );
  return normalize(data);
}

export async function submitFraming({ contextId, sessionId, framingText }) {
  const { data } = await api.post(
    `/contexts/${contextId}/solva/v2/sessions/${sessionId}/framing`,
    { framing_text: framingText },
  );
  return normalize(data);
}

export async function submitAnswer({ contextId, sessionId, answerText }) {
  const { data } = await api.post(
    `/contexts/${contextId}/solva/v2/sessions/${sessionId}/answer`,
    { answer_text: answerText },
  );
  return normalize(data);
}

export async function refuseSession({ contextId, sessionId, operatorReason }) {
  const { data } = await api.post(
    `/contexts/${contextId}/solva/v2/sessions/${sessionId}/refuse`,
    { operator_reason: operatorReason || null },
  );
  return normalize(data);
}

export async function listPhaseDSessions({ contextId, status, limit = 50 }) {
  const params = { limit };
  if (status) params.status = status;
  const { data } = await api.get(
    `/contexts/${contextId}/solva/v2/sessions`,
    { params },
  );
  return {
    items: (data.items || []).map(normalize),
    count: data.count || 0,
  };
}
