"use client";

import * as Tooltip from "@radix-ui/react-tooltip";
import {
  Accessibility,
  BadgeCheck,
  Bot,
  Building2,
  CalendarDays,
  CircleHelp,
  Clock,
  Construction,
  Droplets,
  GitBranch,
  Lightbulb,
  Megaphone,
  ShieldCheck,
  ShowerHead,
  TrafficCone,
  Trash2,
  TriangleAlert,
  Users,
  Waves,
} from "lucide-react";
import { ISSUE_STATUSES, label } from "@/lib/format";
import { Badge } from "./ui/primitives";

const PROVENANCE: Record<string, { text: string; tone: any; icon: any; explain: string }> = {
  OFFICIAL_VERIFIED: { text: "Official source", tone: "navy", icon: ShieldCheck, explain: "Published by an official authority and ingested from its public feed. CityPulse links to the original." },
  SOURCE_VERIFIED: { text: "Source-backed", tone: "teal", icon: BadgeCheck, explain: "Comes from a documented public data source (e.g. OpenStreetMap) with attribution." },
  COMMUNITY_REPORTED: { text: "Community report", tone: "neutral", icon: Megaphone, explain: "Submitted by a CityPulse resident. Not verified by any government authority." },
  COMMUNITY_CORROBORATED: { text: "Corroborated", tone: "positive", icon: Users, explain: "Several residents independently confirmed they are affected. Still not an official confirmation." },
  RULE_INFERRED: { text: "Graph-inferred", tone: "violet", icon: GitBranch, explain: "Derived by a deterministic graph or location rule (e.g. nearest mapped place). Shown with its basis." },
  AI_INFERRED: { text: "AI inference", tone: "violet", icon: Bot, explain: "Produced by an AI agent. Never an official fact; requires human review." },
  EXPIRED: { text: "Expired", tone: "outline", icon: Clock, explain: "No longer in effect according to its source." },
  RETRACTED: { text: "Retracted", tone: "critical", icon: TriangleAlert, explain: "Withdrawn by its source." },
};

export function ProvenanceBadge({ status }: { status?: string | null }) {
  if (!status) return null;
  const p = PROVENANCE[status] ?? { text: status, tone: "neutral", icon: CircleHelp, explain: status };
  return (
    <Tooltip.Root>
      <Tooltip.Trigger asChild>
        <span tabIndex={0} className="inline-flex">
          <Badge tone={p.tone}>
            <p.icon /> {p.text}
          </Badge>
        </span>
      </Tooltip.Trigger>
      <Tooltip.Portal>
        <Tooltip.Content sideOffset={6} className="z-50 max-w-64 rounded-lg bg-navy px-3 py-2 text-[12.5px] leading-snug text-white shadow-lg">
          {p.explain}
        </Tooltip.Content>
      </Tooltip.Portal>
    </Tooltip.Root>
  );
}

const STATUS_TONE: Record<string, any> = {
  submitted: "neutral",
  community_corroborated: "positive",
  under_review: "amber",
  coordination_in_progress: "teal",
  resolved_reporter_confirmed: "positive",
  closed: "outline",
};

export function StatusBadge({ status }: { status: string }) {
  return <Badge tone={STATUS_TONE[status] ?? "neutral"}>{label(ISSUE_STATUSES, status)}</Badge>;
}

export function SeverityBadge({ severity }: { severity?: string | null }) {
  if (!severity) return null;
  const tone = severity === "Extreme" || severity === "Severe" ? "critical" : severity === "Moderate" ? "amber" : "neutral";
  return (
    <Badge tone={tone}>
      <TriangleAlert /> {severity}
    </Badge>
  );
}

export const CATEGORY_ICONS: Record<string, any> = {
  waterlogging: Waves,
  roads_potholes: Construction,
  streetlights: Lightbulb,
  garbage: Trash2,
  water_supply: Droplets,
  sanitation: ShowerHead,
  traffic_obstruction: TrafficCone,
  public_infrastructure: Building2,
  accessibility: Accessibility,
  other: CircleHelp,
};

export function CategoryIcon({ category, className }: { category: string; className?: string }) {
  const Icon = CATEGORY_ICONS[category] ?? CircleHelp;
  return <Icon className={className} />;
}

export function KindIcon({ kind, className }: { kind: string; className?: string }) {
  const Icon = kind === "event" ? CalendarDays : kind === "warning" ? TriangleAlert : kind === "coordination" ? Users : Megaphone;
  return <Icon className={className} />;
}
