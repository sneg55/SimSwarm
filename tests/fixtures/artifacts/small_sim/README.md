# Small-sim artifact fixtures

These are **minimal structurally-valid** artifact stand-ins used by the report
tools + runner tests. They are NOT real production sim data — the SaaS rule
`feedback_no_fake_data` allows test mocks but prefers real data where possible.

**Action:** Replace with real small-tier MinIO artifacts when a production
sim is available. See `docs/superpowers/plans/2026-04-13-external-llm-report.md`
Task 5 for instructions.

Files must match the JSON shape emitted by `simswarm.extractor` / `simswarm.adapter`.
