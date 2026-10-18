// Query G — Replacement-performer candidates for an event whose booked performer cancelled.
// Multi-hop evidence per candidate: shares a discipline (Profession) with the cancelled performer, lives within
// the search radius, belongs to the same artistic family (music / visual / performance) as the cancelled performer, explicitly opted in to fill-in gigs, is not already featured, has no pending invitation and has not declined, and — via a
// (Event)-[:FEATURES]->(Resident) traversal — has no confirmed booking that overlaps this event's time window.
// Names are returned only for residents who opted into a public, named profile.
// Params: $event_id, $radius_m
MATCH (e:Event {event_id:$event_id})
OPTIONAL MATCH (e)-[:FEATURES {status:'cancelled'}]->(:Resident)-[:PRACTICES]->(gp:Profession)
WITH e, collect(DISTINCT gp.profession_id) AS gone_professions, collect(DISTINCT gp.family) AS gone_families
MATCH (c:Resident)-[:PRACTICES]->(p:Profession {category:'artist'})
WHERE c.open_to_gigs = true
  AND distance(c.location, e.location) < $radius_m
  AND NOT (e)-[:FEATURES]->(c)
  AND NOT (e)-[:INVITED {status:'pending'}]->(c)
  AND NOT (e)-[:INVITED {status:'declined'}]->(c)   // closed invitations (position was filled) may be re-invited in a later round
OPTIONAL MATCH (c)<-[:FEATURES {status:'confirmed'}]-(o:Event)
WHERE o.event_id <> e.event_id AND o.start_time < e.end_time AND o.end_time > e.start_time
WITH e, c, p, gone_professions, gone_families,
     collect(DISTINCT {id: o.event_id, title: o.title, start: o.start_time, end: o.end_time}) AS clashes
OPTIONAL MATCH (c)-[:LIVES_IN]->(n:Neighborhood)
RETURN c.resident_id AS resident_id,
       CASE WHEN c.display_name_opt_in = true AND c.public_visibility = 'public' THEN c.name ELSE null END AS display_name,
       p.name AS profession, p.profession_id AS profession_id,
       p.profession_id IN gone_professions AS same_discipline,
       p.family IN gone_families AS same_family, p.family AS family,
       distance(c.location, e.location) AS distance_m,
       n.name AS neighborhood,
       [x IN clashes WHERE x.id IS NOT NULL] AS clashes
