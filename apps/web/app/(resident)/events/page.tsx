"use client";

import { useQuery } from "@tanstack/react-query";
import { CalendarPlus } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Chip, Select } from "@/components/ui/primitives";
import { EmptyState, ErrorState, ListSkeleton, PageHeader } from "@/components/ui/states";
import { EventFeedCard } from "@/features/feed/feed-card";
import { NeighborhoodPicker } from "@/features/neighborhood/neighborhood-picker";
import { useProfile } from "@/hooks/use-profile";
import { api } from "@/lib/api";
import { EVENT_CATEGORIES } from "@/lib/format";
import type { EventCard } from "@/lib/types";

const RANGES = {
  any: "Any time",
  week: "Next 7 days",
  weekend: "This weekend",
  month: "Next 30 days",
} as const;

function range(r: keyof typeof RANGES): { from_ms?: number; to_ms?: number } {
  const now = Date.now();
  if (r === "week") return { from_ms: now, to_ms: now + 7 * 864e5 };
  if (r === "month") return { from_ms: now, to_ms: now + 30 * 864e5 };
  if (r === "weekend") {
    const d = new Date();
    const day = d.getDay();
    const sat = new Date(d);
    sat.setDate(d.getDate() + ((6 - day + 7) % 7));
    sat.setHours(0, 0, 0, 0);
    const end = new Date(sat);
    end.setDate(sat.getDate() + 2);
    return { from_ms: Math.max(now, sat.getTime() - (day === 0 ? 864e5 : 0)), to_ms: end.getTime() };
  }
  return {};
}

export default function EventsPage() {
  const { profile } = useProfile();
  const [category, setCategory] = useState("");
  const [when, setWhen] = useState<keyof typeof RANGES>("any");
  const [free, setFree] = useState<"" | "true" | "false">("");
  const [setting, setSetting] = useState("");
  const [nearMe, setNearMe] = useState(false);
  const [nbh, setNbh] = useState<{ id: string; name: string } | null>(null);
  const q = useQuery({
    queryKey: ["events", category, when, free, setting, nearMe, nbh?.id],
    queryFn: () =>
      nearMe && profile
        ? api.get<{ items: EventCard[] }>("/nearby/events", { radius_km: 5 })
        : api.get<{ items: EventCard[] }>("/events", { category, ...range(when), is_free: free || undefined, setting, neighborhood_id: nbh?.id }),
  });
  const items = (q.data?.items ?? []).filter((e) => !nearMe || ((!category || e.category === category) && (!free || String(e.is_free) === free) && (!setting || e.setting === setting)));

  return (
    <div className="container-page max-w-5xl py-10">
      <PageHeader
        eyebrow="Events"
        title="Things happening in Delhi"
        description="Community meetings, cleanups, workshops, markets and more — shared by residents and organisers, labelled with where they came from."
        action={
          <Button asChild variant="accent">
            <Link href="/events/create">
              <CalendarPlus /> Share an event
            </Link>
          </Button>
        }
      />
      <div className="mb-4 flex flex-wrap gap-2">
        {(Object.keys(RANGES) as (keyof typeof RANGES)[]).map((r) => (
          <Chip key={r} active={when === r && !nearMe} onClick={() => { setWhen(r); setNearMe(false); }}>
            {RANGES[r]}
          </Chip>
        ))}
        {profile && (
          <Chip active={nearMe} onClick={() => setNearMe(!nearMe)}>
            Within 5 km of home
          </Chip>
        )}
      </div>
      <div className="mb-6 grid gap-3 sm:grid-cols-2 md:grid-cols-4">
        <Select value={category} onChange={(e) => setCategory(e.target.value)} aria-label="Category">
          <option value="">All categories</option>
          {Object.entries(EVENT_CATEGORIES).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </Select>
        <Select value={free} onChange={(e) => setFree(e.target.value as any)} aria-label="Price">
          <option value="">Free or paid</option>
          <option value="true">Free</option>
          <option value="false">Paid</option>
        </Select>
        <Select value={setting} onChange={(e) => setSetting(e.target.value)} aria-label="Setting">
          <option value="">Indoor or outdoor</option>
          <option value="indoor">Indoor</option>
          <option value="outdoor">Outdoor</option>
          <option value="mixed">Mixed</option>
        </Select>
        {!nearMe && <NeighborhoodPicker value={nbh} onChange={setNbh} homeLabel={undefined} />}
      </div>
      {q.isLoading ? (
        <ListSkeleton />
      ) : q.error ? (
        <ErrorState error={q.error} onRetry={() => q.refetch()} />
      ) : items.length ? (
        <div className="grid gap-3 md:grid-cols-2">
          {items.map((e) => (
            <EventFeedCard key={e.event_id} item={e} />
          ))}
        </div>
      ) : (
        <EmptyState
          icon={<CalendarPlus />}
          title="No upcoming events match"
          body="CityPulse only lists genuine events submitted by residents and organisers — no placeholder listings. Hosting something? Share it."
          action={
            <Button asChild variant="outline">
              <Link href="/events/create">Share an event</Link>
            </Button>
          }
        />
      )}
    </div>
  );
}
