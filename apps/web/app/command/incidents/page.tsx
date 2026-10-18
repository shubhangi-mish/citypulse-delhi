"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { StatusBadge } from "@/components/badges";
import { Chip } from "@/components/ui/primitives";
import { EmptyState, ErrorState, ListSkeleton } from "@/components/ui/states";
import { CmdHeader } from "@/features/command/ui";
import { api } from "@/lib/api";
import { ISSUE_CATEGORIES, label, timeAgo } from "@/lib/format";
import type { IssueCard } from "@/lib/types";

const FILTERS = [["", "All open"], ["submitted", "Submitted"], ["community_corroborated", "Corroborated"], ["coordination_in_progress", "In coordination"], ["resolved_reporter_confirmed", "Resolved"]];

export default function Incidents() {
  const [status, setStatus] = useState("");
  const q = useQuery({ queryKey: ["cmd-issues", status], queryFn: () => api.get<{ items: IssueCard[] }>("/issues", { status, limit: 200 }) });
  return (
    <div>
      <CmdHeader title="Incident queue" description="Genuine community reports. Select one to investigate its graph context and run the agents." />
      <div className="mb-4 flex flex-wrap gap-2">{FILTERS.map(([v, l]) => <Chip key={v} active={status === v} onClick={() => setStatus(v)}>{l}</Chip>)}</div>
      {q.isLoading ? <ListSkeleton /> : q.error ? <ErrorState error={q.error} /> : !q.data?.items.length ? (
        <EmptyState title="No reports in this state" body="When residents submit reports through CityPulse they appear here." />
      ) : (
        <div className="overflow-hidden rounded-xl border border-line bg-white">
          <table className="w-full text-left text-[13.5px]">
            <thead className="border-b border-line bg-paper-2/60 text-[12px] uppercase tracking-wider text-slate">
              <tr><th className="px-4 py-2.5 font-medium">Report</th><th className="hidden px-4 py-2.5 font-medium md:table-cell">Area</th><th className="px-4 py-2.5 font-medium">Affected</th><th className="px-4 py-2.5 font-medium">Status</th><th className="hidden px-4 py-2.5 font-medium sm:table-cell">Age</th></tr>
            </thead>
            <tbody>
              {q.data.items.map((i) => (
                <tr key={i.issue_id} className="border-b border-line last:border-0 hover:bg-paper-2/50">
                  <td className="px-4 py-3"><Link href={`/command/incidents/${i.issue_id}`} className="font-medium hover:text-teal-600">{i.title}</Link><p className="text-[12px] text-slate">{label(ISSUE_CATEGORIES, i.category)}</p></td>
                  <td className="hidden px-4 py-3 text-slate md:table-cell">{i.neighborhood ?? "—"}</td>
                  <td className="px-4 py-3 tabular-nums">{i.support_count}</td>
                  <td className="px-4 py-3"><StatusBadge status={i.status} /></td>
                  <td className="hidden px-4 py-3 text-slate sm:table-cell">{timeAgo(i.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
