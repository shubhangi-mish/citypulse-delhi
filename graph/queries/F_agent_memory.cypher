// Query F — Persistent agent memory retrieval.
// For a new issue, find prior issues connected through the graph (confirmed/possible duplicates, the same
// OSM road, the same nearby asset, or the same neighbourhood with the same category), then the coordination
// cases that addressed them, the actions taken with their outcomes, approving coordinators, and the memory
// records the Memory Agent wrote. `via` explains WHY the prior case is relevant.
// Params: $issue_id
MATCH (i:Issue {issue_id:$issue_id})
MATCH route = (i)-[:POSSIBLY_DUPLICATES|ON_ROAD|CONCERNS|NEAR|LOCATED_IN*1..2]-(prior:Issue)
WHERE prior.issue_id <> i.issue_id
WITH i, prior, [r IN relationships(route) | type(r)] AS via, [x IN nodes(route) | coalesce(x.name, x.title)] AS hops
WHERE NOT 'LOCATED_IN' IN via OR prior.category = i.category
WITH i, prior, collect({via: via, hops: hops}) AS routes
MATCH (c:CoordinationCase)-[:ADDRESSES]->(prior)
OPTIONAL MATCH (m:AgentMemory)-[:SUMMARIZES]->(c)
OPTIONAL MATCH (a:CoordinationAction)-[:PART_OF]->(c)
OPTIONAL MATCH (a)<-[:APPROVED]-(crd:Coordinator)
WITH prior, routes, c,
     collect(DISTINCT {memory_id: m.memory_id, summary: m.summary, memory_type: m.memory_type,
                       created_at: m.created_at}) AS memories,
     collect(DISTINCT {action_id: a.action_id, action_type: a.action_type, status: a.status,
                       outcome: a.outcome, approved_by: crd.display_name}) AS actions
RETURN prior.issue_id AS prior_issue_id, prior.title AS prior_title, prior.status AS prior_status,
       routes, c.case_id AS case_id, c.title AS case_title, c.status AS case_status,
       [x IN memories WHERE x.memory_id IS NOT NULL] AS memories,
       [x IN actions WHERE x.action_id IS NOT NULL] AS actions
ORDER BY size([x IN memories WHERE x.memory_id IS NOT NULL]) DESC
LIMIT 10
