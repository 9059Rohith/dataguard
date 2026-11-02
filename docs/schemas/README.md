# OpenLineage validation fixtures

Unmodified official schemas retrieved 2026-11-02:

- DataQualityAssertionsDatasetFacet.json: https://openlineage.io/spec/facets/1-1-0/DataQualityAssertionsDatasetFacet.json
- OpenLineage.json: https://openlineage.io/spec/2-0-2/OpenLineage.json

These fixtures enable offline Draft 2020-12 validation of the exported **facet**, including
its inherited producer/schema URL requirements. Tests target the facet definition explicitly,
so a wrong top-level object cannot pass an unconstrained wrapper. A negative control changes
success to a string and must fail. Disabled rules are omitted from the facet rather than
misrepresented as executed passing assertions. The full comparison report retains them.

Upstream project: https://github.com/OpenLineage/OpenLineage (Apache License 2.0).
