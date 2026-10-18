# Demo script (≈4 minutes)

Everything shown is real: OSM geography, the live SACHET feed state, and actions performed live in the app. Label any demo report as a test submission in its text.

**Before recording:** `docker compose up -d falkordb postgres`, API and web running, `.env` has a Mapbox token and an operator account. Use two browser profiles (Resident A, Resident B) and a third window for Command.

1. **The city graph (20 s).** Home → "The city graph today" card: 580 neighbourhoods, 2,983 assets, 14 areas, all from OpenStreetMap. Open `/about` to show the source manifest (what's ingested, what was evaluated and why not).
2. **Onboard A (30 s).** "Continue as a resident" → name, email, address → pin on the Mapbox map → nearest OSM neighbourhoods → continue. Point out: private by default, email never used to sign in.
3. **Report (30 s).** Report → Waterlogging → location → optionally pick a nearby metro station → submit. The confirmation shows it's now connected to a neighbourhood, an OSM road and related reports, and that nothing was filed with a department.
4. **Graph persistence (20 s).** "See connections": Resident (private) —REPORTED→ Issue —LOCATED_IN→ Neighbourhood ←CONTAINS— District; ON_ROAD, NEAR → asset —OPERATED_BY→ operator. Click edges to show provenance class and basis.
5. **Second resident (40 s).** In window B, onboard nearby → Around You → 1 km vs 3 km radius → the report appears → "I'm affected too". Back in A: notification bell, support count. Mention that nearby contributors only show opted-in public names.
6. **Command (60 s).** `/command` sign-in → Overview (real counts) → Incident queue → the report → **Run agents**. Walk through the four agents, explanation paths with query file names, evidence strength (not a probability), proposals. Approve "Request community verification" → executed (in-app notifications). Record an outcome → "Memory Agent wrote mem_…".
7. **Memory (40 s).** Restart the API (`Ctrl+C`, rerun uvicorn) and reload. City memory shows the record. Submit a second, related report as B → run agents → Memory panel shows the prior case reached via `ON_ROAD→ON_ROAD`, and the recommendation rationale starts "Memory: …". Agent activity → decision trace shows `USED_MEMORY` and the INFORMED hand-off chain.
8. **Warnings (20 s).** Warnings page: live SACHET state (if no Delhi alert is active, show the honest empty state and the source health page with last check time). If one is active, open it: official instruction verbatim, source link, graph-derived impact paths labelled as such.
9. **Resilience (10 s).** `docker compose stop falkordb` → reload Around You → "City graph unavailable" with no fallback data. Restart it.

Close: FalkorDB is the context the agents act on — the radius feed, duplicates, impact, responsibility and memory are all graph traversals.
