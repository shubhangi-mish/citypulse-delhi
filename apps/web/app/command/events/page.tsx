"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { EmptyState, ErrorState, ListSkeleton } from "@/components/ui/states";
import { CmdHeader, Panel } from "@/features/command/ui";
import { api } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { EventCard } from "@/lib/types";

export default function CmdEvents() {
  const q = useQuery({ queryKey: ["events", "cmd"], queryFn: () => api.get<{ items: EventCard[] }>("/events") });
  const [results, setResults] = useState<Record<string, any>>({});
  const analyze = useMutation({ mutationFn: (id: string) => api.post<any>("/agents/analyze-event", { event_id: id }), onSuccess: (r) => setResults((s) => ({ ...s, [r.event_id]: r })) });
  return (
    <div>
      <CmdHeader title="Event coordination" description="Upcoming genuine events and their graph-derived exposure to official alerts and nearby reports." />
      {q.isLoading ? <ListSkeleton /> : q.error ? <ErrorState error={q.error} /> : !q.data?.items.length ? <EmptyState title="No upcoming events" body="Events appear when residents or organisers submit them." /> : (
        <div className="space-y-3">
          {q.data.items.map((e) => (
            <Panel key={e.event_id}>
              <div className="flex flex-wrap items-center gap-3">
                <div className="mr-auto"><Link href={`/events/${e.event_id}`} className="font-medium hover:underline">{e.title}</Link><p className="text-[12.5px] text-slate">{formatDateTime(e.start_time)} · {e.venue} · {e.participant_count} participants · {e.warning_count} alert link(s)</p></div>
                <Button size="sm" variant="outline" loading={analyze.isPending && analyze.variables === e.event_id} onClick={() => analyze.mutate(e.event_id)}>Analyse impact</Button>
              </div>
              {results[e.event_id] && (
                <div className="mt-3 rounded-lg bg-paper-2 p-3 text-[13px]">
                  <p>{results[e.event_id].summary}</p>
                  {results[e.event_id].nearby_issues.map((i: any) => <p key={i.issue_id} className="text-slate">• {i.title} ({i.distance_m} m)</p>)}
                  {results[e.event_id].alert_sources.map((a: any) => <a key={a.warning_id} href={a.source_url} target="_blank" rel="noreferrer" className="block text-teal-600 hover:underline">Source: {a.issuing_authority}</a>)}
                </div>
              )}
            </Panel>
          ))}
        </div>
      )}
    </div>
  );
}
