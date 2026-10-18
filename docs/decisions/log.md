# Technical decision log

Decisions marked **(review)** are ones the project owner should confirm.

| # | Date | Decision | Why |
|---|---|---|---|
| 1 | 2026-10-16 | Modular monolith: FastAPI + Next.js, FalkorDB + PostgreSQL via Docker Compose | Four-day window; fewest moving parts. |
| 2 | 2026-10-16 | FalkorDB is authoritative for the whole city/coordination/memory domain; PostgreSQL holds only sessions, operator sessions, audit, source runs and notifications | Makes the graph indispensable; avoids dual-writing the graph. |
| 3 | 2026-10-16 | Radius filtering with FalkorDB `distance()` on indexed points (not PostGIS) | Keeps spatial candidate selection and graph enrichment in one query; verified on FalkorDB 4.22. |
| 4 | 2026-10-16 | Canonical Cypher in `graph/queries/*.cypher`, loaded at runtime | Documentation can't drift from what runs. |
| 5 | 2026-10-16 | `exists((pattern))` avoided | On FalkorDB 4.22 it returns true for missing patterns; replaced by `size([(pattern) | 1]) > 0`, found by a failing test. |
| 6 | 2026-10-16 | Warnings from NDMA SACHET CAP, area matched by `areaDesc` text → OSM names | Official, public-domain feed. Polygon endpoint returns 403 to automated clients, so it is not used (no bypassing). |
| 7 | 2026-10-16 | Kept an alert only if its area resolves to Delhi entities | "IMD New Delhi" also issues alerts for neighbouring states. |
| 8 | 2026-10-17 | No external events ingested. Tested on 2026-10-17: Delhi Tourism (no robots.txt, events page 404, no feed), Incredible India, data.gov.in (no feed), IGNCA (403), Wikidata (0 upcoming Delhi events), Kamani Auditorium and India Habitat Centre (no iCal/JSON-LD/events API found). Eventbrite public search is discontinued; PredictHQ is paid; Insider/BookMyShow/District only offer scraping, which their terms restrict. | No official or permitted machine-readable source for Delhi events exists, and CityPulse will not scrape. Events come from genuine resident/organiser submissions. **(review)** |
| 9 | 2026-10-16 | `OPERATED_BY` only from explicit OSM operator tags, labelled community-sourced; no responsibility from geography | Jurisdiction in Delhi overlaps; avoid invented responsibility. |
| 10 | 2026-10-16 | New status `RULE_INFERRED` alongside `AI_INFERRED` | Deterministic geo/graph rules shouldn't be labelled as AI. |
| 11 | 2026-10-16 | Quick profile never looks up by email; each submission creates a new profile | Without OTP, email lookup would let anyone claim an account. Trade-off: profiles are browser-bound. **(review)** |
| 12 | 2026-10-16 | Agents run deterministic graph-only by default; LLM optional, used only for wording | Works with no API key; LLM never decides facts; decisions record which mode ran. **(review: choose OpenAI or Gemini for the demo)** |
| 13 | 2026-10-16 | Agent cases start as `proposed` and are hidden from the public until a coordinator approves an action | Human approval for consequential actions; no unreviewed agent output reaches residents. |
| 14 | 2026-10-16 | Corroboration threshold = 3 residents, duplicate threshold = 0.65 | Simple, explainable defaults. **(review)** |
| 15 | 2026-10-16 | Web on port 3100, Postgres on 55432 | 3000 was in use on the dev machine; 5433 is in a Windows-reserved range. |
| 17 | 2026-10-18 | Added a synthetic demo scenario (7 fictional personas, `demo=true`, removable) | Requested by the project owner to show people/professions/complaints/events/solutions and real agent actions. Rule 6 allows synthetic data. Kept out of the real-data story by flags, labels and a one-click removal. **(review)** |
| 18 | 2026-10-18 | Agents may act without a coordinator click only when the event organiser explicitly enabled autopilot; otherwise they propose | Keeps human approval as the default while letting agents take real, authorised actions. Recorded as an AUTHORIZED edge. **(review)** |
| 16 | 2026-10-16 | Mapbox for display/search; stored resident location is the point the resident confirms | Mapbox temporary geocoding results shouldn't be stored as data; production should use Mapbox permanent geocoding if needed. |
