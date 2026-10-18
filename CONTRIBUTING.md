# Contributing

- **Real data only.** Never seed invented residents, reports, events or alerts into a shared graph. Tests use isolated graphs (`citypulse_test`, `citypulse_e2e`).
- **Graph first.** New city/coordination features belong in FalkorDB. Put reusable queries in `graph/queries/` and load them with `app.graph.queries.Q`.
- **Privacy.** Never `RETURN n` for a node to a client. Pass properties through `public_props()`, and add new public fields to `PUBLIC_PROPS` deliberately.
- **No silent fallbacks.** If FalkorDB fails, let `GraphUnavailable` surface as a 503.
- **Provenance.** New external sources go in `data/manifests/sources.json` with licence and access method, and their records get `DERIVED_FROM` a `Source`.
- Before a PR: `cd apps/api && uv run pytest` and `cd apps/web && npx tsc --noEmit && npm run build`.
- Never commit `.env`, personal data, or `data/cache/`.
