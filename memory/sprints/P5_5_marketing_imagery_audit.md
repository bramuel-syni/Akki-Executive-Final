# P5.5.B — Marketing imagery audit & replacement catalog (2026-02)

Scope: every photograph with a human subject in `frontend/public/marketing/` and `frontend/src/website/assets/`. Classification:

- **KEEP** — clearly within target executive demographic (35-55 apparent age band), diverse, or non-human imagery.
- **REPLACE** — elderly-presenting subject (60+ apparent age) — the user's stated concern.
- **VERIFY-WITH-USER** — ambiguous case OR replacement risks narrative meaning loss.

Working threshold: subjects in the 60+ apparent band are REPLACE; 45-60 are KEEP (within target range); 30-45 are unambiguously KEEP.

Image analysis performed via Gemini vision analysis on each PNG/WebP. Raw output captured per file.

## Catalog

| File | Used at | Subject(s) — apparent age / gender / ethnicity | Classification |
|---|---|---|---|
| `public/marketing/hero_executive_reading.png` (+.webp) | `website/pages/Home.jsx:84,86` Home hero | Female, **30-45**, Black | **KEEP** |
| `public/marketing/cohort_peer_group.png` (+.webp) | (asset present, not currently referenced from JSX — likely an enqueued M.0a asset) | 3 subjects: Female 30-45 South Asian; Female 45-60 Caucasian; Male 30-45 Black | **KEEP** |
| `public/marketing/editorial_conversation_oblique.png` (+.webp) | (asset present, not currently referenced) | Female 30-45 South Asian + Male 45-60 Black | **KEEP** |
| `public/marketing/south_asian_executive_portrait.png` (+.webp) | (asset present, not currently referenced) | Male, late 40s-early 50s, South Asian | **KEEP** |
| `public/marketing/hands_annotated_report.png` (+.webp) | (asset present, not currently referenced) | Hands only — 30-50, male, South Asian/Middle Eastern; no face | **KEEP** (no demographic concern; partial human) |
| `public/marketing/boardroom_flatlay.png` (+.webp) | (asset present, not currently referenced) | No human — boardroom flat lay | **KEEP** |
| `public/marketing/empty_boardroom_set.png` (+.webp) | (asset present, not currently referenced) | No human — empty boardroom | **KEEP** |
| `public/marketing/modern_library_interior.png` (+.webp) | (asset present, not currently referenced) | No human — library interior | **KEEP** |
| `public/marketing/modern_vault_detail.png` (+.webp) | (asset present, not currently referenced) | No human — vault detail | **KEEP** |
| `public/marketing/secure_archive_corridor.png` (+.webp) | (asset present, not currently referenced) | No human — archive corridor | **KEEP** |
| `src/website/assets/v7/audience-triptych.webp` | `website/pages/Home.jsx:200` "Three Audiences" section — **THE USER-FLAGGED TRIPTYCH** | Panel 1: Male, **60+**, South Asian/Middle Eastern; Panel 2: Female, 30-45, Caucasian; Panel 3: Male, 45-60, African | **REPLACE** (Panel 1 fails the threshold) |
| `src/website/assets/v7/for-executives-hero.webp` | `website/pages/ForExecutives.jsx:8` /for-executives hero | Male, 45-60, East Asian (heavily graying) | **VERIFY-WITH-USER** (technically in band but reads as senior; user explicitly flagged "screenshots 3 and 4 show photographs dominated by elderly executives" so confirmation needed before replacing) |
| `src/website/assets/v7/for-neds-hero.webp` | `website/pages/ForNeds.jsx:8` /for-non-executive-directors hero | Female, **60+**, South Asian/East Asian | **REPLACE** |
| `src/website/assets/v7/home-hero.webp` | `website/WebsiteShell.jsx:22` default OG share image (overridden on Home page itself but the default for any non-overriding page) | Female, **late 50s-60s**, Black | **REPLACE** |
| `src/website/assets/v7/tier1-safety-band.webp` | `website/pages/Home.jsx:136` Tier 1 safety band | No human — institutional ledger with marginalia | **KEEP** |
| `src/website/assets/hero-library.jpg` | (asset present, not directly referenced in v7 surfaces) | No human — library shot | **KEEP** |
| `src/website/assets/trust-wax-seal.jpg` | (referenced) | No human — wax seal | **KEEP** |
| `src/website/assets/what-archive-boxes.jpg` | (referenced) | No human — archive boxes | **KEEP** |
| `src/website/assets/why-fountain-pen.jpg` | (referenced) | No human — fountain pen | **KEEP** |
| `src/website/assets/evidence/{chat_audit,solva_trace,work_studio_diff}.png` | Home evidence section | Product screenshots, no human subjects | **KEEP** |

## Action summary

- **REPLACE (3):** `audience-triptych.webp`, `for-neds-hero.webp`, `home-hero.webp`. Replacement generation via nano-banana per the brief: monochrome, library/office, 35-55 apparent age band, balanced diversity across the surface as a whole.
- **VERIFY-WITH-USER (1):** `for-executives-hero.webp` — male 45-60 East Asian. The subject is within the target band but reads as senior in a way that matches the user's "screenshots 3 and 4" concern. Surfacing for explicit go/no-go before regenerating. Do NOT auto-replace.
- **KEEP (everything else):** all non-human assets + the explicitly diverse 30-45/45-60 subjects.

## Replacement aesthetic brief (applied to all REPLACE items)

- Monochrome (black-and-white), high-contrast editorial photography.
- Library / private office / wood-panelled study settings, consistent with the existing v7 brand palette.
- Subjects in the **35-55 apparent age band**.
- Across the FULL marketing surface, aim for balanced representation across gender presentation, ethnicity, and physical ability. Diversity expressed across the surface as a whole, not within any one frame.
- Focused reading posture (board pack, briefing folder, open ledger) — same narrative cue as the originals; the only swap is the subject's apparent age band.
- WebP-first via the existing `scripts/transcode_marketing.py` pipeline (PNG fallback only if pipeline already produces both).

## Diversity intent across the post-replacement marketing surface

After P5.5.B, the human-photography set on the live marketing surface will be:

| Surface | Subject(s) — post-replacement intent |
|---|---|
| Home hero (`hero_executive_reading.png`) | KEEP — Black female, 30-45 (unchanged) |
| Audience triptych | REPLACE — three subjects, three apparent age bands within 35-55, three different ethnicities, at least one female |
| For-executives hero | KEEP / VERIFY — pending user decision |
| For-neds hero | REPLACE — single subject, 35-55, gender + ethnicity selected to balance the rest of the surface |
| Home-hero OG default | REPLACE — single subject, 35-55, gender + ethnicity selected to balance the rest of the surface |

## Alt text follow-up

Each replacement asset will carry alt text matching the existing voice contract (board pack reading, no demographic descriptors); voice-lint must pass on the new alt strings before commit.
