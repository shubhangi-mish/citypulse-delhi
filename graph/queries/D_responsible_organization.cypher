// Query D — Responsible / operating organisation for an infrastructure asset.
// Only explicit, sourced relationships count. Geographic containment is deliberately NOT used: in Delhi,
// MCD, NDMC, PWD, DJB, DMRC etc. can each control different assets inside the same area.
// Params: $asset_id
MATCH (a:InfrastructureAsset {asset_id:$asset_id})-[r:MAINTAINED_BY|OPERATED_BY|RESPONSIBLE_FOR]->(o:Organization)
OPTIONAL MATCH (s:Source {source_id: r.source_id})
RETURN o.organization_id AS organization_id, o.name AS organization, o.category AS category,
       type(r) AS relationship, r.basis AS basis, r.verification_status AS verification_status,
       s.name AS source_name, s.url AS source_url, s.license AS license
