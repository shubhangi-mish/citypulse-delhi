"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { Badge } from "@/components/ui/primitives";
import { EmptyState, ErrorState, ListSkeleton } from "@/components/ui/states";
import { CmdHeader, Panel } from "@/features/command/ui";
import { api } from "@/lib/api";
import { timeAgo } from "@/lib/format";

export default function Agents() {
  const q = useQuery({ queryKey: ["agent-activity"], queryFn: () => api.get<{ items: any[] }>("/agents/activity") });
  const [open, setOpen] = useState<string | null>(null);
  const detail = useQuery({ queryKey: ["decision", open], queryFn: () => api.get<any>(`/agents/decisions/${open}`), enabled: !!open });
  return (
    <div>
      <CmdHeader title="Agent activity" description="Every agent decision is a node in the graph, chained Context → Impact → Memory → Coordination with INFORMED edges." />
      <div className="grid gap-6 xl:grid-cols-[1fr_460px]">
        <div>
          {q.isLoading ? <ListSkeleton /> : q.error ? <ErrorState error={q.error} /> : !q.data?.items.length ? <EmptyState title="No agent runs yet" body="Open a report in the incident queue and choose Run agents." /> : (
            <ul className="space-y-2">
              {q.data.items.map((d) => (
                <li key={d.decision_id}>
                  <button onClick={() => setOpen(d.decision_id)} className={`w-full rounded-xl border bg-white p-3.5 text-left hover:border-line-strong ${open === d.decision_id ? "border-teal" : "border-line"}`}>
                    <div className="flex items-center gap-2"><b className="text-[13.5px] font-medium">{d.agent_name}</b><Badge tone="neutral">{d.decision_type}</Badge><Badge tone={d.review_status === "pending_review" ? "amber" : d.review_status === "approved" ? "positive" : "outline"}>{d.review_status}</Badge><span className="ml-auto text-[12px] text-slate">{timeAgo(d.created_at)}</span></div>
                    <p className="mt-1 text-[13px] text-slate">{d.rationale}</p>
                    <p className="mt-1 text-[12px]">on “{d.issue_title}”</p>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
        <Panel title="Decision trace">
          {!open ? <p className="text-[13px] text-slate">Select a decision to see its inputs, graph queries, sources and hand-offs.</p> : detail.isLoading ? <ListSkeleton rows={1} /> : detail.data ? (
            <div className="space-y-3 text-[13px]">
              <p><b>{detail.data.agent_name}</b> · {detail.data.model_name} · run <span className="font-mono text-[11.5px]">{detail.data.run_id}</span></p>
              <p>{detail.data.rationale}</p>
              <p className="text-[12.5px] text-slate">Hand-off: {detail.data.handoff.previous_agent ?? "start"} → <b>{detail.data.agent_name}</b> → {detail.data.handoff.next_agent ?? "end"}</p>
              <div><p className="font-medium">Considered</p>{detail.data.considered.map((c: any) => <p key={c.id} className="text-slate">{c.role}: <Link className="text-ink hover:underline" href={c.label === "Issue" ? `/command/incidents/${c.id}` : `/command/graph?focus=${c.id}`}>{c.name}</Link></p>)}</div>
              <div><p className="font-medium">Based on sources</p>{detail.data.sources.map((s: any) => <p key={s.source_id} className="text-slate">{s.name} — {s.license}</p>)}</div>
              {!!detail.data.memories.length && <div><p className="font-medium">Used memory</p>{detail.data.memories.map((m: any) => <p key={m.memory_id} className="text-slate">{m.summary}</p>)}</div>}
              {!!detail.data.actions.length && <div><p className="font-medium">Produced actions</p>{detail.data.actions.map((a: any) => <p key={a.action_id} className="text-slate">{a.action_type} — {a.status}</p>)}</div>}
              <details><summary className="cursor-pointer font-medium">Raw trace (queries, paths)</summary><pre className="mt-2 max-h-96 overflow-auto rounded-lg bg-navy-950 p-3 text-[11px] text-white/80">{JSON.stringify(detail.data.trace, null, 2)}</pre></details>
            </div>
          ) : null}
        </Panel>
      </div>
    </div>
  );
}
