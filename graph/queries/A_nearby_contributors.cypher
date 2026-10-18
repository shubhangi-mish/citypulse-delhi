// Query A — Nearby contributors and their public activity.
// Residents who contributed to reports/events inside a radius, restricted to people who opted into a
// public, named profile. Anonymous reports are excluded. Output never includes email, address or location.
// Params: $lat, $lng, $radius_m
MATCH (i:Issue)
WHERE distance(i.location, point({latitude:$lat, longitude:$lng})) < $radius_m
MATCH (r:Resident)-[c:REPORTED|SUPPORTS|FOLLOWS]->(i)
WHERE r.public_visibility = 'public' AND r.display_name_opt_in = true AND coalesce(c.anonymous, false) = false
OPTIONAL MATCH (r)-[:LIVES_IN]->(n:Neighborhood)
RETURN r.resident_id AS resident_id, r.name AS display_name, n.name AS neighborhood,
       type(c) AS contribution, 'Issue' AS kind, i.issue_id AS entity_id, i.title AS title, i.created_at AS at
UNION ALL
MATCH (e:Event)
WHERE distance(e.location, point({latitude:$lat, longitude:$lng})) < $radius_m
MATCH (r:Resident)-[c:SUBMITTED|PARTICIPATES_IN]->(e)
WHERE r.public_visibility = 'public' AND r.display_name_opt_in = true
OPTIONAL MATCH (r)-[:LIVES_IN]->(n:Neighborhood)
RETURN r.resident_id AS resident_id, r.name AS display_name, n.name AS neighborhood,
       type(c) AS contribution, 'Event' AS kind, e.event_id AS entity_id, e.title AS title, e.created_at AS at
