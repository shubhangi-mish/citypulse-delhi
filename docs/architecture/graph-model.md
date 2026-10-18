# Graph model

FalkorDB graph `citypulse`. IDs are prefixed by label (`iss_`, `evt_`, `wrn_`, `nbh_`, `ast_`, `road_`, `org_`, `area_`, `case_`, `act_`, `dec_`, `mem_`, `src_`, `dis_`, `crd_`, `res_`, `ven_`) so any entity resolves with one indexed lookup (`app/graph/model.py`). Timestamps are epoch milliseconds. Locations are FalkorDB `point`s.

## Nodes

| Label | Key properties | Origin |
|---|---|---|
| Resident | resident_id, name, email\*, address\*, latitude\*, longitude\*, location\*, public_visibility, display_name_opt_in, area_updates_opt_in | Quick profile (\* private, never in public responses) |
| Neighborhood | neighborhood_id, name, administrative_type, osm_ref, location, source_id | OSM `place=suburb|neighbourhood|quarter` nodes |
| AdministrativeArea | area_id, name, type (`union_territory`/`district`), osm_ref | OSM admin_level 4 / 5 relations |
| InfrastructureAsset | asset_id, asset_type, name, location, osm_ref, verification_status | OSM metro stations, hospitals, police, fire stations, public toilets, named parks |
| Organization | organization_id, name, category, verification_status | OSM `operator` tags, or organiser-named groups |
| Road | road_id, name, road_class, osm_ref | Nominatim reverse lookup at submission time |
| Venue | venue_id, name, address, location | Event submissions |
| Issue | issue_id, title, description, category, status, location (private-precision), public_lat/lng, public_location_precision, support_count, verification_status | Resident submissions |
| Event | event_id, title, description, category, start/end_time, status, location, public_lat/lng, organizer_name, organizer_contact\*, source_type, organizer_attestation, verification_status | Resident/organiser submissions |
| Warning | warning_id, external_id, title, warning_type, severity, urgency, certainty, issuing_authority, issued/effective/expires_at, area_description, instruction, source_url, source_name, license, published_at, ingested_at, last_verified_at, verification_status | NDMA SACHET CAP |
| Source | source_id, name, url, license, source_type, access_method, retrieved_at | `data/manifests/sources.json` |
| Discussion | discussion_id, body, kind (`comment`/`history`/`organizer_update`), created_at | Residents / system history |
| CoordinationCase | case_id, title, case_type, status (`proposed`/`open`/`in_progress`/`resolved`/`closed`), assigned_to | Coordinators or Coordination Agent |
| CoordinationAction | action_id, action_type, description, status (`proposed`→`approved`→`executed`→`completed`/`rejected`), payload (JSON), outcome, outcome_success | Agents/coordinators |
| Coordinator | coordinator_id, display_name | Authenticated operator |
| AgentDecision | decision_id, agent_name, decision_type, rationale, model_name, evidence_strength, review_status, run_id, trace (JSON: tool calls, query ids, paths) | Agents |
| AgentMemory | memory_id, memory_type, summary, valid_until, source_reference, written_by | Memory Agent on recorded outcome |

## Relationships

| Relationship | Meaning | Provenance class |
|---|---|---|
| Resident LIVES_IN Neighborhood | home area (`basis`: resident_selected / nearest_osm_place) | community (hidden in public explorer) |
| AdministrativeArea CONTAINS Neighborhood/Area | OSM boundary membership | verified |
| Resident REPORTED Issue `{anonymous}` | authorship | community |
| Resident SUPPORTS / FOLLOWS Issue | "I'm affected too" (idempotent MERGE) / following | community |
| Issue LOCATED_IN Neighborhood | nearest OSM place within 4 km | rule-inferred |
| Issue ON_ROAD Road · Venue ACCESSIBLE_VIA Road | Nominatim reverse geocode | rule-inferred |
| Issue NEAR InfrastructureAsset `{distance_m}` | within 300 m | rule-inferred |
| Issue CONCERNS InfrastructureAsset | chosen by the reporter | community |
| Issue POSSIBLY_DUPLICATES Issue `{score, reasons, query_id, confirmed}` | Query B ≥ 0.65 same category, or coordinator-linked | rule-inferred / coordination |
| InfrastructureAsset OPERATED_BY Organization | explicit OSM operator tag only | community (OSM) |
| InfrastructureAsset LOCATED_IN Neighborhood | nearest OSM place | rule-inferred |
| Resident SUBMITTED / PARTICIPATES_IN `{role}` Event | organiser / interested·going·volunteer | community |
| Event HOSTED_AT Venue · Event ORGANIZED_BY Organization · Event LOCATED_IN Neighborhood | event structure | community / rule-inferred |
| Warning AFFECTS Neighborhood/AdministrativeArea `{basis}` | CAP areaDesc → OSM district/neighbourhood name match | verified (official area) |
| Warning MAY_IMPACT Event | warning window overlaps event and area/road matches | rule-inferred |
| X DERIVED_FROM Source | record provenance | verified |
| Resident COMMENTED_ON Discussion ABOUT Issue/Event | discussion | community |
| CoordinationCase ADDRESSES Issue · CoordinationAction PART_OF CoordinationCase · Resident PARTICIPATES_IN CoordinationCase | coordination | coordination |
| Coordinator APPROVED CoordinationAction | human approval | coordination |
| AgentDecision CONSIDERED `{role}` / BASED_ON Source / USED_MEMORY AgentMemory / PRODUCED CoordinationAction / INFORMED AgentDecision | agent trace and hand-off chain | AI |
| AgentMemory SUMMARIZES CoordinationCase / RECORDS CoordinationAction / LEARNED_FROM AgentDecision | persistent memory | AI |

**Not modelled on purpose:** maintenance or jurisdiction edges derived from geography. In Delhi, MCD, NDMC, PWD, DJB, DMRC and others can each control different assets inside the same area, so responsibility only comes from an explicit sourced edge.
