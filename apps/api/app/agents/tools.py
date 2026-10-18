"""Typed graph tools used by the agents. Each tool is one parameterised Cypher query against FalkorDB and
returns a pydantic model plus the query id, so every agent conclusion can be traced to its query."""

from pydantic import BaseModel

from app.graph.client import GraphClient
from app.graph.model import now_ms
from app.graph.queries import Q, query_id


class ToolResult(BaseModel):
    tool: str
    query_id: str
    rows: list[dict]


def issue_context(graph: GraphClient, issue_id: str) -> ToolResult:
    rows = graph.query(
        """
        MATCH (i:Issue {issue_id:$id})
        OPTIONAL MATCH (i)-[:LOCATED_IN]->(n:Neighborhood)
        OPTIONAL MATCH (d:AdministrativeArea)-[:CONTAINS]->(n)
        OPTIONAL MATCH (i)-[:ON_ROAD]->(rd:Road)
        OPTIONAL MATCH (i)-[ar:NEAR|CONCERNS]->(a:InfrastructureAsset)
        OPTIONAL MATCH (a)-[:DERIVED_FROM]->(s:Source)
        RETURN i.issue_id AS issue_id, i.title AS title, i.description AS description, i.category AS category,
               i.status AS status, i.support_count AS support_count, i.created_at AS created_at,
               n.neighborhood_id AS neighborhood_id, n.name AS neighborhood, d.name AS district,
               rd.road_id AS road_id, rd.name AS road,
               collect(DISTINCT {asset_id: a.asset_id, name: a.name, asset_type: a.asset_type,
                                 relationship: type(ar), distance_m: ar.distance_m}) AS assets,
               collect(DISTINCT s.source_id) AS sources
        """, {"id": issue_id}, readonly=True)
    for r in rows:
        r["assets"] = [a for a in r["assets"] if a["asset_id"]]
        r["sources"] = [s for s in r["sources"] if s]
    return ToolResult(tool="issue_context", query_id="agents/tools.py#issue_context", rows=rows)


def related_issues(graph: GraphClient, issue_id: str) -> ToolResult:
    rows = graph.query(Q("related_issues"),
                       {"issue_id": issue_id, "radius_m": 1500, "since_ms": now_ms() - 120 * 86400 * 1000},
                       readonly=True)
    return ToolResult(tool="related_issues", query_id=query_id("related_issues"), rows=rows)


def responsible_organizations(graph: GraphClient, asset_ids: list[str]) -> ToolResult:
    rows = []
    for aid in asset_ids:
        for r in graph.query(Q("responsible_organization"), {"asset_id": aid}, readonly=True):
            rows.append({"asset_id": aid, **r})
    return ToolResult(tool="responsible_organizations", query_id=query_id("responsible_organization"), rows=rows)


def active_warnings(graph: GraphClient, issue_id: str) -> ToolResult:
    rows = graph.query(
        """
        MATCH (i:Issue {issue_id:$id})-[:LOCATED_IN]->(n:Neighborhood)<-[r:AFFECTS]-(w:Warning)
        WHERE w.expires_at > $now
        RETURN DISTINCT w.warning_id AS warning_id, w.title AS title, w.severity AS severity,
               w.issuing_authority AS issuing_authority, w.source_url AS source_url, n.name AS via,
               r.basis AS basis
        """, {"id": issue_id, "now": now_ms()}, readonly=True)
    return ToolResult(tool="active_warnings", query_id="agents/tools.py#active_warnings", rows=rows)


def upcoming_events_nearby(graph: GraphClient, issue_id: str, radius_m: int = 2000, days: int = 14) -> ToolResult:
    rows = graph.query(
        """
        MATCH (i:Issue {issue_id:$id}), (e:Event)
        WHERE e.end_time >= $now AND e.start_time <= $until AND e.status <> 'cancelled'
          AND distance(e.location, i.location) < $radius
        OPTIONAL MATCH (e)-[:HOSTED_AT]->(v:Venue)
        OPTIONAL MATCH (v)-[:ACCESSIBLE_VIA]->(rd:Road)<-[:ON_ROAD]-(i)
        OPTIONAL MATCH (p:Resident)-[:PARTICIPATES_IN]->(e)
        RETURN e.event_id AS event_id, e.title AS title, e.start_time AS start_time, v.name AS venue,
               round(distance(e.location, i.location)) AS distance_m, rd.name AS shared_road,
               count(DISTINCT p) AS participants
        ORDER BY e.start_time ASC
        """, {"id": issue_id, "now": now_ms(), "until": now_ms() + days * 86400 * 1000, "radius": radius_m},
        readonly=True)
    return ToolResult(tool="upcoming_events_nearby", query_id="agents/tools.py#upcoming_events_nearby", rows=rows)


def coordination_network(graph: GraphClient, issue_id: str) -> ToolResult:
    rows = graph.query(Q("coordination_network"), {"issue_id": issue_id}, readonly=True)
    return ToolResult(tool="coordination_network", query_id=query_id("coordination_network"), rows=rows)


def prior_memory(graph: GraphClient, issue_id: str) -> ToolResult:
    rows = graph.query(Q("agent_memory"), {"issue_id": issue_id}, readonly=True)
    return ToolResult(tool="prior_memory", query_id=query_id("agent_memory"), rows=rows)


def recurrence(graph: GraphClient, issue_id: str, days: int = 365) -> ToolResult:
    rows = graph.query(
        """
        MATCH (i:Issue {issue_id:$id})
        OPTIONAL MATCH (i)-[:ON_ROAD]->(rd:Road)<-[:ON_ROAD]-(o:Issue)
        WHERE o.category = i.category AND o.created_at > $since AND o.issue_id <> i.issue_id
        WITH i, rd, count(DISTINCT o) AS same_road
        OPTIONAL MATCH (i)-[:LOCATED_IN]->(n:Neighborhood)<-[:LOCATED_IN]-(o2:Issue)
        WHERE o2.category = i.category AND o2.created_at > $since AND o2.issue_id <> i.issue_id
        RETURN rd.name AS road, same_road, n.name AS neighborhood, count(DISTINCT o2) AS same_neighborhood
        """, {"id": issue_id, "since": now_ms() - days * 86400 * 1000}, readonly=True)
    return ToolResult(tool="recurrence", query_id="agents/tools.py#recurrence", rows=rows)
