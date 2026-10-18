// Applied automatically at API startup by app/graph/schema.py (idempotent). Verified on FalkorDB 4.22.
// Stable IDs
CREATE INDEX FOR (n:Resident) ON (n.resident_id);
CREATE INDEX FOR (n:Neighborhood) ON (n.neighborhood_id);
CREATE INDEX FOR (n:AdministrativeArea) ON (n.area_id);
CREATE INDEX FOR (n:Organization) ON (n.organization_id);
CREATE INDEX FOR (n:InfrastructureAsset) ON (n.asset_id);
CREATE INDEX FOR (n:Road) ON (n.road_id);
CREATE INDEX FOR (n:Venue) ON (n.venue_id);
CREATE INDEX FOR (n:Event) ON (n.event_id);
CREATE INDEX FOR (n:Issue) ON (n.issue_id);
CREATE INDEX FOR (n:Warning) ON (n.warning_id);
CREATE INDEX FOR (n:Community) ON (n.community_id);
CREATE INDEX FOR (n:CoordinationCase) ON (n.case_id);
CREATE INDEX FOR (n:CoordinationAction) ON (n.action_id);
CREATE INDEX FOR (n:AgentDecision) ON (n.decision_id);
CREATE INDEX FOR (n:AgentMemory) ON (n.memory_id);
CREATE INDEX FOR (n:Source) ON (n.source_id);
CREATE INDEX FOR (n:Discussion) ON (n.discussion_id);
CREATE INDEX FOR (n:Coordinator) ON (n.coordinator_id);
// Filters and time
CREATE INDEX FOR (n:Issue) ON (n.status);
CREATE INDEX FOR (n:Issue) ON (n.created_at);
CREATE INDEX FOR (n:Issue) ON (n.category);
CREATE INDEX FOR (n:Event) ON (n.status);
CREATE INDEX FOR (n:Event) ON (n.start_time);
CREATE INDEX FOR (n:Warning) ON (n.expires_at);
CREATE INDEX FOR (n:Warning) ON (n.external_id);
CREATE INDEX FOR (n:CoordinationCase) ON (n.status);
CREATE INDEX FOR (n:CoordinationAction) ON (n.status);
CREATE INDEX FOR (n:Road) ON (n.osm_ref);
CREATE INDEX FOR (n:InfrastructureAsset) ON (n.osm_ref);
CREATE INDEX FOR (n:Neighborhood) ON (n.osm_ref);
CREATE INDEX FOR (n:Organization) ON (n.name);
// Geospatial point indexes used by distance() filters
CREATE INDEX FOR (n:Issue) ON (n.location);
CREATE INDEX FOR (n:Event) ON (n.location);
CREATE INDEX FOR (n:Neighborhood) ON (n.location);
CREATE INDEX FOR (n:InfrastructureAsset) ON (n.location);
CREATE INDEX FOR (n:Venue) ON (n.location);
CREATE INDEX FOR (n:Resident) ON (n.location);
