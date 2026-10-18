import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

const TZ = "Asia/Kolkata";

export function timeAgo(ms?: number | null) {
  if (!ms) return "";
  const diff = Date.now() - ms;
  const abs = Math.abs(diff);
  const future = diff < 0;
  const units: [number, string][] = [
    [60_000, "min"],
    [3_600_000, "h"],
    [86_400_000, "d"],
  ];
  if (abs < 60_000) return future ? "in a moment" : "just now";
  let out = "";
  if (abs < 3_600_000) out = `${Math.round(abs / units[0][0])} min`;
  else if (abs < 86_400_000) out = `${Math.round(abs / units[1][0])} h`;
  else if (abs < 30 * 86_400_000) out = `${Math.round(abs / units[2][0])} d`;
  else return formatDate(ms);
  return future ? `in ${out}` : `${out} ago`;
}

export function formatDate(ms?: number | null, opts: Intl.DateTimeFormatOptions = {}) {
  if (!ms) return "";
  return new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", year: "numeric", timeZone: TZ, ...opts }).format(ms);
}

export function formatDateTime(ms?: number | null) {
  if (!ms) return "";
  return new Intl.DateTimeFormat("en-IN", {
    weekday: "short",
    day: "numeric",
    month: "short",
    hour: "numeric",
    minute: "2-digit",
    timeZone: TZ,
  }).format(ms);
}

export function formatTime(ms?: number | null) {
  if (!ms) return "";
  return new Intl.DateTimeFormat("en-IN", { hour: "numeric", minute: "2-digit", timeZone: TZ }).format(ms);
}

export const ISSUE_CATEGORIES: Record<string, string> = {
  waterlogging: "Waterlogging",
  roads_potholes: "Roads and potholes",
  streetlights: "Streetlights",
  garbage: "Garbage",
  water_supply: "Water supply",
  sanitation: "Public sanitation",
  traffic_obstruction: "Traffic obstruction",
  public_infrastructure: "Public infrastructure",
  accessibility: "Accessibility",
  other: "Other",
};

export const ISSUE_STATUSES: Record<string, string> = {
  submitted: "Submitted",
  community_corroborated: "Community corroborated",
  under_review: "Under community review",
  coordination_in_progress: "Coordination in progress",
  resolved_reporter_confirmed: "Resolved by reporter",
  closed: "Closed",
};

export const EVENT_CATEGORIES: Record<string, string> = {
  cultural: "Cultural festivals",
  concert: "Concerts",
  exhibition: "Exhibitions",
  educational: "Educational events",
  community_meeting: "Community meetings",
  cleanup: "Neighbourhood cleanups",
  workshop: "Workshops",
  market: "Markets",
  volunteering: "Volunteering",
  sports: "Sports and recreation",
};

export const ASSET_TYPES: Record<string, string> = {
  metro_station: "Metro station",
  hospital: "Hospital",
  police: "Police station",
  fire_station: "Fire station",
  public_toilet: "Public toilet",
  park: "Park",
};

export const ACTION_TYPES: Record<string, string> = {
  assign_coordinator: "Assign coordinator",
  request_more_info: "Request more information",
  publish_community_update: "Publish community update",
  link_related_reports: "Link related reports",
  request_community_verification: "Request community verification",
  contact_organizer: "Contact event organizer",
  mark_completed: "Mark completed",
  invite_replacement: "Invite replacement performers",
  notify_attendees: "Notify event participants",
};

export function label(map: Record<string, string>, key?: string | null) {
  if (!key) return "";
  return map[key] ?? key.replace(/_/g, " ");
}

export function pluralize(n: number, one: string, many?: string) {
  return `${n} ${n === 1 ? one : many ?? one + "s"}`;
}
