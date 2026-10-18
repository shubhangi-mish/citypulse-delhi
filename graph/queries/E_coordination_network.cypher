// Query E — Coordination network around an issue.
// Supporters, publicly-named participants, linked duplicate reports, coordination cases and their actions.
// Names are only returned for residents who opted into public attribution.
// Params: $issue_id
MATCH (i:Issue {issue_id:$issue_id})
OPTIONAL MATCH (i)<-[:SUPPORTS]-(sup:Resident)
WITH i, count(DISTINCT sup) AS supporter_count,
     [x IN collect(DISTINCT CASE WHEN sup.public_visibility = 'public' AND sup.display_name_opt_in
                                 THEN sup.name END) WHERE x IS NOT NULL] AS named_supporters
OPTIONAL MATCH (i)<-[:FOLLOWS]-(f:Resident)
WITH i, supporter_count, named_supporters, count(DISTINCT f) AS follower_count
OPTIONAL MATCH (i)-[dup:POSSIBLY_DUPLICATES]-(other:Issue)
WITH i, supporter_count, named_supporters, follower_count,
     [x IN collect(DISTINCT {issue_id: other.issue_id, title: other.title, score: dup.score,
                             confirmed: coalesce(dup.confirmed, false)}) WHERE x.issue_id IS NOT NULL] AS linked
OPTIONAL MATCH (c:CoordinationCase)-[:ADDRESSES]->(i)
OPTIONAL MATCH (a:CoordinationAction)-[:PART_OF]->(c)
OPTIONAL MATCH (p:Resident)-[:PARTICIPATES_IN]->(c)
WITH i, supporter_count, named_supporters, follower_count, linked, c,
     collect(DISTINCT {action_id: a.action_id, action_type: a.action_type, status: a.status,
                       description: a.description, outcome: a.outcome}) AS actions,
     count(DISTINCT p) AS participants
RETURN supporter_count, named_supporters, follower_count, linked,
       [x IN collect(CASE WHEN c IS NULL THEN NULL ELSE
          {case_id: c.case_id, title: c.title, status: c.status, participants: participants,
           actions: [y IN actions WHERE y.action_id IS NOT NULL]} END) WHERE x IS NOT NULL] AS cases
