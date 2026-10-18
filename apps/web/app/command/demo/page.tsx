"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, Bot, Brain, Check, CircleDashed, Eye, Flag, Megaphone, Mic2, Play, RotateCcw, Trash2, UserX, X } from "lucide-react";
import Link from "next/link";
import { toast } from "@/components/toaster";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/primitives";
import { ErrorState, ListSkeleton } from "@/components/ui/states";
import { CmdHeader, Panel } from "@/features/command/ui";
import { GraphExplorer } from "@/features/graph/graph-explorer";
import { api, ApiError } from "@/lib/api";
import { cn, formatDateTime, timeAgo } from "@/lib/format";

interface Persona {
  resident_id: string;
  key: string;
  name: string;
  profession: string;
  category: string;
  open_to_gigs: boolean;
  neighborhood: string;
  inbox: { kind: string; message: string; at: string }[];
  unread: number;
}
interface Candidate { name: string; profession: string; neighborhood: string; distance: string; score?: number; reasons?: string[]; reason?: string }
interface State {
  seeded: boolean;
  organizer?: { name: string; is_real: boolean; unread: number; inbox: { kind: string; message: string }[] } | null;
  personas: Persona[];
  steps: { seeded?: boolean; cancelled?: boolean; agents_acted?: boolean; complaint?: boolean; resolved?: boolean };
  event?: {
    event_id: string;
    title: string;
    start_time: number;
    performer_gap?: boolean;
    performers: { display_name: string | null; profession: string; status: string; role: string }[];
    named_participants: string[];
    invites: { key: string; name: string; profession: string; status: string; score: number; reasons: string[] }[];
    updates: { discussion_id: string; body: string; created_at: number; kind: string }[];
  };
  decisions: { decision_id: string; agent_name: string; decision_type: string; rationale: string; review_status: string; created_at: number; run_id: string }[];
  case: { case_id: string; title: string; status: string } | null;
  complaint: { issue_id: string; title: string; status: string } | null;
  memory: { memory_id: string; summary: string }[];
}

const STEPS = [
  { k: "seeded", label: "Scenario loaded", icon: Flag },
  { k: "cancelled", label: "Headliner cancels", icon: UserX },
  { k: "agents_acted", label: "Agents act", icon: Bot },
  { k: "complaint", label: "Attendee complains", icon: Megaphone },
  { k: "resolved", label: "Artist steps in", icon: Mic2 },
] as const;

export default function DemoPage() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["demo-state"], queryFn: () => api.get<State>("/demo/state"), refetchInterval: 6000 });
  const impactId = q.data?.decisions.find((d) => d.decision_type === "impact_assessment")?.decision_id;
  const impact = useQuery({ queryKey: ["demo-impact", impactId], queryFn: () => api.get<any>(`/graph/explanations/${impactId}`), enabled: !!impactId });
  const refresh = () => ["demo-state", "demo-impact", "cmd-overview", "events", "agent-activity"].forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
  const onError = (e: unknown) => toast.error(e instanceof ApiError ? e.message : "Failed.");

  const seed = useMutation({ mutationFn: () => api.post("/demo/seed"), onSuccess: () => { toast.success("Scenario loaded: 7 synthetic personas, 2 events."); refresh(); }, onError });
  const reset = useMutation({ mutationFn: () => api.post("/demo/reset"), onSuccess: () => { toast.info("Scenario reset."); refresh(); }, onError });
  const viewAs = useMutation({
    mutationFn: (key: string) => api.post<{ event_id: string | null }>("/demo/impersonate", { persona_key: key }),
    onSuccess: (r) => {
      qc.invalidateQueries();
      window.location.href = r.event_id ? `/events/${r.event_id}` : "/";
    },
    onError,
  });
  const remove = useMutation({ mutationFn: () => api.del("/demo"), onSuccess: () => { toast.info("All demo data removed."); refresh(); }, onError });
  const cancel = useMutation({
    mutationFn: () => api.post<any>("/demo/cancel-artist"),
    onSuccess: (r) => { toast.success(`Agents acted: ${r.executed.length} action(s) executed under organiser autopilot.`); refresh(); },
    onError,
  });
  const complain = useMutation({ mutationFn: () => api.post("/demo/file-complaint"), onSuccess: () => { toast.success("Complaint filed and linked to the case."); refresh(); }, onError });
  const respond = useMutation({
    mutationFn: (v: { persona_key: string; accept: boolean }) => api.post<any>("/demo/respond", v),
    onSuccess: (r) => { toast.success(r.accepted ? `${r.who} stepped in!` : "Declined."); refresh(); },
    onError,
  });

  if (q.isLoading) return <ListSkeleton />;
  if (q.error) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  const d = q.data!;
  const cand = impact.data?.trace?.impact?.candidates as { eligible: Candidate[]; excluded: Candidate[]; query_id: string } | undefined;
  const impactDecision = d.decisions.find((x) => x.decision_type === "impact_assessment");
  const runDecisions = d.decisions.filter((x) => x.run_id === d.decisions[0]?.run_id).sort((a, b) => ["event_context", "impact_assessment", "memory_retrieval", "coordination_recommendation"].indexOf(a.decision_type) - ["event_context", "impact_assessment", "memory_retrieval", "coordination_recommendation"].indexOf(b.decision_type));
  const excludedNames = new Set((cand?.excluded ?? []).map((c) => c.name));

  function status(p: Persona) {
    const perf = d.event?.performers.find((x) => x.display_name === p.name);
    const inv = d.event?.invites.find((x) => x.key === p.key);
    if (perf?.status === "cancelled") return { tone: "critical", text: "Cancelled performer" } as const;
    if (perf?.role === "replacement") return { tone: "positive", text: "Stepped in as replacement" } as const;
    if (perf?.role === "headliner") return { tone: "teal", text: p.key === "kabir" ? "Booked elsewhere (double-booked)" : "Booked headliner" } as const;
    if (inv) return { tone: inv.status === "pending" ? "amber" : inv.status === "accepted" ? "positive" : "outline", text: `Invited · ${inv.status}` } as const;
    if (excludedNames.has(p.name)) return { tone: "outline", text: "Excluded by agents: double-booked" } as const;
    if (d.event?.named_participants.includes(p.name)) return { tone: "violet", text: "Attending the event" } as const;
    return { tone: "neutral", text: p.key === "meher" ? "Organiser (autopilot on)" : "—" } as const;
  }

  return (
    <div>
      <CmdHeader
        title="Demo scenario: the headliner cancels"
        description="People, professions, an event, a complaint and a solution — connected in FalkorDB and acted on by agents. Everything here is synthetic and flagged demo=true; one click removes it."
        action={d.seeded ? (
          <div className="flex gap-2">
            <Button size="sm" variant="outline" loading={reset.isPending} onClick={() => reset.mutate()}><RotateCcw /> Reset</Button>
            <Button size="sm" variant="ghost" loading={remove.isPending} onClick={() => confirm("Remove all demo personas, events, cases and agent records?") && remove.mutate()}><Trash2 /> Remove demo data</Button>
          </div>
        ) : undefined}
      />

      <div className="mb-6 rounded-xl border border-amber/40 bg-amber-50 p-3.5 text-[13px] text-[#6f4b13]">
        <b>Synthetic demo data.</b> The seven people are fictional personas, the neighbourhoods are real OpenStreetMap places, and every action below really runs: graph writes, agent decisions and in-app notifications.
      </div>

      <ol className="mb-8 grid gap-2 sm:grid-cols-5">
        {STEPS.map((s, i) => {
          const done = !!(d.steps as any)[s.k];
          return (
            <li key={s.k} className={cn("flex items-center gap-2.5 rounded-xl border px-3.5 py-3 text-[13px]", done ? "border-teal/40 bg-teal-50 text-teal-600" : "border-line bg-white text-slate")}>
              {done ? <Check className="size-4" /> : <CircleDashed className="size-4" />}
              <span><span className="block text-[11px] opacity-70">Step {i + 1}</span>{s.label}</span>
            </li>
          );
        })}
      </ol>

      {!d.seeded ? (
        <Panel>
          <p className="text-[14px]">Load the scenario to create seven synthetic residents (three artists, an organiser, two attendees and a double-booked comedian) and two events in real Delhi neighbourhoods.</p>
          <Button className="mt-4" variant="accent" loading={seed.isPending} onClick={() => seed.mutate()}><Play /> Load the scenario</Button>
        </Panel>
      ) : (
        <div className="grid gap-6 xl:grid-cols-[1fr_440px]">
          <div className="space-y-6">
            <Panel title="Story controls">
              {d.event && <p className="mb-3 text-[13.5px]"><Link className="font-medium text-teal-600 hover:underline" href={`/events/${d.event.event_id}`}>{d.event.title}</Link> · {formatDateTime(d.event.start_time)} · {d.event.named_participants.length} attending</p>}
              <div className="flex flex-wrap gap-2">
                <Button variant="danger" disabled={d.steps.cancelled} loading={cancel.isPending} onClick={() => cancel.mutate()}><UserX /> 1 · Aarav (headliner) cancels</Button>
                <Button variant="outline" disabled={!d.steps.cancelled || d.steps.complaint} loading={complain.isPending} onClick={() => complain.mutate()}><Megaphone /> 2 · Rohan files a complaint</Button>
              </div>
              {d.event?.invites.some((i) => i.status === "pending") && (
                <div className="mt-4 border-t border-line pt-4">
                  <p className="mb-2 text-[13px] font-medium">3 · The invited artists reply (acting as each persona)</p>
                  <div className="space-y-2">
                    {d.event.invites.filter((i) => i.status === "pending").map((i) => (
                      <div key={i.key} className="flex flex-wrap items-center gap-2 rounded-lg bg-paper-2 px-3 py-2">
                        <span className="mr-auto text-[13.5px]"><b className="font-medium">{i.name}</b> <span className="text-slate">· {i.profession}</span></span>
                        <Button size="sm" variant="accent" loading={respond.isPending && respond.variables?.persona_key === i.key && respond.variables.accept} onClick={() => respond.mutate({ persona_key: i.key, accept: true })}><Check /> Step in</Button>
                        <Button size="sm" variant="ghost" onClick={() => respond.mutate({ persona_key: i.key, accept: false })}><X /> Decline</Button>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {d.steps.resolved && <p className="mt-4 rounded-lg bg-positive-50 p-3 text-[13.5px] text-positive">Solved: a replacement performer is booked, participants were notified, the complaint is closed and the Memory Agent recorded what worked.</p>}
            </Panel>

            {d.decisions.length > 0 && (
              <Panel title="What the agents did and why" action={<Link href="/command/agents" className="text-[12.5px] text-teal-600">All agent activity</Link>}>
                <ol className="space-y-3">
                  {runDecisions.map((x) => (
                    <li key={x.decision_id} className="rounded-lg border border-line p-3">
                      <div className="flex items-center gap-2"><Bot className="size-4 text-teal" /><b className="text-[13.5px] font-medium">{x.agent_name}</b><Badge tone={x.review_status === "auto_authorized" ? "positive" : "neutral"}>{x.review_status === "auto_authorized" ? "acted · authorised by organiser" : x.review_status}</Badge><span className="ml-auto text-[11.5px] text-slate">{timeAgo(x.created_at)}</span></div>
                      <p className="mt-1.5 text-[13px] leading-relaxed text-slate">{x.rationale}</p>
                    </li>
                  ))}
                </ol>
                {cand && (
                  <div className="mt-5">
                    <p className="mb-2 text-[13px] font-semibold">Replacement search — Query G <span className="font-mono text-[11px] font-normal text-slate">{cand.query_id}</span></p>
                    <div className="overflow-hidden rounded-lg border border-line">
                      {cand.eligible.map((c, i) => (
                        <div key={c.name} className="border-b border-line bg-white p-3 last:border-0">
                          <p className="flex items-center gap-2 text-[13.5px]"><b className="font-medium">{c.name}</b><span className="text-slate">{c.profession} · {c.neighborhood} · {c.distance}</span><Badge tone={i < 2 ? "positive" : "neutral"} className="ml-auto">{i < 2 ? "Invited" : "Eligible"} · score {c.score}</Badge></p>
                          <p className="mt-1 text-[12px] text-slate">{c.reasons?.join(" · ")}</p>
                        </div>
                      ))}
                      {cand.excluded.map((c) => (
                        <div key={c.name} className="border-b border-line bg-paper-2/60 p-3 last:border-0">
                          <p className="flex items-center gap-2 text-[13.5px]"><b className="font-medium">{c.name}</b><span className="text-slate">{c.profession} · {c.neighborhood}</span><Badge tone="outline" className="ml-auto">Excluded</Badge></p>
                          <p className="mt-1 text-[12px] text-slate">{c.reason}</p>
                        </div>
                      ))}
                    </div>
                    {impactDecision && <Link className="mt-2 inline-block text-[12px] text-teal-600 hover:underline" href="/command/agents">Open the full decision trace</Link>}
                  </div>
                )}
              </Panel>
            )}

            {d.memory.length > 0 && (
              <Panel title="Persistent memory written">
                {d.memory.map((m) => <p key={m.memory_id} className="flex gap-2 text-[13.5px]"><Brain className="mt-0.5 size-4 shrink-0 text-amber" />{m.summary}</p>)}
                <p className="mt-2 text-[12px] text-slate">Retrieved by the Memory Agent (Query H) the next time a performer cancels.</p>
              </Panel>
            )}

          </div>

          <div className="space-y-6">
            {d.organizer?.is_real && (
              <Panel title="You">
                <p className="text-[14px]"><b className="font-medium">{d.organizer.name}</b> <Badge tone="teal">Organiser · autopilot on</Badge></p>
                <p className="mt-1.5 text-[13px] leading-relaxed text-slate">This is <b>your own account</b>. Open CityPulse normally (not “View as”): the event is yours, the agents act for you, and your notification bell fills up as things happen.</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {d.event && <Button size="sm" variant="accent" asChild><Link href={`/events/${d.event.event_id}`} target="_blank">Open my event</Link></Button>}
                  <Button size="sm" variant="outline" asChild><Link href="/my-activity" target="_blank">My activity</Link></Button>
                </div>
                {d.organizer.inbox.length > 0 && (
                  <ul className="mt-3 space-y-1.5 border-t border-line pt-3">
                    {d.organizer.inbox.map((n, i) => <li key={i} className="flex gap-1.5 text-[12px] leading-snug text-slate"><Bell className="mt-0.5 size-3 shrink-0 text-teal" />{n.message}</li>)}
                  </ul>
                )}
              </Panel>
            )}
            <Panel title="People">
              <ul className="space-y-3">
                {d.personas.map((p) => {
                  const st = status(p);
                  return (
                    <li key={p.key} className="rounded-xl border border-line p-3">
                      <div className="flex items-start gap-2">
                        <div className="min-w-0">
                          <p className="text-[14px] font-medium">{p.name}</p>
                          <p className="text-[12.5px] text-slate">{p.profession} · {p.neighborhood}</p>
                        </div>
                        <div className="ml-auto flex flex-col items-end gap-1">
                          <Badge tone={p.category === "artist" ? "violet" : "neutral"}>{p.category === "artist" ? "Artist" : "Professional"}</Badge>
                          <Badge tone={st.tone as any}>{st.text}</Badge>
                        </div>
                      </div>
                      <Button size="sm" variant="outline" className="mt-2.5 w-full" loading={viewAs.isPending && viewAs.variables === p.key} onClick={() => viewAs.mutate(p.key)}>
                        <Eye /> View CityPulse as {p.name.split(" ")[0] === "Dr." ? "Dr. " + p.name.split(" ")[1] : p.name.split(" ")[0]}
                      </Button>
                      {p.inbox.length > 0 && (
                        <ul className="mt-2.5 space-y-1.5 border-t border-line pt-2.5">
                          {p.inbox.slice(0, 2).map((n, i) => (
                            <li key={i} className="flex gap-1.5 text-[12px] leading-snug text-slate"><Bell className="mt-0.5 size-3 shrink-0 text-teal" />{n.message}</li>
                          ))}
                          {p.unread > 2 && <li className="text-[11.5px] text-slate">+{p.unread - 2} more in their inbox</li>}
                        </ul>
                      )}
                    </li>
                  );
                })}
              </ul>
            </Panel>
            {d.complaint && (
              <Panel title="The complaint">
                <Link href={`/issues/${d.complaint.issue_id}`} className="text-[14px] font-medium hover:underline">{d.complaint.title}</Link>
                <p className="mt-1 text-[12.5px] text-slate">Status: {d.complaint.status.replace(/_/g, " ")}{d.case ? ` · attached to “${d.case.title}”` : ""}</p>
              </Panel>
            )}
            {d.event && d.event.updates.length > 0 && (
              <Panel title="Event timeline">
                <ol className="space-y-2.5">
                  {[...d.event.updates].map((u) => <li key={u.discussion_id} className="text-[12.5px] leading-snug"><span className="text-slate">{timeAgo(u.created_at)} · </span>{u.body}</li>)}
                </ol>
              </Panel>
            )}
          </div>
        </div>
      )}
      {d.event && (
        <Panel title="Live graph around the event" className="mt-6">
          <GraphExplorer key={`${d.event.event_id}-${Object.values(d.steps).filter(Boolean).length}`} initialFocus={d.event.event_id} heightClass="h-[480px]" />
        </Panel>
      )}
    </div>
  );
}
