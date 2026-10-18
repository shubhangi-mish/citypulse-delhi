"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, CalendarPlus, Compass, Megaphone, Network, ShieldCheck, TriangleAlert } from "lucide-react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type { MapFeature } from "@/components/map/map-view";
import { Button } from "@/components/ui/button";
import { Card, SectionHeader, Skeleton } from "@/components/ui/primitives";
import { EmptyState, ErrorState, ListSkeleton } from "@/components/ui/states";
import { EventFeedCard, IssueFeedCard, WarningFeedCard } from "@/features/feed/feed-card";
import { GraphSearch } from "@/features/search/graph-search";
import { useProfile } from "@/hooks/use-profile";
import { api } from "@/lib/api";
import type { Center, FeedItem, WarningCard } from "@/lib/types";

const MapView = dynamic(() => import("@/components/map/map-view").then((m) => m.MapView), { ssr: false, loading: () => <div className="skeleton h-full w-full" /> });

function greeting() {
  const h = Number(new Intl.DateTimeFormat("en-IN", { hour: "numeric", hourCycle: "h23", timeZone: "Asia/Kolkata" }).format(new Date()));
  return h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening";
}

export default function Home() {
  const { profile, isLoading: profileLoading } = useProfile();
  const radius = profile ? 3 : 5;
  const feed = useQuery({
    queryKey: ["nearby", "home", profile?.resident_id ?? "visitor", radius],
    queryFn: () => api.get<{ center: Center; items: FeedItem[] }>("/nearby/activity", { radius_km: radius }),
    enabled: !profileLoading,
  });
  const warnings = useQuery({ queryKey: ["warnings", "active"], queryFn: () => api.get<{ items: WarningCard[] }>("/warnings") });
  const stats = useQuery({ queryKey: ["graph-stats"], queryFn: () => api.get<{ nodes: Record<string, number>; relationships: Record<string, number> }>("/graph/stats"), staleTime: 300_000 });

  const router = useRouter();
  const mapData = useQuery({
    queryKey: ["map-layers", "home"],
    queryFn: () => api.get<{ features: MapFeature[] }>("/map/layers", { layers: "issues,events,warnings" }),
    refetchInterval: 60_000,
  });
  const mapFeatures = mapData.data?.features ?? [];
  const mapCounts = mapFeatures.reduce<Record<string, number>>((a, f) => ((a[f.properties.kind] = (a[f.properties.kind] ?? 0) + 1), a), {});
  const items = feed.data?.items ?? [];
  const issues = items.filter((i) => i.kind === "issue");
  const events = items.filter((i) => i.kind === "event");
  const needsAttention = issues.filter((i) => i.kind === "issue" && i.status === "submitted" && (i.support_count ?? 0) < 3 && !i.viewer?.mine);
  const recent = issues.slice(0, 4);

  return (
    <div>
      <section className="border-b border-line bg-[radial-gradient(1200px_400px_at_80%_-20%,#dff0ef_0%,transparent_60%)]">
        <div className="container-page py-12 md:py-16">
          {profile ? (
            <>
              <div className="eyebrow mb-3">{profile.neighborhood_name ?? "Your area"} · Delhi</div>
              <h1 className="font-display text-[40px] leading-[1.05] tracking-tight md:text-[54px]">
                {greeting()}, {profile.name.split(" ")[0]}.
              </h1>
              <p className="mt-3 max-w-xl text-[15.5px] text-slate">Here's what's happening within {radius} km of home, from neighbours and official sources.</p>
            </>
          ) : (
            <>
              <div className="eyebrow mb-3">Delhi · community & city information</div>
              <h1 className="max-w-3xl font-display text-[42px] leading-[1.03] tracking-tight md:text-[64px]">
                What's happening around you, <span className="italic text-teal">and who's on it.</span>
              </h1>
              <p className="mt-5 max-w-xl text-[16px] leading-relaxed text-slate">
                CityPulse connects residents, reports, events and official alerts across Delhi in one city graph — so neighbours can see shared problems, coordinate, and know what's verified.
              </p>
              <div className="mt-7 flex flex-wrap gap-3">
                <Button asChild size="lg">
                  <Link href="/onboarding">
                    Continue as a resident <ArrowRight />
                  </Link>
                </Button>
                <Button asChild size="lg" variant="outline">
                  <Link href="/explore">Explore the map</Link>
                </Button>
              </div>
            </>
          )}
          <GraphSearch className="mt-8 max-w-2xl" />
        </div>
      </section>

      <section className="container-page pt-10">
        <SectionHeader
          eyebrow="Live map"
          title="What's happening across Delhi"
          action={
            <Link href="/explore" className="text-[13.5px] font-medium text-teal-600 hover:underline">
              Open full map
            </Link>
          }
        />
        <Card className="overflow-hidden">
          <div className="relative h-[340px] md:h-[420px]">
            <MapView
              features={mapFeatures}
              center={profile?.neighborhood_latitude && profile.neighborhood_longitude ? { latitude: profile.neighborhood_latitude, longitude: profile.neighborhood_longitude } : null}
              zoom={profile ? 12 : 10.5}
              onSelect={(f) => {
                if (!f) return;
                const { kind, id } = f.properties;
                router.push(kind === "issue" ? `/issues/${id}` : kind === "event" ? `/events/${id}` : `/warnings/${id}`);
              }}
            />
          </div>
          <div className="flex flex-wrap items-center gap-x-5 gap-y-1 border-t border-line px-4 py-3 text-[13px] text-slate">
            <span className="flex items-center gap-1.5"><span className="size-2.5 rounded-full bg-teal" /> {mapCounts.issue ?? 0} reports</span>
            <span className="flex items-center gap-1.5"><span className="size-2.5 rounded-full bg-violet" /> {mapCounts.event ?? 0} events</span>
            <span className="flex items-center gap-1.5"><span className="size-2.5 rounded-full bg-amber" /> {warnings.data?.items.length ?? 0} active official alerts</span>
            <span className="ml-auto text-[12px]">Click a pin to open it · report locations are approximate</span>
          </div>
        </Card>
      </section>

      <div className="container-page grid gap-10 py-10 lg:grid-cols-[1fr_340px]">
        <div className="space-y-12">
          <section>
            <SectionHeader
              eyebrow="Verified information"
              title="Official alerts for Delhi"
              action={
                <Link href="/warnings" className="text-[13.5px] font-medium text-teal-600 hover:underline">
                  All alerts
                </Link>
              }
            />
            {warnings.isLoading ? (
              <ListSkeleton rows={1} />
            ) : warnings.error ? (
              <ErrorState error={warnings.error} onRetry={() => warnings.refetch()} />
            ) : warnings.data?.items.length ? (
              <div className="space-y-3">
                {warnings.data.items.slice(0, 2).map((w) => (
                  <WarningFeedCard key={w.warning_id} item={w} />
                ))}
              </div>
            ) : (
              <EmptyState
                icon={<ShieldCheck />}
                title="No active official alerts for Delhi"
                body="CityPulse checks the NDMA SACHET alert feed (IMD, SDMAs) every 15 minutes. When an alert covers Delhi, it appears here with its source."
              />
            )}
          </section>

          <section>
            <SectionHeader
              eyebrow={`Within ${radius} km`}
              title="Community activity"
              action={
                <Link href="/around-you" className="text-[13.5px] font-medium text-teal-600 hover:underline">
                  Around you
                </Link>
              }
            />
            {feed.isLoading || profileLoading ? (
              <ListSkeleton rows={2} />
            ) : feed.error ? (
              <ErrorState error={feed.error} onRetry={() => feed.refetch()} />
            ) : recent.length ? (
              <div className="space-y-3">
                {recent.map((i) => i.kind === "issue" && <IssueFeedCard key={i.issue_id} item={i} />)}
              </div>
            ) : (
              <EmptyState
                icon={<Megaphone />}
                title="No public contributions in this area yet"
                body="Be the first to help your neighbourhood stay connected."
                action={
                  <Button asChild variant="accent">
                    <Link href="/report">Report something</Link>
                  </Button>
                }
              />
            )}
          </section>

          <section>
            <SectionHeader
              eyebrow="Coming up nearby"
              title="Events"
              action={
                <Link href="/events" className="text-[13.5px] font-medium text-teal-600 hover:underline">
                  All events
                </Link>
              }
            />
            {feed.isLoading ? (
              <ListSkeleton rows={1} />
            ) : events.length ? (
              <div className="space-y-3">{events.slice(0, 3).map((e) => e.kind === "event" && <EventFeedCard key={e.event_id} item={e} />)}</div>
            ) : (
              <EmptyState
                icon={<CalendarPlus />}
                title="No upcoming events nearby"
                body="Organising a cleanup, workshop or community meeting? Share it so neighbours can join."
                action={
                  <Button asChild variant="outline">
                    <Link href="/events/create">Share an event</Link>
                  </Button>
                }
              />
            )}
          </section>
        </div>

        <aside className="space-y-6">
          <Card className="overflow-hidden">
            <div className="bg-navy p-5 text-white">
              <Megaphone className="size-5 text-[#7fd1c0]" />
              <h3 className="mt-3 text-[17px] font-semibold">Seen something that needs fixing?</h3>
              <p className="mt-1.5 text-[13.5px] leading-relaxed text-white/75">
                Report it to the CityPulse community. Neighbours can confirm it, and coordinators can connect related reports.
              </p>
              <Button asChild variant="accent" className="mt-4 w-full">
                <Link href="/report">Report an issue</Link>
              </Button>
              <Button asChild variant="dark" className="mt-2 w-full">
                <Link href="/events/create">
                  <CalendarPlus /> Share an event
                </Link>
              </Button>
            </div>
            <p className="px-5 py-3 text-[12px] text-slate">This doesn't file a complaint with a government department.</p>
          </Card>

          {needsAttention.length > 0 && (
            <Card className="p-5">
              <div className="flex items-center gap-2 text-[13px] font-semibold">
                <TriangleAlert className="size-4 text-amber" /> Reports needing confirmation
              </div>
              <ul className="mt-3 space-y-2.5">
                {needsAttention.slice(0, 4).map(
                  (i) =>
                    i.kind === "issue" && (
                      <li key={i.issue_id}>
                        <Link href={`/issues/${i.issue_id}`} className="block text-[14px] leading-snug hover:text-teal-600">
                          {i.title}
                        </Link>
                        <span className="text-[12px] text-slate">
                          {i.neighborhood} · {i.support_count} affected
                        </span>
                      </li>
                    ),
                )}
              </ul>
            </Card>
          )}

          <Card className="p-5">
            <div className="flex items-center gap-2 text-[13px] font-semibold">
              <Network className="size-4 text-teal" /> The city graph today
            </div>
            <p className="mt-1 text-[12.5px] text-slate">Live counts from FalkorDB — sourced data plus genuine CityPulse activity.</p>
            {stats.isLoading ? (
              <Skeleton className="mt-4 h-24" />
            ) : stats.data ? (
              <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3">
                {[
                  ["Neighbourhoods", "Neighborhood"],
                  ["Infrastructure", "InfrastructureAsset"],
                  ["Districts", "AdministrativeArea"],
                  ["Reports", "Issue"],
                  ["Events", "Event"],
                  ["Official alerts", "Warning"],
                ].map(([l, k]) => (
                  <div key={k}>
                    <dt className="text-[11.5px] text-slate">{l}</dt>
                    <dd className="text-[18px] font-semibold tabular-nums">{(stats.data!.nodes[k] ?? 0).toLocaleString("en-IN")}</dd>
                  </div>
                ))}
              </dl>
            ) : null}
            <Link href="/connections" className="mt-4 flex items-center gap-1 text-[13px] font-medium text-teal-600 hover:underline">
              Explore city connections <ArrowRight className="size-3.5" />
            </Link>
          </Card>

          <Card className="p-5">
            <div className="flex items-center gap-2 text-[13px] font-semibold">
              <Compass className="size-4 text-teal" /> Around you
            </div>
            <p className="mt-1 text-[13px] leading-relaxed text-slate">Choose a 1–10 km radius to see who's reporting, organising and corroborating near you.</p>
            <Button asChild variant="outline" size="sm" className="mt-3">
              <Link href="/around-you">Open Around You</Link>
            </Button>
          </Card>
        </aside>
      </div>
    </div>
  );
}
