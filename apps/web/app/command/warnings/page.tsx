"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { SeverityBadge } from "@/components/badges";
import { EmptyState, ErrorState, ListSkeleton } from "@/components/ui/states";
import { CmdHeader } from "@/features/command/ui";
import { api } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { WarningCard } from "@/lib/types";

export default function CmdWarnings() {
  const q = useQuery({ queryKey: ["warnings", "cmd"], queryFn: () => api.get<{ items: WarningCard[] }>("/warnings", { include_expired: true }) });
  return (
    <div>
      <CmdHeader title="Warning intelligence" description="Official CAP alerts ingested from NDMA SACHET and the city entities they connect to. CityPulse never writes its own emergency instructions." />
      {q.isLoading ? <ListSkeleton /> : q.error ? <ErrorState error={q.error} /> : !q.data?.items.length ? <EmptyState title="No Delhi alerts ingested yet" body="The SACHET feed is checked every 15 minutes; only alerts whose area resolves to Delhi are kept." /> : (
        <div className="overflow-hidden rounded-xl border border-line bg-white">
          <table className="w-full text-left text-[13.5px]">
            <thead className="border-b border-line bg-paper-2/60 text-[12px] uppercase tracking-wider text-slate"><tr><th className="px-4 py-2.5 font-medium">Alert</th><th className="px-4 py-2.5 font-medium">Severity</th><th className="px-4 py-2.5 font-medium">Areas</th><th className="px-4 py-2.5 font-medium">Events</th><th className="px-4 py-2.5 font-medium">Expires</th></tr></thead>
            <tbody>{q.data.items.map((w) => (
              <tr key={w.warning_id} className="border-b border-line last:border-0">
                <td className="px-4 py-3"><Link href={`/warnings/${w.warning_id}`} className="font-medium hover:underline">{w.title}</Link><p className="text-[12px] text-slate">{w.issuing_authority}</p></td>
                <td className="px-4 py-3"><SeverityBadge severity={w.severity} /></td>
                <td className="px-4 py-3 tabular-nums">{w.affected_neighborhood_count}</td>
                <td className="px-4 py-3 tabular-nums">{w.affected_event_count}</td>
                <td className="px-4 py-3 text-slate">{w.active ? formatDateTime(w.expires_at) : "expired"}</td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      )}
    </div>
  );
}
