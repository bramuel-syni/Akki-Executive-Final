# Marketing assets — slug map

Source-of-truth list for marketing/website imagery. The Sprint M.1+
JSX rewrite consumes from this map. All 10 native PNGs ship at
1408×768 and live under `/frontend/public/marketing/`.

## Slug → file → role

| Slug | File (public path) | Native size | Voice-clean role |
| --- | --- | --- | --- |
| `hero_executive_reading` | `/marketing/hero_executive_reading.png` | 1408×768 | Primary hero option A — executive in quiet reading attitude. |
| `editorial_conversation_oblique` | `/marketing/editorial_conversation_oblique.png` | 1408×768 | Hero option B — two-person editorial conversation at oblique angle. |
| `south_asian_executive_portrait` | `/marketing/south_asian_executive_portrait.png` | 1408×768 | Hero option C — single executive portrait. |
| `modern_vault_detail` | `/marketing/modern_vault_detail.png` | 1408×768 | Security page — vault detail shot. |
| `secure_archive_corridor` | `/marketing/secure_archive_corridor.png` | 1408×768 | Security page — archive corridor. |
| `cohort_peer_group` | `/marketing/cohort_peer_group.png` | 1408×768 | Cohort page — peer group setting. |
| `empty_boardroom_set` | `/marketing/empty_boardroom_set.png` | 1408×768 | Trust / Methodology — atmospheric set piece. |
| `modern_library_interior` | `/marketing/modern_library_interior.png` | 1408×768 | About / Methodology — interior backdrop. |
| `boardroom_flatlay` | `/marketing/boardroom_flatlay.png` | 1408×768 | Editorial — paper pack flatlay. |
| `hands_annotated_report` | `/marketing/hands_annotated_report.png` | 1408×768 | Ambient use only — soft (depicts an annotated letter, not a report). |

## srcset convention

Native PNGs are 1408×768. They serve as the @2x source for any
CSS-rendered width up to 704px. Recommended usage:

```jsx
<img
  src="/marketing/hero_executive_reading.png"
  alt="<voice-clean alt text — must pass scripts/lint_voice.py>"
  width={1408}
  height={768}
  loading="lazy"
  decoding="async"
  className="..."
/>
```

For above-the-fold heroes, drop `loading="lazy"` and add
`fetchpriority="high"` instead.

For tighter rendered widths (e.g. cohort peer group at 480px CSS),
declare srcset:

```jsx
<img
  src="/marketing/cohort_peer_group.png"
  srcSet="/marketing/cohort_peer_group.png 1408w"
  sizes="(max-width: 768px) 100vw, 480px"
  alt="..."
  width={1408}
  height={768}
  loading="lazy"
/>
```

## Alt-text constraints (voice lint)

Every `alt` attribute on these images must pass
`scripts/lint_voice.py` (and the M.0b ban list including the late
addition documented in `WEBSITE_BRIEF_V3.md §1.3.1`). The scanner
runs against marketing/website JSX automatically.

PASS pattern — declarative + concrete + no banned vocabulary:
  * "An executive reading paper materials in a quiet study."
  * "Two people in editorial conversation at an oblique angle."
  * "A peer group of executives in conversation."

FAIL pattern — any alt text matching a word in the main ban list
(`WEBSITE_BRIEF_V3.md §1.3`) or the late-additions list (§1.3.1).
The scanner emits the offending line + the matched word; fix in
place rather than re-running until clean.

## CLS prevention

All `<img>` mounts MUST set explicit `width={1408} height={768}` to
reserve aspect ratio. Browsers will compute the intrinsic ratio
(11:6) and reserve layout space before bytes arrive.

## Status

Authored 2026-02 during Sprint M.0a. The 10 native PNGs are
mirrored from the original cloudfront generations and are stable
under `/frontend/public/marketing/`.
