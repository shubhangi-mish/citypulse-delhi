// Query H — Persistent memory for event disruptions.
// Earlier performer-cancellation cases (and what resolved them), reached through
// AgentMemory-[:SUMMARIZES]->CoordinationCase-[:ADDRESSES]->Event. Used by the Memory Agent so that what worked
// before (e.g. a same-discipline artist from a nearby neighbourhood) informs the next recommendation.
// Params: $event_id (kept for callers; resolved cases from any event, including this one, are returned)
MATCH (m:AgentMemory)-[:SUMMARIZES]->(c:CoordinationCase {case_type:'event_disruption'})-[:ADDRESSES]->(pe:Event)
WHERE c.status = 'resolved'   // only cases that were actually solved teach the agents; includes earlier rounds on this same event
OPTIONAL MATCH (a:CoordinationAction {action_type:'invite_replacement'})-[:PART_OF]->(c)
OPTIONAL MATCH (pe)-[f:FEATURES {role:'replacement', status:'confirmed'}]->(rep:Resident)
OPTIONAL MATCH (rep)-[:PRACTICES]->(pr:Profession)
RETURN m.memory_id AS memory_id, m.summary AS summary, c.case_id AS case_id, pe.title AS prior_event,
       a.outcome AS outcome, a.outcome_success AS outcome_success, pr.name AS replacement_profession,
       pr.profession_id AS replacement_profession_id
ORDER BY m.created_at DESC
LIMIT 5
