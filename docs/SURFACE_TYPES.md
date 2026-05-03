# Route → surface mapping (Phase 13.4)

_Companion to `ACCESSIBILITY.md` and `lighthouserc.json`._

The UI/UX architect brief defines five surface types. Each AKKI route maps
to exactly one type, which determines the Lighthouse CI performance budget.

| Surface | FCP ≤ | LCP ≤ | TTI ≤ | Why |
| --- | --- | --- | --- | --- |
| Stream         | 1.6s | 2.5s | 3.5s | News-feed pace; users skim. |
| Workspace      | 1.8s | 2.8s | 4.0s | Heavier UI (composers, multi-tab tabs). |
| Reading        | 1.4s | 2.2s | 3.0s | Reading needs first-paint snap. |
| Structural     | 1.8s | 2.8s | 4.0s | Cycle / Monitor dashboards — list + chart heavy. |
| Conversational | 1.6s | 2.5s | 3.5s | Streaming UI — first message must arrive fast. |

## Mapping

| Route | Surface | Reason |
| --- | --- | --- |
| `/` (Landing)              | Stream         | Marketing first-impression; brand/hero band. |
| `/about`, `/features`, `/security`, `/plans`, `/enterprise`, `/early-access`, `/blog` | Stream | Marketing read-only pages. |
| `/solva` (landing)         | Stream         | Marketing landing for the Solva module. |
| `/signin`, `/signup`       | Stream         | Single-form auth pages. |
| `/app` (Home, role-aware)  | Stream         | News-feed style stream of stream-cards. |
| `/app/pulse`               | Stream         | Same chrome class as Home. |
| `/app/learn`               | Stream         | Editorial article list. |
| `/app/work-studio`         | Workspace      | Multi-source aggregator (briefings + decks + reports). |
| `/app/solva` (in-app)      | Workspace      | 4-phase composer with side rail + dialogs. |
| `/app/decks/:id`           | Workspace      | Block composer; multi-pane. |
| `/app/studio/composer/:kind/:artefactId` | Workspace | Block composer. |
| `/app/cycle`               | Structural    | Outer 5 tabs + inner 6-tab spine workflow. |
| `/app/monitor`             | Structural    | Function-aware tile dashboard. |
| `/app/influence`           | Structural    | Influence map graph. |
| `/app/contexts`            | Structural    | Context list + invitation table. |
| `/app/manage`              | Structural    | Settings/people management dashboard. |
| `/app/documents/:id` (Reading View) | Reading | Long-form rail-commentary reader. |
| `/app/chat`                | Conversational | Streaming multi-model chat. |

## Baseline (2026-05-04)

First-run desktop Lighthouse on three sample URLs (one per accessible bucket):

| URL | FCP | LCP | TTI | TBT | CLS | Verdict |
| --- | --- | --- | --- | --- | --- | --- |
| `/`        | 744ms  | 3528ms | 3691ms | 482ms | 0.000 | LCP + TBT warn |
| `/security`| 728ms  | 2249ms | 2431ms | 266ms | 0.000 | All pass |
| `/solva`   | 730ms  | 2241ms | 2445ms | 301ms | 0.000 | TBT warn (1ms over) |

Only the homepage misses LCP — driven by the hero image. Tracked for
optimisation in 13.x+1 (defer image, preconnect Unsplash, smaller asset).
