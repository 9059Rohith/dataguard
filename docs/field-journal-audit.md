# DataGuard field journal audit

## Baseline

DataGuard is a working FastAPI application with a vanilla HTML, CSS and JavaScript console, packaged with setuptools and deployed as a container to the existing Vercel project at `https://rohith-dataguard.vercel.app`. The active workspace stores captures and operator state in PostgreSQL. Public GitHub repository data, the separate 500-repository replay, and the bounded Gemini investigator already use their own APIs and evidence sources. No new dependency or hosting project is required.

Before changing the interface, the canonical home, readiness, impact and quality shells, workspace API, strict replay and both WOFF2 fonts were checked over HTTPS. One first readiness request returned 500 and the next probe returned 200 alongside the workspace API. This initial spot check establishes availability at the successful probe and records the transient response separately. Prior committed browser evidence covers desktop and 390px layouts and the benchmark workflow. The current brief adds further responsive and visual checks.

| Route | Existing workflow to preserve | Visual opportunity |
|---|---|---|
| Overview | Live stored counts, source trail, repository search and export | Make the real quality workflow the opening chapter, with the ledger directly after the hero |
| Datasets | Search, sort, filter, detail drawer and JSON export | A collection plate and clearer form/table rhythm |
| Contracts | Typed fields and operator-only saves | An archival folio above a quiet form |
| Contract impact | Public baseline/candidate comparison, source and report exports | Paired specimens convey a controlled comparison |
| Quality checks | Recorded checks and live baseline/strict replay over 500 actual GitHub repositories | Calibration plate, separate benchmark specimen and exact failure evidence |
| Capture history | Filter and inspect capture sequence, import actual records as operator | Stacked strata establish sequence |
| Quarantine | Review and recheck failures with operator boundary | Isolated amber specimen reflects containment |
| Versions | Compare retained capture records | Parallel engraved studies show two revisions |
| Lineage | Source, immutable capture, checks and publication trail | Branch geometry supports provenance |
| Incidents | Inspect and add private investigation notes | A fault plate and legible notes surface |
| Recovery | Revalidate and select recovery reference with operator access | Dendrochronology reflects return to a retained reference |
| AI investigator | Token-free bounded public evidence inquiry, source citations and quotas | Prism plate leads into a calm prompt form |
| Connections | GitHub, PostgreSQL, Gemini and operator status | Root junction drawing connects the four integration descriptions |
| Settings | Workspace scope, access and API links | Ruler and plate alignment motif anchors compact settings |

The current serif and ivory theme gives DataGuard a distinct foundation. Repeated text-only headings, flat panels, small utility copy, and a simple top border make routes feel similar. The shell has keyboard focus, a skip link and a reduced-motion rule. Forms, headings and tables already render as native elements. There are no atmospheric image assets. Existing responsive rules, drawer focus behavior, history navigation and error messages are the starting point.

## Boundaries and design plan

The console's operator bearer token stays in tab memory. Authorization runs before body parsing on protected mutations. Public AI has separate scope, quotas and origin checks. The 500-repository benchmark uses fixed replay policies and a pinned data artifact. These paths, the PostgreSQL persistence layer and the existing environment configuration remain the basis for acceptance. Add only allowlisted same-origin static artwork and presentational behavior around the routes. No content security policy relaxation is needed.

Trickee's reference contributes clear heading hierarchy, an artwork-led reading direction and a stable primary action. Shunya Chakra contributes an artwork focal point and distinct chapters followed by quieter functional forms. The generated DataGuard board translates these into an ivory field journal, forest navigation, chartreuse actions, registration marks and original engraved botanical or geological specimens. The board's illustrative dataset and navigation are visual references only. Existing app workflows and actual records determine the live copy and evidence.

Use Instrument Serif for display headings and Manrope for controls and data. Keep ink on pale paper, forest on the navigation and ledger, chartreuse on active states, and warm brass for fine marks. Stage a compact chapter masthead on each route, with a forest illustration and a ginkgo plate framing the overview. Use the existing heading, panel, table and form structure. Artwork metadata, loading behavior and placement are covered by the manifest. Use native scroll, short entry motion, intersection-triggered panel movement and a small progress rule. Reduced motion skips animations and keeps the same layout.

Acceptance requires all 14 routes and critical public workflows to work, at least 20 distinct deployed and integrated original artworks, responsive content without document overflow, reduced motion and usable keyboard controls, passing existing tests, successful production deployment and direct canonical smoke checks. Record measured Lighthouse results from the project-wide verification pass.

## Implementation and fidelity review

The overview opens on a warm ivory cover with the approved headline, a chartreuse underline and controls that lead to the actual quality and source workflows. The forest engraving gives the eye a vertical frame and the ginkgo plate balances it on the right. At mobile widths, the plates sit below the copy and actions. Forest navigation and a chartreuse active state remain visible when the mobile menu opens. The real stored ledger replaces the concept board's illustrative records. The original export and investigator links sit below the ledger. [Production overview](../evidence/field-journal-production-overview.jpg)

Each of the 14 routes has an individually composed chapter plate. Eight additional artwork placements accompany the overview landscape, audit ledger, provenance rail, benchmark, impact source, lineage flow, recovery steps and investigator grounding. The 22 original SVGs total approximately 481 KB uncompressed and 74 KB when individually gzip-compressed locally. Each page preloads its own lead plate and lazy-loads the secondary plates. The two self-hosted fonts remain in WOFF2. Artwork uses empty alt text because the visible interface already explains each workflow. [Artwork manifest](../dataguard/archive-manifest.json) · [Original illustration source](../scripts/create_field_journal_art.py)

The motion system uses short page entrances, one-time section reveals, a native scroll-progress rule, small plate drift and a foil sweep on hover. It adds no animation library. The app renders readable content before motion runs. Reduced motion cancels the in-flight entry effects and disables scroll-linked effects and smooth scrolling. Browser testing found that parallel static requests could occupy the four API work slots. Known static files now use a separate 16-slot pool while API capacity and early authorization remain bounded. Testing also found overflowing breadcrumb actions at 320 px. The compact toolbar now keeps the route label readable and the actions within the viewport.

## Release verification

The local Playwright check passed all 70 combinations of 14 routes at 320, 390, 820, 1366 and 1920 px. All 22 illustrations were visible and decoded across the route set. The check also exercised the baseline and strict benchmark, contract impact, browser history, mobile-menu Escape and focus restoration, scroll progress and reduced motion. The PostgreSQL-enabled suite passed all 196 tests. After the final artwork and motion pass, 20 focused asset and boundary tests passed. JavaScript syntax, the existing Node tests and Ruff checks passed. [Browser verification script](../scripts/verify_field_journal.cjs) · [Local browser results](../evidence/field-journal-browser-local.json)

The existing Vercel project built and promoted deployment `dpl_4Upo7Zsfnet5w691TQeMitY3nwcG` from runtime commit `2c0a6542dcfe`. The staged URL required Vercel SSO, so the functional preview was tested locally before promotion. The canonical URL resolved to the Ready deployment. Direct HTTPS checks confirmed all 14 shells, the 22 source-matching asset digests, both fonts, readiness, the public impact result and the existing 500-repository evidence. The browser confirmed the published baseline and quarantined strict result with 96 missing license metadata and 177 archived repositories. The workspace before-and-after comparison was equal and an unauthorized upload returned 401. [Production HTTP proof](../evidence/field-journal-production.json)

An independent production browser check covered overview, datasets, checks and impact at 390 and 1366 px without console errors or horizontal overflow. A separate concurrent run encountered one HTTP 500 on overview. The deployment log recorded `Application exited with code 1` at 03:40:59 UTC with no traceback or causal error. Four subsequent overview requests and four readiness requests returned 200. The intermittent runtime exit remains unexplained. [Production browser results](../evidence/field-journal-browser-production.json) · [HTTP and runtime observations](../evidence/field-journal-production.json)

Mobile Lighthouse on the canonical overview recorded **94 Performance, 100 Accessibility, 100 Best Practices and 100 SEO** with simulated throttling. Lab LCP was 1.66 s, TBT was 32 ms and CLS was 0.1204. The lab layout shift remains an improvement opportunity. Field Core Web Vitals were not measured. [Lighthouse measurements](../evidence/field-journal-lighthouse.json)
