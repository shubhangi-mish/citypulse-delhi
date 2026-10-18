export type Verification =
  | "OFFICIAL_VERIFIED"
  | "SOURCE_VERIFIED"
  | "COMMUNITY_REPORTED"
  | "COMMUNITY_CORROBORATED"
  | "RULE_INFERRED"
  | "AI_INFERRED"
  | "EXPIRED"
  | "RETRACTED";

export interface Profile {
  resident_id: string;
  name: string;
  email: string;
  address: string;
  latitude: number;
  longitude: number;
  public_visibility: "private" | "public";
  display_name_opt_in: boolean;
  discovery_opt_in: boolean;
  area_updates_opt_in: boolean;
  profession?: string | null;
  demo?: boolean | null;
  open_to_gigs?: boolean | null;
  neighborhood_id: string | null;
  neighborhood_name: string | null;
  neighborhood_latitude: number | null;
  neighborhood_longitude: number | null;
  created_at: number;
}

export interface Neighborhood {
  neighborhood_id: string;
  name: string;
  district?: string | null;
  latitude: number;
  longitude: number;
  distance_m?: number;
}

export interface IssueCard {
  kind?: "issue";
  issue_id: string;
  title: string;
  description: string;
  category: string;
  status: string;
  public_lat: number;
  public_lng: number;
  public_location_precision: string;
  created_at: number;
  updated_at: number;
  verification_status: Verification;
  support_count: number;
  neighborhood: string | null;
  comment_count: number;
  reported_by: string | null;
  in_coordination?: boolean;
  viewer?: { supported: boolean; following: boolean; mine: boolean };
  distance?: string;
}

export interface EventCard {
  kind?: "event";
  event_id: string;
  title: string;
  description: string;
  category: string;
  start_time: number;
  end_time: number;
  status: string;
  verification_status: Verification;
  source_type: string;
  is_free: boolean | null;
  setting: string | null;
  organizer_attestation?: boolean;
  performer_gap?: boolean;
  accessibility: string | null;
  registration_url: string | null;
  public_lat: number;
  public_lng: number;
  organizer_name: string;
  venue: string | null;
  neighborhood: string | null;
  participant_count: number;
  warning_count: number;
  viewer?: { participating: boolean };
  distance?: string;
}

export interface WarningCard {
  kind?: "warning";
  warning_id: string;
  title: string;
  warning_type: string | null;
  category: string | null;
  severity: string | null;
  urgency: string | null;
  certainty: string | null;
  issuing_authority: string;
  issued_at: number;
  effective_at: number;
  expires_at: number;
  verification_status: Verification;
  area_description: string | null;
  instruction: string | null;
  source_url: string;
  source_name: string;
  license: string;
  ingested_at: number;
  affected_neighborhoods?: string[];
  affected_count?: number;
  affected_neighborhood_count?: number;
  affected_event_count?: number;
  active?: boolean;
}

export interface CaseCard {
  kind?: "coordination";
  case_id: string;
  title: string;
  case_type: string;
  status: string;
  created_at: number;
  updated_at: number;
  issues: { issue_id: string; title: string }[];
  participant_count?: number;
  action_count?: number;
  pending_actions?: number;
}

export type FeedItem = (IssueCard & { kind: "issue" }) | (EventCard & { kind: "event" }) | (WarningCard & { kind: "warning" }) | (CaseCard & { kind: "coordination" });

export interface Center {
  label: string;
  mode: "home" | "neighborhood" | "point" | "default";
  latitude: number;
  longitude: number;
  radius_km: number;
}

export interface GraphNode {
  id: string;
  label: string;
  name: string;
  props: Record<string, any>;
  expandable?: boolean;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type: string;
  class: "verified" | "community" | "inferred" | "coordination" | "ai";
  meaning: string;
  basis?: string | null;
  verification_status?: string | null;
  score?: number | null;
  reasons?: string[] | null;
}

export interface PathStep {
  id: string | null;
  label: string;
  name: string | null;
}

export interface ExplanationPath {
  nodes: PathStep[];
  rels: string[];
  query_id: string;
  meaning: string;
}
