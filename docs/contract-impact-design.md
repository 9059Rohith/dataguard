# Public Contract Impact Workbench

The workbench answers: which repositories would a proposed source contract reject, and why?
Both policies run against the exact same immutable public GitHub capture and an explicit UTC
analysis clock. A capture selector connects the experiment to dataset evidence. No experiments
persist, change contracts, reserve AI quota, contact a model, or admit private uploads.

The fixed declarative vocabulary covers required metadata, accepted source languages, archived
status, source push freshness, minimum stars, and maximum open issues. Empty optional limits
disable that rule. Defaults require identity and nonnegative stars, leaving optional selection
criteria disabled. Rules are user-authored acceptance criteria, never repository quality scores.
GitHub metadata does not establish software security or license suitability; open issues includes
pull requests in this source field. Future timestamps fail rather than receiving a zero age.

Results include accepted/rejected transitions, each repository's exact observed and expected
values, per-rule failure witnesses, content hash, clock, and policy hashes. JSON report and an
OpenLineage dataQualityAssertions dataset facet can be downloaded separately. The facet uses
the official 1-1-0 schema, with a vendored core reference, validated offline in tests. It is a
dataset facet, not a complete lineage event or an integration with a lineage server.

The page extends the existing ivory/forest editorial interface with paired policy sheets,
an acceptance transition ribbon, and expandable evidence rows. Inputs remain usable on mobile.
Dirty inputs explicitly invalidate the displayed report until comparison is rerun.

## Primary references (consulted 2026-11-02)

- https://docs.github.com/en/rest/repos/repos#get-a-repository — source field semantics.
- https://docs.github.com/en/rest/issues/issues#list-repository-issues — GitHub treats pull requests as issues in its REST model.
- https://openlineage.io/docs/1.53.0/spec/facets/dataset-facets/data_quality_assertions/ — assertions, success independent of severity, dataset scope.
- https://openlineage.io/spec/facets/1-1-0/DataQualityAssertionsDatasetFacet.json — actual current schema linked by those docs.
- https://openlineage.io/spec/2-0-2/OpenLineage.json — referenced core facet definition.

## Boundaries

Public POST /api/quality/contract-impact accepts at most 16 KiB, rejects unknown fields,
duplicate keys, nonfinite numbers, coercible booleans/numbers, and excessive lists. The global
four-request capacity guard applies. Only genuine public allowlisted captures with matching
content digests are eligible; unknown and private IDs share a 404. At most eight source rows
and six rules per policy bound work. Origin checks match the existing public investigator.
Existing authenticated writes and persistent AI limits stay unchanged.
