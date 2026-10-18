"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Brain } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { StatusBadge } from "@/components/badges";
import { Badge, Select } from "@/components/ui/primitives";
import { ErrorState, ListSkeleton } from "@/components/ui/states";
import { ActionCard, type ActionRow } from "@/features/command/actions";
import { CmdHeader, Panel } from "@/features/command/ui";
import { api } from "@/lib/api";
import { formatDateTime, timeAgo } from "@/lib/format";

export default function CaseDetail() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["case", id], queryFn: () => api.get<any>(`/coordination/cases/${id}`) });
  const mem = useQuery({ queryKey: ["case-memory", id], queryFn: () => api.get<{ memories: any[] }>(`/agents/memory/${id}`) });
  const status = useMutation({ mutationFn: (s: string) => api.post(`/coordination/cases/${id}/status`, { status: s }), onSuccess: () => qc.invalidateQueries({ queryKey: ["case", id] }) });
  if (q.isLoading) return <ListSkeleton />;
  if (q.error) return <ErrorState error={q.error} />;
  const c = q.data;
  return (
    <div>
      <Link href="/command/cases" className="mb-4 inline-flex items-center gap-1.5 text-[13px] text-slate hover:text-ink"><ArrowLeft className="size-4" /> Cases</Link>
      <CmdHeader
        title={c.title}
        description={`Opened ${formatDateTime(c.created_at)} · ${c.participant_count} resident volunteer(s)${c.assigned_to ? ` · assigned to ${c.assigned_to}` : ""}`}
        action={<Select className="h-9 w-44 text-[13px]" value={c.status} onChange={(e) => status.mutate(e.target.value)}>{["proposed", "open", "in_progress", "resolved", "closed"].map((s) => <option key={s} value={s} disabled={s === "proposed"}>{s.replace("_", " ")}</option>)}</Select>}
      />
      <div className="grid gap-6 xl:grid-cols-[1fr_400px]">
        <div className="space-y-6">
          <Panel title="Reports in this case">
            <ul className="space-y-2">{c.issues.map((i: any) => <li key={i.issue_id} className="flex items-center justify-between gap-2 text-[13.5px]"><Link href={`/command/incidents/${i.issue_id}`} className="font-medium hover:underline">{i.title}</Link><span className="flex items-center gap-2 text-slate">{i.neighborhood} <StatusBadge status={i.status} /></span></li>)}</ul>
          </Panel>
          <Panel title={`Actions (${c.actions.length})`}>
            <div className="space-y-3">{c.actions.length ? c.actions.map((a: ActionRow) => <ActionCard key={a.action_id} a={a} invalidate={[["case", id], ["case-memory", id]]} />) : <p className="text-[13px] text-slate">No actions yet.</p>}</div>
          </Panel>
        </div>
        <div className="space-y-6">
          <Panel title="Persistent memory">
            {mem.data?.memories.length ? (
              <ul className="space-y-3">{mem.data.memories.map((m) => (
                <li key={m.memory_id} className="rounded-lg border border-amber/30 bg-amber-50/50 p-3 text-[13px]">
                  <p className="flex items-center gap-1.5 text-[11.5px] text-slate"><Brain className="size-3.5" /> {m.memory_id} · {timeAgo(m.created_at)}</p>
                  <p className="mt-1">{m.summary}</p>
                  {!!m.reused_by.length && <p className="mt-1.5 text-[12px] text-teal-600">Reused by {m.reused_by.length} later agent decision(s)</p>}
                </li>
              ))}</ul>
            ) : <p className="text-[13px] text-slate">Memory is written when a coordinator records an action's outcome.</p>}
          </Panel>
          <Panel title="Agent decisions">
            {c.decisions.length ? <ul className="space-y-2">{c.decisions.map((d: any) => <li key={d.decision_id} className="text-[12.5px]"><b className="font-medium">{d.agent_name}</b> <Badge tone="neutral">{d.review_status}</Badge><p className="text-slate">{d.rationale}</p></li>)}</ul> : <p className="text-[13px] text-slate">None.</p>}
          </Panel>
        </div>
      </div>
    </div>
  );
}
