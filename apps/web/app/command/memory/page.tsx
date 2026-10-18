"use client";

import { useQuery } from "@tanstack/react-query";
import { Brain } from "lucide-react";
import Link from "next/link";
import { EmptyState, ErrorState, ListSkeleton } from "@/components/ui/states";
import { CmdHeader } from "@/features/command/ui";
import { api } from "@/lib/api";
import { formatDateTime } from "@/lib/format";

export default function Memory() {
  const q = useQuery({ queryKey: ["memory-all"], queryFn: () => api.get<{ items: any[] }>("/agents/memory") });
  return (
    <div>
      <CmdHeader title="City memory" description="AgentMemory nodes written by the Memory Agent when coordinators record real outcomes. They persist in FalkorDB across restarts and are retrieved by graph traversal (Query F) for new, connected reports." />
      {q.isLoading ? <ListSkeleton /> : q.error ? <ErrorState error={q.error} /> : !q.data?.items.length ? (
        <EmptyState icon={<Brain />} title="No memories yet" body="Approve an action on a case and record what happened. That outcome becomes memory the agents reuse." />
      ) : (
        <ul className="space-y-3">
          {q.data.items.map((m) => (
            <li key={m.memory_id} className="rounded-xl border border-line bg-white p-4">
              <div className="flex flex-wrap items-center gap-2 text-[12px] text-slate"><Brain className="size-4 text-amber" /> {formatDateTime(m.created_at)} · <Link href={`/command/cases/${m.case_id}`} className="text-ink hover:underline">{m.case_title}</Link><span className="ml-auto">reused {m.times_reused}×</span></div>
              <p className="mt-2 text-[14px] leading-relaxed">{m.summary}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
