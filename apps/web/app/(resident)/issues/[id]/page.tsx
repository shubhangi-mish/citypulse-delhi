"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Bell, BellOff, Building2, CalendarDays, CheckCircle2, GitBranch, HandHeart, Link2, MapPin, Network, ShieldCheck, Users } from "lucide-react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { CategoryIcon, ProvenanceBadge, StatusBadge } from "@/components/badges";
import { toast } from "@/components/toaster";
import { Button } from "@/components/ui/button";
import { Badge, Card, Textarea } from "@/components/ui/primitives";
import { EmptyState, ErrorState, ListSkeleton } from "@/components/ui/states";
import { useIssueActions, useRequireProfile } from "@/features/issues/use-issue-actions";
import { api } from "@/lib/api";
import { ACTION_TYPES, ASSET_TYPES, ISSUE_CATEGORIES, cn, formatDateTime, label, pluralize, timeAgo } from "@/lib/format";

const MapView = dynamic(() => import("@/components/map/map-view").then((m) => m.MapView), { ssr: false, loading: () => <div className="skeleton h-full w-full" /> });

interface Related {
  issue_id: string;
  title: string;
  category: string;
  status: string;
  support_count: number;
  created_at: number;
  distance_m: number;
  same_category: boolean;
  shared_roads: { id: string; name: string }[];
  shared_assets: { id: string; name: string }[];
  shared_neighborhoods: { id: string; name: string }[];
  score: number;
}

interface IssueDetail {
  issue_id: string;
  title: string;
  description: string;
  category: string;
  status: string;
  public_lat: number;
  public_lng: number;
  public_location_precision: string;
  created_at: number;
  updated_at: number;
  verification_status: string;
  support_count: number;
  reported_by: string | null;
  is_mine: boolean;
  neighborhood_id: string | null;
  neighborhood: string | null;
  district: string | null;
  road: string | null;
  case_reference: string;
  assets: { asset_id: string; name: string; asset_type: string; relationship: string; distance_m: number | null; verification_status: string; organizations: { name: string; relationship: string; basis: string }[] }[];
  viewer: { supported: boolean; following: boolean };
  discussion: { discussion_id: string; body: string; created_at: number; kind: string; author: string | null; mine: boolean }[];
  related: Related[];
  related_query_id: string;
  about_event?: { event_id: string; title: string } | null;
  network: {
    supporter_count: number;
    named_supporters: string[];
    follower_count: number;
    linked: { issue_id: string; title: string; score: number; confirmed: boolean }[];
    cases: { case_id: string; title: string; status: string; participants: number; actions: { action_id: string; action_type: string; status: string; description: string; outcome: string | null }[] }[];
  } | null;
  warnings: { warning_id: string; title: string; severity: string; issuing_authority: string; expires_at: number }[];
  nearby_events: { event_id: string; title: string; start_time: number; distance_m: number }[];
}

function IssuePage() {
  const { id } = useParams<{ id: string }>();
  const isNew = useSearchParams().get("new") === "1";
  const q = useQuery({ queryKey: ["issue", id], queryFn: () => api.get<IssueDetail>(`/issues/${id}`) });
  const { support, follow, comment } = useIssueActions(id);
  const require = useRequireProfile();
  const qc = useQueryClient();
  const [body, setBody] = useState("");
  const resolve = useMutation({
    mutationFn: () => api.post(`/issues/${id}/status`, { status: "resolved_reporter_confirmed" }),
    onSuccess: () => {
      toast.success("Marked as resolved. Thanks for closing the loop.");
      qc.invalidateQueries({ queryKey: ["issue", id] });
    },
  });

  if (q.isLoading)
    return (
      <div className="container-page py-10">
        <ListSkeleton rows={3} />
      </div>
    );
  if (q.error || !q.data)
    return (
      <div className="container-page py-10">
        <ErrorState error={q.error ?? new Error("Not found")} onRetry={() => q.refetch()} />
      </div>
    );
  const i = q.data;
  const comments = i.discussion.filter((d) => d.kind === "comment");
  const timeline = i.discussion;
  const activeCases = i.network?.cases.filter((c) => c.status !== "proposed") ?? [];

  return (
    <div className="container-page py-8">
      <Link href="/around-you" className="mb-6 inline-flex items-center gap-1.5 text-[13.5px] text-slate hover:text-ink">
        <ArrowLeft className="size-4" /> Around you
      </Link>

      {isNew && (
        <div className="mb-6 flex items-start gap-3 rounded-xl border border-teal/30 bg-teal-50 p-4 text-[14px]">
          <CheckCircle2 className="mt-0.5 size-5 shrink-0 text-teal" />
          <div>
            <p className="font-medium text-teal-600">Submitted to the CityPulse community.</p>
            <p className="mt-0.5 text-[13px] text-slate">
              It's now connected in the city graph{i.neighborhood ? ` to ${i.neighborhood}` : ""}
              {i.road ? `, ${i.road}` : ""}
              {i.related.length ? ` and ${pluralize(i.related.length, "related report")}` : ""}. This has not been filed with any government department.
            </p>
          </div>
        </div>
      )}

      <div className="grid gap-10 lg:grid-cols-[1fr_340px]">
        <article>
          <div className="flex items-center gap-2 text-[13px] text-slate">
            <CategoryIcon category={i.category} className="size-4 text-teal" />
            {label(ISSUE_CATEGORIES, i.category)}
            <span>·</span>
            <span title="CityPulse-generated reference. Not an official complaint number.">{i.case_reference}</span>
          </div>
          <h1 className="mt-2 font-display text-[34px] leading-[1.1] tracking-tight md:text-[42px]">{i.title}</h1>
          <div className="mt-4 flex flex-wrap items-center gap-1.5">
            <StatusBadge status={i.status} />
            <ProvenanceBadge status={i.verification_status} />
            {activeCases.length > 0 && (
              <Badge tone="teal">
                <Users /> Coordination active
              </Badge>
            )}
          </div>
          <p className="mt-4 text-[13.5px] text-slate">
            Reported by <b className="font-medium text-ink">{i.is_mine ? "you" : i.reported_by ?? "a resident"}</b> · {formatDateTime(i.created_at)}
            {i.neighborhood && (
              <>
                {" "}
                · <MapPin className="mb-0.5 inline size-3.5" /> {i.neighborhood}
                {i.district && `, ${i.district}`}
              </>
            )}
            {i.road && <> · {i.road}</>}
          </p>

          {i.about_event && (
            <p className="mt-4 text-[14px]">About the event: <Link className="font-medium text-teal-600 hover:underline" href={`/events/${i.about_event.event_id}`}>{i.about_event.title}</Link></p>
          )}
          <p className="mt-6 whitespace-pre-line text-[16px] leading-relaxed">{i.description}</p>

          <div className="mt-6 flex flex-wrap gap-2">
            {!i.is_mine && (
              <Button variant={i.viewer.supported ? "subtle" : "accent"} loading={support.isPending} onClick={() => require(`/issues/${id}`) && support.mutate(!i.viewer.supported)}>
                <HandHeart /> {i.viewer.supported ? "You're affected" : "I'm affected too"}
              </Button>
            )}
            {!i.is_mine && (
              <Button variant="outline" loading={follow.isPending} onClick={() => require() && follow.mutate(!i.viewer.following)}>
                {i.viewer.following ? <BellOff /> : <Bell />} {i.viewer.following ? "Following" : "Follow"}
              </Button>
            )}
            {i.is_mine && i.status !== "resolved_reporter_confirmed" && (
              <Button variant="outline" loading={resolve.isPending} onClick={() => resolve.mutate()}>
                <CheckCircle2 /> It's resolved
              </Button>
            )}
            <Button
              variant="ghost"
              onClick={async () => {
                await navigator.clipboard?.writeText(window.location.href.split("?")[0]);
                toast.success("Link copied.");
              }}
            >
              <Link2 /> Share
            </Button>
            <Button variant="ghost" asChild>
              <Link href={`/connections?focus=${i.issue_id}`}>
                <Network /> See connections
              </Link>
            </Button>
          </div>

          {/* corroboration */}
          <Card className="mt-8 p-5">
            <div className="flex flex-wrap items-center gap-x-8 gap-y-3">
              <div>
                <div className="text-[28px] font-semibold tabular-nums">{i.support_count}</div>
                <div className="text-[12.5px] text-slate">residents affected</div>
              </div>
              <div>
                <div className="text-[28px] font-semibold tabular-nums">{i.network?.follower_count ?? 0}</div>
                <div className="text-[12.5px] text-slate">following</div>
              </div>
              <div className="min-w-48 flex-1 text-[13px] leading-relaxed text-slate">
                {i.support_count >= 3
                  ? "Independently confirmed by several residents. This is community corroboration, not official confirmation."
                  : `Reports become “community corroborated” after 3 residents confirm they're affected.`}
                {!!i.network?.named_supporters.length && <span className="block text-ink">Including {i.network.named_supporters.slice(0, 3).join(", ")}.</span>}
              </div>
            </div>
          </Card>

          {/* related */}
          <section className="mt-10">
            <div className="mb-3 flex items-end justify-between">
              <h2 className="text-[17px] font-semibold tracking-tight">Related reports</h2>
              <span className="font-mono text-[11px] text-slate">{i.related_query_id}</span>
            </div>
            {i.related.length === 0 ? (
              <p className="rounded-xl border border-dashed border-line-strong p-4 text-[13.5px] text-slate">No related reports nearby in the last 120 days. The graph checks shared roads, nearby assets, neighbourhood and category.</p>
            ) : (
              <ul className="space-y-2">
                {i.related.map((r) => (
                  <li key={r.issue_id}>
                    <Link href={`/issues/${r.issue_id}`} className="block rounded-xl border border-line bg-white p-4 hover:border-line-strong">
                      <div className="flex items-start justify-between gap-3">
                        <p className="text-[14.5px] font-medium">{r.title}</p>
                        {r.same_category && r.score >= 0.65 && <Badge tone="violet">Possible duplicate</Badge>}
                      </div>
                      <div className="mt-2 flex flex-wrap gap-1.5 text-[12px]">
                        {r.same_category && <Badge tone="outline">Same category</Badge>}
                        {r.shared_roads.map((x) => (
                          <Badge key={x.id} tone="outline">
                            <GitBranch /> Same road: {x.name}
                          </Badge>
                        ))}
                        {r.shared_assets.map((x) => (
                          <Badge key={x.id} tone="outline">
                            Near {x.name}
                          </Badge>
                        ))}
                        {r.shared_neighborhoods.map((x) => (
                          <Badge key={x.id} tone="outline">
                            {x.name}
                          </Badge>
                        ))}
                        <Badge tone="neutral">{Math.round(r.distance_m)} m away</Badge>
                      </div>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </section>

          {/* coordination */}
          {activeCases.length > 0 && (
            <section className="mt-10">
              <h2 className="mb-3 text-[17px] font-semibold tracking-tight">Coordination on CityPulse</h2>
              {activeCases.map((c) => (
                <Card key={c.case_id} className="p-5">
                  <div className="flex items-center justify-between gap-3">
                    <p className="font-medium">{c.title}</p>
                    <Badge tone="teal">{c.status.replace("_", " ")}</Badge>
                  </div>
                  <ul className="mt-3 space-y-2">
                    {c.actions
                      .filter((a) => a.status !== "proposed" && a.status !== "rejected")
                      .map((a) => (
                        <li key={a.action_id} className="flex gap-2 text-[13.5px]">
                          <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-positive" />
                          <span>
                            {label(ACTION_TYPES, a.action_type)} — {a.description}
                            {a.outcome && <span className="block text-slate">Outcome: {a.outcome}</span>}
                          </span>
                        </li>
                      ))}
                  </ul>
                  <p className="mt-3 text-[12px] text-slate">Coordinated by CityPulse community coordinators. Not an official government process.</p>
                </Card>
              ))}
            </section>
          )}

          {/* discussion */}
          <section className="mt-10">
            <h2 className="mb-3 text-[17px] font-semibold tracking-tight">Discussion & history</h2>
            <ol className="space-y-3">
              {timeline.map((d) => (
                <li key={d.discussion_id} className={cn("rounded-xl p-4", d.kind === "comment" ? "border border-line bg-white" : "bg-paper-2/70")}>
                  <p className="text-[12.5px] text-slate">
                    {d.kind === "comment" ? <b className="font-medium text-ink">{d.mine ? "You" : d.author ?? "A resident"}</b> : <span className="font-medium text-ink">CityPulse</span>} · {timeAgo(d.created_at)}
                  </p>
                  <p className="mt-1 whitespace-pre-line text-[14.5px] leading-relaxed">{d.body}</p>
                </li>
              ))}
            </ol>
            <form
              className="mt-4"
              onSubmit={(e) => {
                e.preventDefault();
                if (!require(`/issues/${id}`) || !body.trim()) return;
                comment.mutate(body.trim(), { onSuccess: () => setBody("") });
              }}
            >
              <Textarea value={body} onChange={(e) => setBody(e.target.value)} placeholder={comments.length ? "Add to the discussion…" : "Be the first to comment. Share what you've seen."} className="min-h-20" maxLength={2000} />
              <div className="mt-2 flex justify-end">
                <Button size="sm" type="submit" loading={comment.isPending} disabled={!body.trim()}>
                  Comment
                </Button>
              </div>
            </form>
          </section>
        </article>

        <aside className="space-y-5">
          <Card className="overflow-hidden">
            <div className="h-56">
              <MapView
                center={{ latitude: i.public_lat, longitude: i.public_lng }}
                zoom={15}
                features={[{ type: "Feature", geometry: { type: "Point", coordinates: [i.public_lng, i.public_lat] }, properties: { kind: "issue", id: i.issue_id, title: i.title } }]}
                selectedId={i.issue_id}
              />
            </div>
            <p className="px-4 py-2.5 text-[12px] text-slate">{i.public_location_precision === "neighborhood" ? "Shown at neighbourhood level." : "Approximate location (~100 m)."}</p>
          </Card>

          <Card className="p-5">
            <h3 className="flex items-center gap-2 text-[13.5px] font-semibold">
              <Building2 className="size-4 text-teal" /> Known places nearby
            </h3>
            {i.assets.length === 0 ? (
              <p className="mt-2 text-[13px] text-slate">No mapped infrastructure within 300 m.</p>
            ) : (
              <ul className="mt-3 space-y-3">
                {i.assets.map((a) => (
                  <li key={a.asset_id + a.relationship}>
                    <p className="text-[13.5px] font-medium">{a.name}</p>
                    <p className="text-[12px] text-slate">
                      {label(ASSET_TYPES, a.asset_type)} · {a.relationship === "CONCERNS" ? "selected by reporter" : `${a.distance_m} m away`}
                    </p>
                    {a.organizations.map((o) => (
                      <p key={o.name} className="mt-1 text-[12px] text-slate">
                        Operated by <span className="text-ink">{o.name}</span> <span className="italic">({o.basis})</span>
                      </p>
                    ))}
                  </li>
                ))}
              </ul>
            )}
            <p className="mt-3 border-t border-line pt-2.5 text-[11.5px] leading-relaxed text-slate">
              Operator information comes from OpenStreetMap tags. CityPulse does not infer who is responsible from location alone.
            </p>
          </Card>

          <Card className="p-5">
            <h3 className="flex items-center gap-2 text-[13.5px] font-semibold">
              <ShieldCheck className="size-4 text-amber" /> Official alerts here
            </h3>
            {i.warnings.length === 0 ? (
              <p className="mt-2 text-[13px] text-slate">No active official alert covers this neighbourhood.</p>
            ) : (
              <ul className="mt-3 space-y-2">
                {i.warnings.map((w) => (
                  <li key={w.warning_id}>
                    <Link href={`/warnings/${w.warning_id}`} className="text-[13.5px] font-medium hover:underline">
                      {w.title}
                    </Link>
                    <p className="text-[12px] text-slate">{w.issuing_authority}</p>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <Card className="p-5">
            <h3 className="flex items-center gap-2 text-[13.5px] font-semibold">
              <CalendarDays className="size-4 text-violet" /> Upcoming events within 2 km
            </h3>
            {i.nearby_events.length === 0 ? (
              <p className="mt-2 text-[13px] text-slate">None scheduled.</p>
            ) : (
              <ul className="mt-3 space-y-2">
                {i.nearby_events.map((e) => (
                  <li key={e.event_id}>
                    <Link href={`/events/${e.event_id}`} className="text-[13.5px] font-medium hover:underline">
                      {e.title}
                    </Link>
                    <p className="text-[12px] text-slate">
                      {formatDateTime(e.start_time)} · {e.distance_m} m
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </aside>
      </div>
    </div>
  );
}

export default function Page() {
  return (
    <Suspense>
      <IssuePage />
    </Suspense>
  );
}
