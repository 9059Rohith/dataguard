# Published-version comparison

1. Prove directional added/removed/changed/unchanged counts with real published batches;
   test identity, period ownership, never-published states, authentication and immutability.
2. Implement bounded SQL aggregates over retained publication tables, published-attempt
   provenance and strict period/ID validation. Add authenticated GET and trusted CLI.
3. Document the contract, reviewer walkthrough, deployment scope and measured boundaries.
4. Run the full suite, PostgreSQL integration, lint/format and native Python 3.15 image
   checks without modifying running services. Record evidence, inspect diff and commit.
