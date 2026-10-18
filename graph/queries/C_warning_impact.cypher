// Query C — Warning impact paths.
// From a source-backed warning, traverse affected neighbourhoods/roads to upcoming events, open reports and
// known infrastructure. Every row carries the explicit path (node ids + relationship types) as evidence.
// Params: $warning_id, $now_ms
MATCH (w:Warning {warning_id:$warning_id})-[:AFFECTS]->(n:Neighborhood)<-[:LOCATED_IN]-(e:Event)
WHERE e.end_time >= $now_ms AND e.status <> 'cancelled'
RETURN 'event' AS impact_type, e.event_id AS entity_id, e.title AS title,
       [w.warning_id, n.neighborhood_id, e.event_id] AS path_ids, ['AFFECTS', 'LOCATED_IN'] AS path_rels,
       n.name AS via
UNION ALL
MATCH (w:Warning {warning_id:$warning_id})-[:AFFECTS]->(rd:Road)<-[:ACCESSIBLE_VIA]-(v:Venue)<-[:HOSTED_AT]-(e:Event)
WHERE e.end_time >= $now_ms AND e.status <> 'cancelled'
RETURN 'event' AS impact_type, e.event_id AS entity_id, e.title AS title,
       [w.warning_id, rd.road_id, v.venue_id, e.event_id] AS path_ids,
       ['AFFECTS', 'ACCESSIBLE_VIA', 'HOSTED_AT'] AS path_rels, rd.name AS via
UNION ALL
MATCH (w:Warning {warning_id:$warning_id})-[:AFFECTS]->(n:Neighborhood)<-[:LOCATED_IN]-(i:Issue)
WHERE i.status <> 'closed'
RETURN 'issue' AS impact_type, i.issue_id AS entity_id, i.title AS title,
       [w.warning_id, n.neighborhood_id, i.issue_id] AS path_ids, ['AFFECTS', 'LOCATED_IN'] AS path_rels,
       n.name AS via
UNION ALL
MATCH (w:Warning {warning_id:$warning_id})-[:AFFECTS]->(n:Neighborhood)<-[:LOCATED_IN]-(a:InfrastructureAsset)
RETURN 'asset' AS impact_type, a.asset_id AS entity_id, a.name AS title,
       [w.warning_id, n.neighborhood_id, a.asset_id] AS path_ids, ['AFFECTS', 'LOCATED_IN'] AS path_rels,
       n.name AS via
