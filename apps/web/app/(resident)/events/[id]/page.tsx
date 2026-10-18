"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Bot, Check, Clock, ExternalLink, HandHeart, MapPin, Mic2, Network, ShieldCheck, Star, TriangleAlert, Users, X } from "lucide-react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { ProvenanceBadge, StatusBadge } from "@/components/badges";
import { toast } from "@/components/toaster";
import { Button } from "@/components/ui/button";
import { Badge, Card, Switch, Textarea } from "@/components/ui/primitives";
import { ErrorState, ListSkeleton } from "@/components/ui/states";
import { useRequireProfile } from "@/features/issues/use-issue-actions";
import { api, ApiError } from "@/lib/api";
import { EVENT_CATEGORIES, formatDateTime, formatTime, label, pluralize, timeAgo } from "@/lib/format";

const MapView = dynamic(() => import("@/components/map/map-view").then((m) => m.MapView), { ssr: false, loading: () => <div className="skeleton h-full w-full" /> });

interface EventDetail {
  event_id: string;
  title: string;
  description: string;
  category: string;
  start_time: number;
  end_time: number;
  status: string;
  verification_status: string;
  source_type: string;
  is_free: boolean | null;
  setting: string | null;
  organizer_attestation?: boolean;
  accessibility: string | null;
  registration_url: string | null;
  public_lat: number;
  public_lng: number;
  organizer_name: string;
  organizer_contact?: string;
  venue: { name: string; address: string } | null;
  road: string | null;
  neighborhood: string | null;
  organization: { name: string; verification_status: string } | null;
  is_organizer: boolean;
  participant_count: number;
  participant_roles: Record<string, number>;
  named_participants: string[];
  attendees?: { name: string; profession: string | null; role: string | null }[];
  viewer: { participating: boolean; role: string | null };
  warnings: { warning_id: string; title: string; severity: string; issuing_authority: string; via: string; basis: string }[];
  nearby_issues: { issue_id: string; title: string; category: string; status: string; distance_m: number }[];
  updates: { discussion_id: string; body: string; created_at: number; kind: string; author: string | null; actor?: string | null }[];
  performer_gap?: boolean;
  agent_autopilot?: boolean;
  performers: { display_name: string | null; profession: string | null; status: string; role: string | null }[];
  viewer_invitation: string | null;
  viewer_performance?: string | null;
  coordination: { case_id: string; title: string; status: string; actions: { action_type: string; description: string; status: string; outcome: string | null; proposed_by: string; authorised_by: string | null; note: string | null }[] }[];
}

export default function EventPage() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();
  const require = useRequireProfile();
  const q = useQuery({ queryKey: ["event", id], queryFn: () => api.get<EventDetail>(`/events/${id}`), refetchInterval: 8000 });
  const [text, setText] = useState("");
  const refresh = () => qc.invalidateQueries({ queryKey: ["event", id] });
  const onError = (e: unknown) => toast.error(e instanceof ApiError ? e.message : "Something went wrong.");
  const participate = useMutation({
    mutationFn: (role: string | null) => api.post(`/events/${id}/participate`, { role }),
    onSuccess: (_, role) => {
      toast.success(role ? `Marked as ${role}.` : "Removed.");
      refresh();
    },
    onError,
  });
  const autopilot = useMutation({
    mutationFn: (enabled: boolean) => api.post(`/events/${id}/autopilot`, { enabled }),
    onSuccess: (_, on) => { toast.success(on ? "Agents may now act for you if a performer cancels." : "Agents will only propose; nothing happens without a coordinator."); refresh(); },
    onError,
  });
  const reportCancel = useMutation({
    mutationFn: () => api.post<any>(`/events/${id}/cancel-performance`, { reason: "Reported by the organiser" }),
    onSuccess: (r) => { toast.success(r.executed?.length ? `Your agents acted: ${r.executed.length} action(s) done on your behalf.` : "Agents analysed it and proposed actions for a coordinator."); refresh(); qc.invalidateQueries({ queryKey: ["notifications"] }); },
    onError,
  });
  const [performerQ, setPerformerQ] = useState("");
  const artists = useQuery({
    queryKey: ["performer-search", id, performerQ],
    queryFn: () => api.get<{ items: { resident_id: string; name: string; profession: string; neighborhood: string | null }[] }>(`/events/${id}/performer-search`, { q: performerQ }),
    enabled: !!q.data?.is_organizer,
  });
  const addPerformer = useMutation({
    mutationFn: (rid: string) => api.post(`/events/${id}/performers`, { resident_id: rid }),
    onSuccess: () => { toast.success("Performer added — they've been notified."); refresh(); qc.invalidateQueries({ queryKey: ["performer-search", id] }); },
    onError,
  });
  const cantMakeIt = useMutation({
    mutationFn: () => api.post<any>(`/events/${id}/cancel-performance`, { reason: "The performer can no longer make it" }),
    onSuccess: () => { toast.success("The organiser and attendees have been told, and CityPulse is looking for a replacement."); refresh(); qc.invalidateQueries({ queryKey: ["notifications"] }); },
    onError,
  });
  const invitation = useMutation({
    mutationFn: (accept: boolean) => api.post(`/events/${id}/invitation`, { accept }),
    onSuccess: (_, accept) => {
      toast.success(accept ? "You're booked — thank you for stepping in!" : "No problem — thanks for letting us know.");
      refresh();
      qc.invalidateQueries({ queryKey: ["notifications"] });
    },
    onError,
  });
  const post = useMutation({
    mutationFn: () => api.post(`/events/${id}/${q.data?.is_organizer ? "updates" : "comments"}`, { body: text }),
    onSuccess: () => {
      setText("");
      refresh();
    },
    onError,
  });

  if (q.isLoading) return <div className="container-page py-10"><ListSkeleton /></div>;
  if (q.error || !q.data) return <div className="container-page py-10"><ErrorState error={q.error} onRetry={() => q.refetch()} /></div>;
  const e = q.data;
  const roles = [
    { role: "interested", label: "Interested", icon: Star },
    { role: "going", label: "Going", icon: Users },
    { role: "volunteer", label: "Volunteer", icon: HandHeart },
  ];

  return (
    <div className="container-page py-8">
      <Link href="/events" className="mb-6 inline-flex items-center gap-1.5 text-[13.5px] text-slate hover:text-ink">
        <ArrowLeft className="size-4" /> Events
      </Link>
      <div className="grid gap-10 lg:grid-cols-[1fr_340px]">
        <article>
          <div className="eyebrow">{label(EVENT_CATEGORIES, e.category)}</div>
          <h1 className="mt-2 font-display text-[36px] leading-[1.08] tracking-tight md:text-[46px]">{e.title}</h1>
          <div className="mt-4 flex flex-wrap gap-1.5">
            <ProvenanceBadge status={e.verification_status} />
            {e.source_type === "user_submitted" && <Badge tone="outline">{e.organizer_attestation ? "Resident-submitted · organiser attested" : "Shared by a resident from a public listing · not confirmed by the organiser"}</Badge>}
            {e.is_free === true ? <Badge tone="neutral">Free</Badge> : e.is_free === false ? <Badge tone="neutral">Paid</Badge> : <Badge tone="outline">Price not listed</Badge>}
            {e.setting && <Badge tone="neutral">{e.setting}</Badge>}
          </div>
          <dl className="mt-6 grid gap-4 rounded-xl border border-line bg-white p-5 sm:grid-cols-2">
            <div className="flex gap-3">
              <Clock className="mt-0.5 size-5 text-violet" />
              <div>
                <dt className="text-[12px] text-slate">When</dt>
                <dd className="text-[14.5px] font-medium">
                  {formatDateTime(e.start_time)} – {formatTime(e.end_time)}
                </dd>
              </div>
            </div>
            <div className="flex gap-3">
              <MapPin className="mt-0.5 size-5 text-violet" />
              <div>
                <dt className="text-[12px] text-slate">Where</dt>
                <dd className="text-[14.5px] font-medium">{e.venue?.name}</dd>
                <dd className="text-[12.5px] text-slate">
                  {[e.road, e.neighborhood].filter(Boolean).join(" · ")}
                </dd>
              </div>
            </div>
          </dl>
          <p className="mt-6 whitespace-pre-line text-[16px] leading-relaxed">{e.description}</p>
          {e.viewer_performance === "confirmed" && !e.is_organizer && (
            <div className="mt-6 rounded-xl border border-violet/30 bg-violet-50/60 p-5">
              <p className="flex items-center gap-2 text-[15px] font-semibold text-violet"><Mic2 className="size-5" /> You're performing at this event</p>
              <p className="mt-1 text-[13.5px] text-slate">If your plans change, tell everyone as early as you can: attendees are notified and nearby artists are invited to step in.</p>
              <Button className="mt-3" variant="outline" loading={cantMakeIt.isPending} onClick={() => confirm("Tell the organiser and attendees that you can't perform?") && cantMakeIt.mutate()}>I can't make it anymore</Button>
            </div>
          )}
          {e.is_organizer && (
            <div className="mt-6 rounded-xl border border-line bg-white p-5">
              <p className="text-[15px] font-semibold">Add a performer</p>
              <p className="mt-0.5 text-[12.5px] text-slate">Only artists who turned on "open to fill-in performances" and chose a public profile are listed.</p>
              <input value={performerQ} onChange={(ev) => setPerformerQ(ev.target.value)} placeholder="Search by name or what they do (e.g. singer, painter)" className="mt-3 h-10 w-full rounded-[10px] border border-line-strong px-3 text-[14px] focus:border-teal focus:outline-none" />
              <ul className="mt-3 space-y-2">
                {artists.data?.items.map((a) => (
                  <li key={a.resident_id} className="flex items-center justify-between gap-3 rounded-lg bg-paper-2 px-3 py-2">
                    <span className="text-[13.5px]"><b className="font-medium">{a.name}</b> <span className="text-slate">· {a.profession}{a.neighborhood ? ` · ${a.neighborhood}` : ""}</span></span>
                    <Button size="sm" variant="accent" loading={addPerformer.isPending && addPerformer.variables === a.resident_id} onClick={() => addPerformer.mutate(a.resident_id)}>Add</Button>
                  </li>
                ))}
                {artists.data && artists.data.items.length === 0 && <li className="text-[13px] text-slate">No matching artists yet. They appear here once they set a profession and opt in on their Profile.</li>}
              </ul>
            </div>
          )}
          {e.is_organizer && e.performers.length > 0 && (
            <div className="mt-6 rounded-xl border border-violet/30 bg-violet-50/60 p-5">
              <p className="flex items-center gap-2 text-[15px] font-semibold text-violet"><Bot className="size-5" /> Organiser controls</p>
              <label className="mt-3 flex items-start justify-between gap-6">
                <span className="text-[13.5px]">Let CityPulse agents act for me if a booked performer cancels
                  <span className="block text-[12.5px] text-slate">They'll find and invite nearby artists who are free, tell your attendees, and notify you of everything they do.</span></span>
                <Switch checked={!!e.agent_autopilot} onCheckedChange={(v) => autopilot.mutate(v)} />
              </label>
              {e.performers.some((p) => p.status === "confirmed") && (
                <Button className="mt-4" variant="danger" loading={reportCancel.isPending} onClick={() => confirm("Report that your booked performer has cancelled? Attendees will be notified and the agents will start looking for a replacement.") && reportCancel.mutate()}>
                  A booked performer has cancelled
                </Button>
              )}
            </div>
          )}
          {e.performer_gap && (
            <div className="mt-6 flex gap-3 rounded-xl border border-amber/40 bg-amber-50 p-4">
              <TriangleAlert className="mt-0.5 size-5 shrink-0 text-amber" />
              <div>
                <p className="text-[14.5px] font-semibold text-[#6f4b13]">The booked performer has cancelled</p>
                <p className="mt-0.5 text-[13.5px] text-[#6f4b13]">CityPulse agents are looking for a replacement among nearby artists. Updates will appear below.</p>
              </div>
            </div>
          )}
          {e.viewer_invitation === "pending" && (
            <div className="mt-6 rounded-xl border border-teal/40 bg-teal-50 p-5">
              <p className="flex items-center gap-2 text-[15px] font-semibold text-teal-600"><Mic2 className="size-5" /> You've been invited to step in</p>
              <p className="mt-1 text-[13.5px] text-slate">A CityPulse agent matched you to this event because you're a nearby artist who's open to fill-in gigs and you're free at that time.</p>
              <div className="mt-4 flex gap-2">
                <Button variant="accent" loading={invitation.isPending && invitation.variables === true} onClick={() => invitation.mutate(true)}><Check /> I can step in</Button>
                <Button variant="outline" loading={invitation.isPending && invitation.variables === false} onClick={() => invitation.mutate(false)}><X /> Can't make it</Button>
              </div>
            </div>
          )}
          {e.performers.length > 0 && (
            <div className="mt-6">
              <h2 className="mb-2 text-[13px] font-semibold uppercase tracking-wider text-slate">Performers</h2>
              <ul className="space-y-2">
                {e.performers.map((p, k) => (
                  <li key={k} className="flex items-center gap-3 rounded-xl border border-line bg-white px-4 py-3">
                    <Mic2 className="size-4 text-violet" />
                    <span className="text-[14.5px] font-medium">{p.display_name ?? "A performer"}</span>
                    <span className="text-[13px] text-slate">{p.profession}</span>
                    <span className="ml-auto flex gap-1.5">
                      {p.role && <Badge tone="outline">{p.role}</Badge>}
                      <Badge tone={p.status === "cancelled" ? "critical" : "positive"}>{p.status === "cancelled" ? "Cancelled" : "Confirmed"}</Badge>
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {e.accessibility && <p className="mt-4 text-[14px] text-slate"><b className="font-medium text-ink">Accessibility:</b> {e.accessibility}</p>}
          <p className="mt-4 text-[14px] text-slate">
            Organised by <b className="font-medium text-ink">{e.organizer_name}</b>
            {e.organization && <> · {e.organization.name}</>}
          </p>
          {e.registration_url && (
            <a href={e.registration_url} target="_blank" rel="noreferrer" className="mt-2 inline-flex items-center gap-1 text-[14px] font-medium text-teal-600 hover:underline">
              Registration <ExternalLink className="size-3.5" />
            </a>
          )}

          {!e.is_organizer && (
            <div className="mt-6 flex flex-wrap gap-2">
              {roles.map((r) => (
                <Button
                  key={r.role}
                  variant={e.viewer.role === r.role ? "accent" : "outline"}
                  loading={participate.isPending && participate.variables === r.role}
                  onClick={() => require(`/events/${id}`) && participate.mutate(e.viewer.role === r.role ? null : r.role)}
                >
                  <r.icon /> {r.label}
                </Button>
              ))}
            </div>
          )}

          <section className="mt-10">
            <h2 className="mb-3 text-[17px] font-semibold tracking-tight">{e.is_organizer ? "Updates & discussion (you're the organiser)" : "Updates & discussion"}</h2>
            {e.updates.length === 0 && <p className="mb-3 text-[13.5px] text-slate">No updates yet.</p>}
            <ol className="space-y-3">
              {e.updates.map((u) => (
                <li key={u.discussion_id} className={u.kind === "organizer_update" ? "rounded-xl border border-violet/25 bg-violet-50/60 p-4" : "rounded-xl border border-line bg-white p-4"}>
                  <p className="text-[12.5px] text-slate">
                    {u.kind === "history" ? <b className="font-medium text-ink">CityPulse</b> : u.kind === "organizer_update" ? <b className="font-medium text-violet">Organiser update</b> : <b className="font-medium text-ink">{u.author ?? "A resident"}</b>} · {timeAgo(u.created_at)}
                  </p>
                  <p className="mt-1 whitespace-pre-line text-[14.5px]">{u.body}</p>
                </li>
              ))}
            </ol>
            <form
              className="mt-4"
              onSubmit={(ev) => {
                ev.preventDefault();
                if (require(`/events/${id}`) && text.trim()) post.mutate();
              }}
            >
              <Textarea value={text} onChange={(ev) => setText(ev.target.value)} placeholder={e.is_organizer ? "Post an update to all participants…" : "Ask a question or add a note…"} className="min-h-20" />
              <div className="mt-2 flex justify-end">
                <Button size="sm" type="submit" disabled={!text.trim()} loading={post.isPending}>
                  {e.is_organizer ? "Post update" : "Comment"}
                </Button>
              </div>
            </form>
          </section>
        </article>

        <aside className="space-y-5">
          <Card className="overflow-hidden">
            <div className="h-52">
              <MapView center={{ latitude: e.public_lat, longitude: e.public_lng }} zoom={15} features={[{ type: "Feature", geometry: { type: "Point", coordinates: [e.public_lng, e.public_lat] }, properties: { kind: "event", id: e.event_id, title: e.title } }]} />
            </div>
          </Card>
          {e.coordination.length > 0 && (
            <Card className="border-teal/30 p-5">
              <h3 className="flex items-center gap-2 text-[13.5px] font-semibold"><Bot className="size-4 text-teal" /> What CityPulse agents did</h3>
              {e.coordination.map((c) => (
                <div key={c.case_id} className="mt-3">
                  <p className="text-[13px] font-medium">{c.title} <Badge tone={c.status === "resolved" ? "positive" : "teal"}>{c.status.replace("_", " ")}</Badge></p>
                  <ul className="mt-2 space-y-2">
                    {c.actions.map((a, k) => (
                      <li key={k} className="text-[12.5px] leading-relaxed">
                        <span className="font-medium">{a.description}</span>
                        <span className="block text-slate">{a.note}</span>
                        {a.outcome && <span className="block text-positive">Outcome: {a.outcome}</span>}
                        <span className="block text-[11.5px] text-slate">proposed by {a.proposed_by.replace("agent:", "")}{a.authorised_by ? ` · authorised by ${a.authorised_by}` : ""}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </Card>
          )}
          <Card className="p-5">
            <h3 className="text-[13.5px] font-semibold">Participants</h3>
            <p className="mt-1 text-[24px] font-semibold tabular-nums">{e.participant_count}</p>
            <p className="text-[12.5px] text-slate">
              {pluralize(e.participant_roles.going ?? 0, "going", "going")} · {e.participant_roles.interested ?? 0} interested · {pluralize(e.participant_roles.volunteer ?? 0, "volunteer")}
            </p>
            {!!e.attendees?.length && (
              <ul className="mt-3 space-y-2 border-t border-line pt-3">
                {e.attendees.map((a, k) => (
                  <li key={k} className="flex items-start justify-between gap-2 text-[13px]">
                    <span><b className="font-medium">{a.name}</b>{a.profession && <span className="block text-[12px] text-slate">{a.profession}</span>}</span>
                    {a.role && <Badge tone={a.role === "volunteer" ? "teal" : "neutral"}>{a.role}</Badge>}
                  </li>
                ))}
              </ul>
            )}
            {e.participant_count > (e.attendees?.length ?? 0) && <p className="mt-2 text-[12px] text-slate">+{e.participant_count - (e.attendees?.length ?? 0)} more with private profiles</p>}
            {e.is_organizer && e.organizer_contact && <p className="mt-3 border-t border-line pt-3 text-[12px] text-slate">Your contact (private): {e.organizer_contact}</p>}
          </Card>
          <Card className="p-5">
            <h3 className="flex items-center gap-2 text-[13.5px] font-semibold">
              <ShieldCheck className="size-4 text-amber" /> Official alerts overlapping this event
            </h3>
            {e.warnings.length === 0 ? (
              <p className="mt-2 text-[13px] text-slate">No active official alert overlaps this event's place and time.</p>
            ) : (
              <ul className="mt-3 space-y-2.5">
                {e.warnings.map((w) => (
                  <li key={w.warning_id}>
                    <Link href={`/warnings/${w.warning_id}`} className="text-[13.5px] font-medium hover:underline">
                      {w.title}
                    </Link>
                    <p className="text-[12px] text-slate">
                      {w.issuing_authority} · via {w.via} <span className="italic">(graph-inferred: time + place overlap)</span>
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </Card>
          <Card className="p-5">
            <h3 className="text-[13.5px] font-semibold">Community reports near the venue</h3>
            {e.nearby_issues.length === 0 ? (
              <p className="mt-2 text-[13px] text-slate">No open reports within 1 km.</p>
            ) : (
              <ul className="mt-3 space-y-2">
                {e.nearby_issues.map((i) => (
                  <li key={i.issue_id} className="flex items-start justify-between gap-2">
                    <Link href={`/issues/${i.issue_id}`} className="text-[13.5px] hover:underline">
                      {i.title}
                    </Link>
                    <span className="shrink-0 text-[12px] text-slate">{i.distance_m} m</span>
                  </li>
                ))}
              </ul>
            )}
            <Link href={`/report?event=${e.event_id}`} className="mt-4 flex items-center gap-1.5 text-[13px] font-medium text-teal-600 hover:underline">
              <TriangleAlert className="size-4" /> Report a problem with this event
            </Link>
            <Link href={`/connections?focus=${e.event_id}`} className="mt-4 flex items-center gap-1.5 text-[13px] font-medium text-teal-600 hover:underline">
              <Network className="size-4" /> See graph connections
            </Link>
          </Card>
        </aside>
      </div>
    </div>
  );
}
