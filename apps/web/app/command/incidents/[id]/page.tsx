"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Bot, Brain, GitBranch, Play, Plus } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { ProvenanceBadge, StatusBadge } from "@/components/badges";
import { toast } from "@/components/toaster";
import { Button } from "@/components/ui/button";
import { Badge, Input, Select } from "@/components/ui/primitives";
import { ErrorState, ListSkeleton } from "@/components/ui/states";
import { ActionCard, type ActionRow } from "@/features/command/actions";
import { CmdHeader, Panel } from "@/features/command/ui";
import { GraphExplorer } from "@/features/graph/graph-explorer";
import { api, ApiError } from "@/lib/api";
import { ACTION_TYPES, ISSUE_CATEGORIES, ISSUE_STATUSES, label, timeAgo } from "@/lib/format";
import type { ExplanationPath } from "@/lib/types";

function PathView({ p }: { p: ExplanationPath }) {
  return (
    <li className="rounded-lg border border-line p-3">
      <p className="text-[13px] font-medium">{p.meaning}</p>
      <p className="mt-1.5 flex flex-wrap items-center gap-1 text-[12px]">
        {p.nodes.map((n, i) => (
          <span key={i} className="flex items-center gap-1">
            <span className="rounded bg-paper-2 px-1.5 py-0.5">{n.name ?? n.label}</span>
            {i < p.rels.length && <span className="font-mono text-[10.5px] text-violet">—{p.rels[i]}→</span>}
          </span>
        ))}
      </p>
      <p className="mt-1 font-mono text-[10.5px] text-slate">{p.query_id}</p>
    </li>
  );
}

export default function Investigate() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();
  const issue = useQuery({ queryKey: ["issue", id], queryFn: () => api.get<any>(`/issues/${id}`) });
  const decisions = useQuery({ queryKey: ["decisions", id], queryFn: () => api.get<{ items: any[] }>(`/agents/issues/${id}/decisions`) });
  const caseId: string | undefined = issue.data?.network?.cases?.[0]?.case_id;
  const kase = useQuery({ queryKey: ["case", caseId], queryFn: () => api.get<any>(`/coordination/cases/${caseId}`), enabled: !!caseId });
  const [result, setResult] = useState<any>(null);
  const [newAction, setNewAction] = useState({ action_type: "publish_community_update", description: "", message: "" });

  const refresh = () => ["issue", "decisions", "case", "cmd-overview"].forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
  const analyze = useMutation({
    mutationFn: () => api.post<any>("/agents/analyze-issue", { issue_id: id }),
    onSuccess: (r) => { setResult(r); refresh(); toast.success(`${r.action_ids.length} proposal(s) for review.`); },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Analysis failed."),
  });
  const createCase = useMutation({
    mutationFn: () => api.post<{ case_id: string }>("/coordination/cases", { title: `Coordination: ${issue.data.title}`.slice(0, 140), case_type: issue.data.category, issue_ids: [id] }),
    onSuccess: () => { toast.success("Case opened."); refresh(); },
  });
  const addAction = useMutation({
    mutationFn: () => api.post(`/coordination/cases/${caseId}/actions`, { action_type: newAction.action_type, description: newAction.description, payload: newAction.message ? { message: newAction.message } : {} }),
    onSuccess: () => { toast.success("Action proposed."); setNewAction({ ...newAction, description: "", message: "" }); refresh(); },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Failed."),
  });
  const setStatus = useMutation({ mutationFn: (s: string) => api.post(`/issues/${id}/status`, { status: s }), onSuccess: refresh });

  if (issue.isLoading) return <ListSkeleton />;
  if (issue.error) return <ErrorState error={issue.error} />;
  const i = issue.data;
  const runs = Object.values((decisions.data?.items ?? []).reduce((acc: any, d: any) => ((acc[d.run_id] ??= []).push(d), acc), {})) as any[][];

  return (
    <div>
      <Link href="/command/incidents" className="mb-4 inline-flex items-center gap-1.5 text-[13px] text-slate hover:text-ink"><ArrowLeft className="size-4" /> Queue</Link>
      <CmdHeader
        title={i.title}
        description={`${label(ISSUE_CATEGORIES, i.category)} · ${i.neighborhood ?? "unmapped"}${i.district ? `, ${i.district}` : ""}${i.road ? ` · ${i.road}` : ""} · ${timeAgo(i.created_at)} · ${i.case_reference}`}
        action={<Button variant="accent" loading={analyze.isPending} onClick={() => analyze.mutate()}><Play /> Run agents</Button>}
      />
      <div className="mb-6 flex flex-wrap items-center gap-2">
        <StatusBadge status={i.status} /><ProvenanceBadge status={i.verification_status} />
        <Badge tone="outline">{i.support_count} affected · {i.network?.follower_count ?? 0} following</Badge>
        <Select className="ml-auto h-9 w-56 text-[13px]" value={i.status} onChange={(e) => setStatus.mutate(e.target.value)} aria-label="Set status">
          {Object.entries(ISSUE_STATUSES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </Select>
      </div>

      <div className="grid gap-6 xl:grid-cols-[1fr_420px]">
        <div className="space-y-6">
          <Panel title="Report"><p className="whitespace-pre-line text-[14.5px] leading-relaxed">{i.description}</p></Panel>

          {result && (
            <Panel title={`Agent analysis · ${result.model_name}`} action={<Badge tone="amber">Evidence: {result.evidence_strength}</Badge>}>
              <p className="text-[14px] leading-relaxed">{result.summary}</p>
              <p className="mt-2 text-[11.5px] text-slate">Evidence strength counts independent graph routes; it is not a calibrated probability.</p>
              {!!result.clarifications.length && <ul className="mt-3 space-y-1 text-[13px] text-[#8a5c17]">{result.clarifications.map((c: string) => <li key={c}>• {c}</li>)}</ul>}
              <div className="mt-4 grid grid-cols-4 gap-2 text-center text-[11.5px]">
                {["Context Agent", "Impact Agent", "Memory Agent", "Coordination Agent"].map((a, k) => (
                  <div key={a} className="rounded-lg border border-line bg-paper-2/50 px-2 py-2"><Bot className="mx-auto mb-1 size-4 text-teal" />{a}<p className="text-slate">{result.tool_calls.filter((t: any) => t.agent === a).length} graph calls</p>{k < 3 && <span className="sr-only">hands off to next</span>}</div>
                ))}
              </div>
              <h3 className="mb-2 mt-5 flex items-center gap-1.5 text-[13px] font-semibold"><GitBranch className="size-4" /> Explanation paths ({result.paths.length})</h3>
              {result.paths.length ? <ul className="space-y-2">{result.paths.map((p: ExplanationPath, k: number) => <PathView key={k} p={p} />)}</ul> : <p className="text-[13px] text-slate">No connected entities found.</p>}
              <h3 className="mb-2 mt-5 flex items-center gap-1.5 text-[13px] font-semibold"><Brain className="size-4" /> Memory retrieved ({result.memory.prior_cases.length} prior case(s))</h3>
              {result.memory.prior_cases.length ? (
                <ul className="space-y-2">
                  {result.memory.prior_cases.map((p: any) => (
                    <li key={p.case_id} className="rounded-lg border border-amber/30 bg-amber-50/50 p-3 text-[13px]">
                      <p className="font-medium">{p.case_title} <span className="font-normal text-slate">({p.case_status})</span></p>
                      <p className="text-[12px] text-slate">Prior report “{p.prior_title}” — connected via {p.routes.map((r: any) => r.via.join("→")).join(" | ")}</p>
                      {p.memories.map((m: any) => <p key={m.memory_id} className="mt-1.5">{m.summary}</p>)}
                    </li>
                  ))}
                </ul>
              ) : <p className="text-[13px] text-slate">No prior coordination reachable through the graph.</p>}
              <h3 className="mb-1 mt-5 font-mono text-[11px] text-slate">Tool calls</h3>
              <ul className="font-mono text-[11px] text-slate">{result.tool_calls.map((t: any, k: number) => <li key={k}>{t.agent}: {t.tool} → {t.rows} rows · {t.query_id}</li>)}</ul>
            </Panel>
          )}

          <Panel title="Coordination" action={!caseId && <Button size="sm" variant="outline" loading={createCase.isPending} onClick={() => createCase.mutate()}><Plus /> Open case</Button>}>
            {!caseId ? (
              <p className="text-[13px] text-slate">No case yet. Run the agents to get proposals, or open a case manually.</p>
            ) : kase.data ? (
              <div className="space-y-3">
                <p className="text-[13.5px]"><b className="font-medium">{kase.data.title}</b> <Badge tone="teal">{kase.data.status}</Badge> <Link className="text-[12.5px] text-teal-600" href={`/command/cases/${caseId}`}>Open case →</Link></p>
                {kase.data.actions.map((a: ActionRow) => <ActionCard key={a.action_id} a={a} invalidate={[["case", caseId], ["issue", id], ["decisions", id]]} />)}
                <div className="rounded-xl border border-dashed border-line-strong p-3">
                  <p className="mb-2 text-[12.5px] font-medium">Propose an action</p>
                  <div className="grid gap-2 sm:grid-cols-2">
                    <Select className="h-9 text-[13px]" value={newAction.action_type} onChange={(e) => setNewAction({ ...newAction, action_type: e.target.value })}>{Object.entries(ACTION_TYPES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</Select>
                    <Input className="h-9 text-[13px]" placeholder="Description" value={newAction.description} onChange={(e) => setNewAction({ ...newAction, description: e.target.value })} />
                    <Input className="h-9 text-[13px] sm:col-span-2" placeholder="Message to residents (for updates/requests)" value={newAction.message} onChange={(e) => setNewAction({ ...newAction, message: e.target.value })} />
                  </div>
                  <Button size="sm" className="mt-2" disabled={newAction.description.length < 3} loading={addAction.isPending} onClick={() => addAction.mutate()}>Propose</Button>
                </div>
              </div>
            ) : <ListSkeleton rows={1} />}
          </Panel>

          <Panel title="Graph context"><GraphExplorer initialFocus={id} heightClass="h-[460px]" /></Panel>
        </div>

        <div className="space-y-6">
          <Panel title={`Related reports (${i.related.length})`}>
            {i.related.length ? <ul className="space-y-2">{i.related.map((r: any) => <li key={r.issue_id} className="text-[13px]"><Link href={`/command/incidents/${r.issue_id}`} className="font-medium hover:underline">{r.title}</Link><p className="text-[12px] text-slate">score {r.score.toFixed(2)} · {Math.round(r.distance_m)} m{r.shared_roads[0] ? ` · ${r.shared_roads[0].name}` : ""}</p></li>)}</ul> : <p className="text-[13px] text-slate">None.</p>}
          </Panel>
          <Panel title="Known assets & operators">
            {i.assets.length ? <ul className="space-y-2 text-[13px]">{i.assets.map((a: any) => <li key={a.asset_id + a.relationship}><b className="font-medium">{a.name}</b> <span className="text-slate">{a.relationship} {a.distance_m ? `${a.distance_m} m` : ""}</span>{a.organizations.map((o: any) => <p key={o.name} className="text-[12px] text-slate">{o.relationship} {o.name} ({o.basis})</p>)}</li>)}</ul> : <p className="text-[13px] text-slate">None within 300 m.</p>}
          </Panel>
          <Panel title="Official alerts & events">
            {i.warnings.map((w: any) => <p key={w.warning_id} className="text-[13px]">⚠ <Link href={`/warnings/${w.warning_id}`} className="hover:underline">{w.title}</Link></p>)}
            {i.nearby_events.map((e: any) => <p key={e.event_id} className="text-[13px]">📅 <Link href={`/events/${e.event_id}`} className="hover:underline">{e.title}</Link> · {e.distance_m} m</p>)}
            {!i.warnings.length && !i.nearby_events.length && <p className="text-[13px] text-slate">None connected.</p>}
          </Panel>
          <Panel title="Decision history">
            {runs.length ? runs.map((run) => (
              <div key={run[0].run_id} className="mb-3 border-b border-line pb-3 last:border-0">
                <p className="text-[12px] text-slate">{timeAgo(run[0].created_at)} · {run.find((d) => d.decision_type === "coordination_recommendation")?.model_name}</p>
                <ul className="mt-1 space-y-1">{run.map((d) => <li key={d.decision_id} className="text-[12.5px]"><b className="font-medium">{d.agent_name}</b> <Badge tone={d.review_status === "approved" ? "positive" : d.review_status === "pending_review" ? "amber" : "neutral"}>{d.review_status}</Badge><p className="text-slate">{d.rationale}</p></li>)}</ul>
              </div>
            )) : <p className="text-[13px] text-slate">No agent runs yet.</p>}
          </Panel>
        </div>
      </div>
    </div>
  );
}
