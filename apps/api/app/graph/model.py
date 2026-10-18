"""Graph vocabulary: labels, ID prefixes, provenance statuses and public property allowlists.

IDs carry a prefix that identifies their label, so any entity can be resolved by ID with an indexed lookup.
"""

import secrets
import time

LABELS: dict[str, tuple[str, str]] = {
    "res": ("Resident", "resident_id"),
    "nbh": ("Neighborhood", "neighborhood_id"),
    "area": ("AdministrativeArea", "area_id"),
    "org": ("Organization", "organization_id"),
    "ast": ("InfrastructureAsset", "asset_id"),
    "road": ("Road", "road_id"),
    "ven": ("Venue", "venue_id"),
    "evt": ("Event", "event_id"),
    "iss": ("Issue", "issue_id"),
    "wrn": ("Warning", "warning_id"),
    "com": ("Community", "community_id"),
    "case": ("CoordinationCase", "case_id"),
    "act": ("CoordinationAction", "action_id"),
    "dec": ("AgentDecision", "decision_id"),
    "mem": ("AgentMemory", "memory_id"),
    "src": ("Source", "source_id"),
    "dis": ("Discussion", "discussion_id"),
    "crd": ("Coordinator", "coordinator_id"),
    "prof": ("Profession", "profession_id"),
}
ID_PROP = {label: prop for label, prop in LABELS.values()}


class VerificationStatus:
    OFFICIAL_VERIFIED = "OFFICIAL_VERIFIED"
    SOURCE_VERIFIED = "SOURCE_VERIFIED"
    COMMUNITY_REPORTED = "COMMUNITY_REPORTED"
    COMMUNITY_CORROBORATED = "COMMUNITY_CORROBORATED"
    RULE_INFERRED = "RULE_INFERRED"  # deterministic graph/geo rule, not an LLM
    AI_INFERRED = "AI_INFERRED"
    EXPIRED = "EXPIRED"
    RETRACTED = "RETRACTED"


def new_id(prefix: str) -> str:
    assert prefix in LABELS, prefix
    return f"{prefix}_{secrets.token_hex(8)}"


def label_for_id(entity_id: str) -> tuple[str, str] | None:
    prefix = entity_id.split("_", 1)[0]
    return LABELS.get(prefix)


def now_ms() -> int:
    return int(time.time() * 1000)


# Properties that may leave the API for each label. Anything not listed is never returned publicly.
# Resident is handled specially in `public_props` (name only with explicit opt-in).
PUBLIC_PROPS: dict[str, set[str]] = {
    "Neighborhood": {"neighborhood_id", "name", "administrative_type", "latitude", "longitude", "source_id"},
    "AdministrativeArea": {"area_id", "name", "type", "boundary_source"},
    "Organization": {"organization_id", "name", "category", "official_website", "verification_status"},
    "InfrastructureAsset": {"asset_id", "asset_type", "name", "latitude", "longitude", "source_id",
                            "verification_status", "osm_ref"},
    "Road": {"road_id", "name", "road_class", "source_id", "osm_ref"},
    "Venue": {"venue_id", "name", "latitude", "longitude", "address", "source_id"},
    "Event": {"event_id", "title", "description", "category", "start_time", "end_time", "status",
              "verification_status", "source_type", "is_free", "setting", "accessibility", "registration_url",
              "public_lat", "public_lng", "organizer_name", "organizer_attestation", "performer_gap", "agent_autopilot",
              "demo", "created_at"},
    "Issue": {"issue_id", "title", "description", "category", "status", "public_lat", "public_lng",
              "public_location_precision", "created_at", "updated_at", "verification_status", "support_count"},
    "Warning": {"warning_id", "title", "warning_type", "category", "severity", "urgency", "certainty",
                "issuing_authority", "issued_at", "effective_at", "expires_at", "verification_status",
                "area_description", "instruction", "source_url", "source_name", "license", "ingested_at"},
    "Community": {"community_id", "name", "neighborhood_id", "description"},
    "CoordinationCase": {"case_id", "title", "case_type", "status", "created_at", "updated_at"},
    "CoordinationAction": {"action_id", "action_type", "status", "description", "proposed_by", "approved_by",
                           "executed_at", "outcome", "created_at"},
    "AgentDecision": {"decision_id", "agent_name", "decision_type", "rationale", "created_at", "model_name",
                      "evidence_strength", "review_status"},
    "AgentMemory": {"memory_id", "memory_type", "summary", "created_at", "valid_until", "source_reference"},
    "Source": {"source_id", "name", "url", "license", "source_type", "retrieved_at", "published_at",
               "verification_status"},
    "Discussion": {"discussion_id", "body", "created_at", "visibility", "kind"},
    "Coordinator": {"coordinator_id", "display_name"},
    "Profession": {"profession_id", "name", "category"},
}


def public_props(label: str, props: dict) -> dict:
    if label == "Resident":
        shown = props.get("display_name_opt_in") and props.get("public_visibility") == "public"
        return {
            "resident_id": props.get("resident_id"),
            "display_name": props.get("name") if shown else None,
            "profession": props.get("profession") if shown else None,
            "demo": bool(props.get("demo")) if shown else None,
        }
    allowed = PUBLIC_PROPS.get(label, set())
    return {k: v for k, v in props.items() if k in allowed}


def display_label(label: str, props: dict) -> str:
    if label == "Resident":
        p = public_props(label, props)
        return p["display_name"] or "Resident (private)"
    for key in ("title", "name", "summary", "action_type", "decision_type", "body"):
        if props.get(key):
            text = str(props[key])
            return text if len(text) <= 60 else text[:57] + "…"
    return label
