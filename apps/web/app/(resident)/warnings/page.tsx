"use client";

import { useQuery } from "@tanstack/react-query";
import { ShieldCheck } from "lucide-react";
import { useState } from "react";
import { Chip } from "@/components/ui/primitives";
import { EmptyState, ErrorState, ListSkeleton, PageHeader } from "@/components/ui/states";
import { WarningFeedCard } from "@/features/feed/feed-card";
import { api } from "@/lib/api";
import { timeAgo } from "@/lib/format";
import type { WarningCard } from "@/lib/types";

export default function WarningsPage() {
  const [expired, setExpired] = useState(false);
  const q = useQuery({ queryKey: ["warnings", expired], queryFn: () => api.get<{ items: WarningCard[] }>("/warnings", { include_expired: expired }) });
  const src = useQuery({ queryKey: ["sources-status"], queryFn: () => api.get<{ items: any[] }>("/sources/status") });
  const sachet = src.data?.items.find((s) => s.source_id === "src_ndma_sachet");
  return (
    <div className="container-page max-w-4xl py-10">
      <PageHeader
        eyebrow="Warnings & advisories"
        title="Official alerts for Delhi"
        description="Alerts come from NDMA's SACHET Common Alerting Protocol feed, which carries warnings from IMD and State Disaster Management Authorities. CityPulse links every alert to its original source and never writes its own emergency instructions."
      />
      <div className="mb-6 flex flex-wrap items-center gap-3">
        <Chip active={!expired} onClick={() => setExpired(false)}>Active</Chip>
        <Chip active={expired} onClick={() => setExpired(true)}>Include expired</Chip>
        {sachet?.last_success_at && <span className="ml-auto text-[12.5px] text-slate">Feed last checked {timeAgo(Date.parse(sachet.last_success_at))}</span>}
      </div>
      {q.isLoading ? (
        <ListSkeleton />
      ) : q.error ? (
        <ErrorState error={q.error} onRetry={() => q.refetch()} />
      ) : q.data?.items.length ? (
        <div className="space-y-3">{q.data.items.map((w) => <WarningFeedCard key={w.warning_id} item={w} />)}</div>
      ) : (
        <EmptyState
          icon={<ShieldCheck />}
          title={expired ? "No Delhi alerts recorded yet" : "No active official alerts for Delhi"}
          body="CityPulse checks the SACHET feed every 15 minutes and keeps only alerts whose area resolves to Delhi districts or neighbourhoods. Nothing is shown unless an official source published it."
        />
      )}
    </div>
  );
}
