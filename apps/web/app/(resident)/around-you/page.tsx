"use client";

import { useQuery } from "@tanstack/react-query";
import { Bell, CalendarDays, Info, List, Map as MapIcon, Megaphone, TriangleAlert, Users } from "lucide-react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useMemo, useState } from "react";
import type { MapFeature } from "@/components/map/map-view";
import { Button } from "@/components/ui/button";
import { Badge, Card, Chip, Segmented } from "@/components/ui/primitives";
import { EmptyState, ErrorState, ListSkeleton } from "@/components/ui/states";
import { FeedCard } from "@/features/feed/feed-card";
import { NeighborhoodPicker } from "@/features/neighborhood/neighborhood-picker";
import { useProfile } from "@/hooks/use-profile";
import { api } from "@/lib/api";
import { pluralize } from "@/lib/format";
import { type FeedKind, type RadiusKm, useDiscovery } from "@/lib/store";
import type { Center, FeedItem } from "@/lib/types";

const MapView = dynamic(() => import("@/components/map/map-view").then((m) => m.MapView), { ssr: false, loading: () => <div className="skeleton h-full w-full" /> });

const FILTERS: { value: FeedKind; label: string; icon: any }[] = [
  { value: "all", label: "All", icon: null },
  { value: "complaints", label: "Complaints", icon: Megaphone },
  { value: "events", label: "Events", icon: CalendarDays },
  { value: "community", label: "Community", icon: Users },
  { value: "warnings", label: "Warnings", icon: TriangleAlert },
  { value: "following", label: "Following", icon: Bell },
];

interface Contributor {
  resident_id: string;
  display_name: string;
  neighborhood: string | null;
  contributions: { type: string; kind: string; entity_id: string; title: string }[];
}

const VERB: Record<string, string> = { REPORTED: "reported", SUPPORTS: "is affected by", FOLLOWS: "follows", SUBMITTED: "is organising", PARTICIPATES_IN: "is joining" };

export default function AroundYou() {
  const { profile, isLoading: profileLoading } = useProfile();
  const { radius, setRadius, kind, setKind, neighborhood, setNeighborhood } = useDiscovery();
  const [view, setView] = useState<"list" | "map">("list");
  const [selected, setSelected] = useState<string | null>(null);
  const params = { radius_km: radius, neighborhood_id: neighborhood?.id };

  const feed = useQuery({
    queryKey: ["nearby", "activity", profile?.resident_id ?? "visitor", radius, kind, neighborhood?.id],
    queryFn: () => api.get<{ center: Center; items: FeedItem[] }>("/nearby/activity", { ...params, kind }),
    enabled: !profileLoading,
  });
  const people = useQuery({
    queryKey: ["nearby", "contributors", profile?.resident_id ?? "visitor", radius, neighborhood?.id],
    queryFn: () => api.get<{ center: Center; contributors: Contributor[]; query_id: string }>("/nearby/contributors", params),
    enabled: !profileLoading,
  });

  const items = feed.data?.items ?? [];
  const center = feed.data?.center;
  const features = useMemo<MapFeature[]>(
    () =>
      items
        .map((i): MapFeature | null => {
          if (i.kind === "issue") return { type: "Feature", geometry: { type: "Point", coordinates: [i.public_lng, i.public_lat] }, properties: { kind: "issue", id: i.issue_id, title: i.title } };
          if (i.kind === "event") return { type: "Feature", geometry: { type: "Point", coordinates: [i.public_lng, i.public_lat] }, properties: { kind: "event", id: i.event_id, title: i.title } };
          return null;
        })
        .filter(Boolean) as MapFeature[],
    [items],
  );
  const counts = {
    issue: items.filter((i) => i.kind === "issue").length,
    event: items.filter((i) => i.kind === "event").length,
    warning: items.filter((i) => i.kind === "warning").length,
  };
  const selectedItem = items.find((i) => (i.kind === "issue" ? i.issue_id : i.kind === "event" ? i.event_id : null) === selected);

  return (
    <div className="container-page py-8 md:py-10">
      <div className="mb-6 flex flex-col gap-5 md:flex-row md:items-end md:justify-between">
        <div>
          <div className="eyebrow mb-2">Community network</div>
          <h1 className="font-display text-[38px] leading-[1.05] tracking-tight md:text-[46px]">Around you</h1>
          <p className="mt-2 max-w-xl text-[15px] text-slate">
            {center ? (
              <>
                Within <b className="font-medium text-ink">{radius} km</b> of <b className="font-medium text-ink">{center.mode === "home" ? `home (${center.label})` : center.label}</b>:{" "}
                {pluralize(counts.issue, "report")}, {pluralize(counts.event, "event")}, {pluralize(counts.warning, "official alert")}.
              </>
            ) : (
              "Reports, events, alerts and coordination near you."
            )}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <NeighborhoodPicker value={neighborhood} onChange={setNeighborhood} homeLabel={profile ? profile.neighborhood_name ?? "your area" : null} />
          <Segmented<RadiusKm>
            ariaLabel="Search radius"
            value={radius}
            onChange={setRadius}
            options={[1, 3, 5, 10].map((r) => ({ value: r as RadiusKm, label: `${r} km` }))}
          />
          <Segmented
            ariaLabel="View"
            value={view}
            onChange={setView}
            options={[
              { value: "list", label: <List className="size-4" aria-label="List" /> },
              { value: "map", label: <MapIcon className="size-4" aria-label="Map" /> },
            ]}
          />
        </div>
      </div>

      <div className="-mx-4 mb-6 flex gap-2 overflow-x-auto px-4 pb-1 md:mx-0 md:px-0">
        {FILTERS.map((f) => (
          <Chip key={f.value} active={kind === f.value} onClick={() => setKind(f.value)}>
            {f.icon && <f.icon />} {f.label}
          </Chip>
        ))}
      </div>

      <div className="grid gap-8 lg:grid-cols-[1fr_330px]">
        <div>
          {view === "map" && (
            <Card className="mb-5 overflow-hidden">
              <div className="h-[420px]">
                <MapView
                  center={center ? { latitude: center.latitude, longitude: center.longitude } : null}
                  radiusKm={radius}
                  features={features}
                  selectedId={selected}
                  onSelect={(f) => setSelected(f?.properties.id ?? null)}
                />
              </div>
              {selectedItem && (
                <div className="border-t border-line p-4">
                  <FeedCard item={selectedItem} />
                </div>
              )}
            </Card>
          )}
          {feed.isLoading || profileLoading ? (
            <ListSkeleton rows={3} />
          ) : feed.error ? (
            <ErrorState error={feed.error} onRetry={() => feed.refetch()} />
          ) : items.length === 0 ? (
            <EmptyState
              icon={<Megaphone />}
              title={kind === "following" ? "You're not following anything here yet" : "No public contributions in this area yet"}
              body={kind === "following" ? "Follow a report to see its updates in this view." : "Be the first to help your neighbourhood stay connected."}
              action={
                <div className="flex flex-wrap justify-center gap-2">
                  <Button asChild variant="accent">
                    <Link href="/report">Report an issue</Link>
                  </Button>
                  {radius < 10 && (
                    <Button variant="outline" onClick={() => setRadius((radius === 1 ? 3 : radius === 3 ? 5 : 10) as RadiusKm)}>
                      Widen to {radius === 1 ? 3 : radius === 3 ? 5 : 10} km
                    </Button>
                  )}
                </div>
              }
            />
          ) : (
            <div className="space-y-3">
              {items.map((i) => (
                <FeedCard key={i.kind + ((i as any).issue_id ?? (i as any).event_id ?? (i as any).warning_id ?? (i as any).case_id)} item={i} />
              ))}
            </div>
          )}
        </div>

        <aside className="space-y-5">
          <Card className="p-5">
            <div className="flex items-center justify-between">
              <h2 className="text-[14px] font-semibold">Neighbours contributing nearby</h2>
              <Users className="size-4 text-slate" />
            </div>
            <p className="mt-1 text-[12.5px] leading-relaxed text-slate">Only residents who chose a public, named profile appear here. Homes and emails are never shown.</p>
            {people.isLoading ? (
              <div className="skeleton mt-4 h-16 rounded-lg" />
            ) : people.error ? (
              <ErrorState error={people.error} className="mt-3" />
            ) : people.data?.contributors.length ? (
              <ul className="mt-4 space-y-3.5">
                {people.data.contributors.slice(0, 8).map((c) => (
                  <li key={c.resident_id} className="flex gap-3">
                    <span className="grid size-8 shrink-0 place-items-center rounded-full bg-teal-50 text-[12px] font-semibold text-teal-600">
                      {c.display_name
                        .split(" ")
                        .map((p) => p[0])
                        .slice(0, 2)
                        .join("")}
                    </span>
                    <div className="min-w-0">
                      <p className="text-[13.5px] font-medium">
                        {c.display_name}
                        {c.neighborhood && <span className="font-normal text-slate"> · {c.neighborhood}</span>}
                      </p>
                      {c.contributions.slice(0, 2).map((x) => (
                        <Link key={x.type + x.entity_id} href={x.kind === "Event" ? `/events/${x.entity_id}` : `/issues/${x.entity_id}`} className="block truncate text-[12.5px] text-slate hover:text-ink">
                          {VERB[x.type] ?? x.type.toLowerCase()} “{x.title}”
                        </Link>
                      ))}
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-4 rounded-lg bg-paper-2 p-3 text-[13px] text-slate">No public contributors within {radius} km yet.</p>
            )}
            {profile && profile.public_visibility === "private" && (
              <Link href="/profile" className="mt-4 block text-[12.5px] font-medium text-teal-600 hover:underline">
                Want neighbours to see your name? Update privacy →
              </Link>
            )}
          </Card>

          <Card className="p-5">
            <div className="flex items-center gap-2 text-[13px] font-semibold">
              <Info className="size-4 text-teal" /> How this feed is built
            </div>
            <ol className="mt-3 space-y-2 text-[12.5px] leading-relaxed text-slate">
              <li>
                <Badge tone="teal" className="mr-1">1</Badge> FalkorDB selects reports and events whose location lies within {radius} km using a geospatial point index.
              </li>
              <li>
                <Badge tone="teal" className="mr-1">2</Badge> Graph traversals add who reported and corroborated, coordination cases, and your own follows.
              </li>
              <li>
                <Badge tone="teal" className="mr-1">3</Badge> Official alerts join through <code>Warning-AFFECTS→Neighbourhood</code>.
              </li>
            </ol>
            {people.data?.query_id && <p className="mt-3 font-mono text-[11px] text-slate">{people.data.query_id}</p>}
          </Card>
        </aside>
      </div>
    </div>
  );
}
