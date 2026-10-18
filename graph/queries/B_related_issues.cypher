// Query B — Related issues and duplicate candidates.
// Ranks other recent reports by shared graph context: same category, same OSM road, shared nearby
// infrastructure asset, same neighbourhood, and physical proximity. Returns the shared entities as evidence.
// Params: $issue_id, $radius_m, $since_ms
MATCH (i:Issue {issue_id:$issue_id})
MATCH (o:Issue)
WHERE o.issue_id <> i.issue_id
  AND o.created_at > $since_ms
  AND distance(o.location, i.location) < $radius_m
OPTIONAL MATCH (i)-[:ON_ROAD]->(rd:Road)<-[:ON_ROAD]-(o)
OPTIONAL MATCH (i)-[:CONCERNS|NEAR]->(a:InfrastructureAsset)<-[:CONCERNS|NEAR]-(o)
OPTIONAL MATCH (i)-[:LOCATED_IN]->(n:Neighborhood)<-[:LOCATED_IN]-(o)
WITH i, o, distance(o.location, i.location) AS d,
     collect(DISTINCT {id: rd.road_id, name: rd.name}) AS roads,
     collect(DISTINCT {id: a.asset_id, name: a.name}) AS assets,
     collect(DISTINCT {id: n.neighborhood_id, name: n.name}) AS nbhs
WITH i, o, d,
     [x IN roads WHERE x.id IS NOT NULL] AS shared_roads,
     [x IN assets WHERE x.id IS NOT NULL] AS shared_assets,
     [x IN nbhs WHERE x.id IS NOT NULL] AS shared_neighborhoods
WITH i, o, d, shared_roads, shared_assets, shared_neighborhoods,
     (CASE WHEN o.category = i.category THEN 0.4 ELSE 0.0 END) +
     (CASE WHEN size(shared_roads) > 0 THEN 0.25 ELSE 0.0 END) +
     (CASE WHEN size(shared_assets) > 0 THEN 0.15 ELSE 0.0 END) +
     (CASE WHEN size(shared_neighborhoods) > 0 THEN 0.1 ELSE 0.0 END) +
     (CASE WHEN d < 250 THEN 0.1 ELSE 0.0 END) AS score
WHERE score >= 0.3
RETURN o.issue_id AS issue_id, o.title AS title, o.category AS category, o.status AS status,
       o.support_count AS support_count, o.created_at AS created_at, round(d) AS distance_m,
       o.category = i.category AS same_category, shared_roads, shared_assets, shared_neighborhoods, score
ORDER BY score DESC, distance_m ASC
LIMIT 20
