# AKKI legacy archive

Files archived during Phase 15.3.5 cutover (the final phase before
GA). Solva v1 was retired in favour of the v2 surface; the legacy
home dispatchers (LegacyAppHome, HomeV2) were retired in favour of
the role-aware home variants under `pages/home/*.jsx`.

DO NOT IMPORT FROM THIS DIRECTORY. Files here are kept for forensic
reference only. Production code paths must not reach into `_legacy/`.

| File | Replaced by | Notes |
|---|---|---|
| backend/routers/solva_engine.py | backend/routers/solva_v2.py | v1 4-phase engine. POST endpoints retired with 410 in active tree; this copy is the pre-15.3.5 source for forensic comparison. |
| backend/solve_pdf.py | backend/routers/solva_v2.py (no v2 PDF export yet) | v1 PDF export. v2 sessions can be exported via the governance audit ZIP (Phase 15.3 §8). |
| frontend/src/pages/AppSolva.jsx.bak | frontend/src/pages/SolvaV2Poc.jsx | v1 4-phase Solva landing. The active-tree AppSolva.jsx is now a 308 stub. |
| frontend/src/pages/SolvaLanding.jsx.bak | frontend/src/pages/marketing/* (redesign in B.2c) | v1 marketing landing. Pending redesign. |
| frontend/src/pages/LegacyAppHome.jsx.bak | frontend/src/pages/home/{HomeNed,HomeExecutive,HomeDual,HomeUndeclared}.jsx | Pre-role-aware home dispatcher with the "Resume audit" card. |
| frontend/src/pages/HomeV2.jsx.bak | frontend/src/pages/home/{HomeNed,HomeExecutive,HomeDual,HomeUndeclared}.jsx | Experimental home variant. Routed only via `?home=v2` URL switch (also retired). |

Retirement date: 2026-05-04

