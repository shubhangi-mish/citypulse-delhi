"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";
import { toast } from "@/components/toaster";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/primitives";
import { ErrorState, ListSkeleton } from "@/components/ui/states";
import { CmdHeader } from "@/features/command/ui";
import { api } from "@/lib/api";
import { timeAgo } from "@/lib/format";

export default function Sources() {
  const q = useQuery({ queryKey: ["sources-status"], queryFn: () => api.get<{ items: any[]; graph_available: boolean }>("/sources/status"), refetchInterval: 15_000 });
  const refresh = useMutation({ mutationFn: (id: string) => api.post(`/sources/${id}/refresh`), onSuccess: () => toast.info("Refresh started in the background.") });
  return (
    <div>
      <CmdHeader title="Source health" description="Freshness and errors for every evaluated source. Sources without permission or machine-readable access are listed, not scraped." />
      {q.isLoading ? <ListSkeleton /> : q.error ? <ErrorState error={q.error} /> : (
        <div className="overflow-hidden rounded-xl border border-line bg-white">
          <table className="w-full text-left text-[13px]">
            <thead className="border-b border-line bg-paper-2/60 text-[12px] uppercase tracking-wider text-slate"><tr><th className="px-4 py-2.5 font-medium">Source</th><th className="px-4 py-2.5 font-medium">Status</th><th className="px-4 py-2.5 font-medium">Last run</th><th className="px-4 py-2.5 font-medium">Records</th><th /></tr></thead>
            <tbody>{q.data!.items.map((s) => (
              <tr key={s.source_id} className="border-b border-line align-top last:border-0">
                <td className="px-4 py-3"><p className="font-medium">{s.name}</p><p className="text-[12px] text-slate">{s.license}</p></td>
                <td className="px-4 py-3"><Badge tone={s.ingestion === "active" ? (s.last_run?.status === "error" ? "critical" : "positive") : "outline"}>{s.ingestion === "active" ? s.last_run?.status ?? "never run" : s.ingestion.replace("_", " ")}</Badge>{s.last_run?.error && <p className="mt-1 max-w-xs text-[11.5px] text-critical">{s.last_run.error}</p>}</td>
                <td className="px-4 py-3 text-slate">{s.last_run ? timeAgo(Date.parse(s.last_run.started_at)) : "—"}{s.last_run && <p className="text-[11.5px]">fetched {s.last_run.records_fetched} · upserted {s.last_run.records_upserted}</p>}</td>
                <td className="px-4 py-3 tabular-nums">{s.graph_records?.toLocaleString("en-IN") ?? "—"}</td>
                <td className="px-4 py-3">{["src_osm", "src_ndma_sachet"].includes(s.source_id) && <Button size="sm" variant="outline" onClick={() => refresh.mutate(s.source_id)}><RefreshCw /> Refresh</Button>}</td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      )}
    </div>
  );
}
