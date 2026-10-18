"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { Badge, Chip } from "@/components/ui/primitives";
import { EmptyState, ErrorState, ListSkeleton } from "@/components/ui/states";
import { CmdHeader } from "@/features/command/ui";
import { api } from "@/lib/api";
import { timeAgo } from "@/lib/format";
import type { CaseCard } from "@/lib/types";

export default function Cases() {
  const [status, setStatus] = useState("");
  const q = useQuery({ queryKey: ["cases", status], queryFn: () => api.get<{ items: CaseCard[] }>("/coordination/cases", { status }) });
  return (
    <div>
      <CmdHeader title="Coordination cases" description="Cases group related reports and the actions taken on them. 'Proposed' cases were opened by the Coordination Agent and await review." />
      <div className="mb-4 flex flex-wrap gap-2">{["", "proposed", "open", "in_progress", "resolved", "closed"].map((s) => <Chip key={s} active={status === s} onClick={() => setStatus(s)}>{s ? s.replace("_", " ") : "All"}</Chip>)}</div>
      {q.isLoading ? <ListSkeleton /> : q.error ? <ErrorState error={q.error} /> : !q.data?.items.length ? <EmptyState title="No cases yet" body="Run the agents on a report or open a case from the incident queue." /> : (
        <div className="grid gap-3 md:grid-cols-2">
          {q.data.items.map((c) => (
            <Link key={c.case_id} href={`/command/cases/${c.case_id}`} className="rounded-xl border border-line bg-white p-4 hover:border-line-strong">
              <div className="flex items-start justify-between gap-2"><p className="font-medium">{c.title}</p><Badge tone={c.status === "proposed" ? "amber" : "teal"}>{c.status}</Badge></div>
              <p className="mt-1 text-[12.5px] text-slate">{c.issues.length} report(s) · {c.action_count} action(s){c.pending_actions ? ` · ${c.pending_actions} awaiting review` : ""} · updated {timeAgo(c.updated_at)}</p>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
