"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, ExternalLink, GitBranch, Network } from "lucide-react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useMemo } from "react";
import { ProvenanceBadge, SeverityBadge } from "@/components/badges";
import type { MapFeature } from "@/components/map/map-view";
import { Badge, Card } from "@/components/ui/primitives";
import { ErrorState, ListSkeleton } from "@/components/ui/states";
import { api } from "@/lib/api";
import { formatDateTime } from "@/lib/format";

const MapView = dynamic(() => import("@/components/map/map-view").then((m) => m.MapView), { ssr: false, loading: () => <div className="skeleton h-full w-full" /> });

interface Impact { impact_type: string; entity_id: string; title: string; path_ids: string[]; path_rels: string[]; via: string }

export default function WarningPage() {
  const { id } = useParams<{ id: string }>();
  const q = useQuery({ queryKey: ["warning", id], queryFn: () => api.get<any>(`/warnings/${id}`) });
  const features = useMemo<MapFeature[]>(
    () => (q.data?.affected_neighborhoods ?? []).map((n: any) => ({ type: "Feature", geometry: { type: "Point", coordinates: [n.longitude, n.latitude] }, properties: { kind: "warning", id: n.neighborhood_id, title: n.name, severity: q.data.severity } })),
    [q.data],
  );
  if (q.isLoading) return <div className="container-page py-10"><ListSkeleton /></div>;
  if (q.error || !q.data) return <div className="container-page py-10"><ErrorState error={q.error} onRetry={() => q.refetch()} /></div>;
  const w = q.data;
  const impact = w.impact as { query_id: string; events: Impact[]; issues: Impact[]; assets: Impact[]; asset_total: number };

  return (
    <div className="container-page py-8">
      <Link href="/warnings" className="mb-6 inline-flex items-center gap-1.5 text-[13.5px] text-slate hover:text-ink"><ArrowLeft className="size-4" /> Warnings</Link>
      <div className="grid gap-10 lg:grid-cols-[1fr_380px]">
        <article>
          <div className="flex flex-wrap gap-1.5">
            <ProvenanceBadge status={w.verification_status} />
            <SeverityBadge severity={w.severity} />
            {w.urgency && <Badge tone="neutral">Urgency: {w.urgency}</Badge>}
            {w.certainty && <Badge tone="neutral">Certainty: {w.certainty}</Badge>}
            {!w.active && <Badge tone="outline">Expired</Badge>}
          </div>
          <h1 className="mt-3 font-display text-[32px] leading-[1.12] tracking-tight md:text-[40px]">{w.title}</h1>
          <Card className="mt-6 divide-y divide-line">
            {[
              ["Issuing authority", w.issuing_authority],
              ["Type", [w.warning_type, w.category].filter(Boolean).join(" · ")],
              ["Effective", formatDateTime(w.effective_at)],
              ["Expires", formatDateTime(w.expires_at)],
              ["Area (as published)", w.area_description],
            ].map(([k, v]) => (
              <div key={k} className="grid grid-cols-[160px_1fr] gap-4 px-5 py-3 text-[14px]">
                <span className="text-slate">{k}</span>
                <span>{v || "—"}</span>
              </div>
            ))}
          </Card>
          {w.description && <p className="mt-6 whitespace-pre-line text-[15.5px] leading-relaxed">{w.description}</p>}
          {w.instruction && (
            <div className="mt-6 rounded-xl border border-amber/40 bg-amber-50 p-4">
              <p className="text-[12px] font-semibold uppercase tracking-wider text-[#8a5c17]">Official instruction (verbatim from source)</p>
              <p className="mt-1 text-[15px]">{w.instruction}</p>
            </div>
          )}
          <a href={w.source_url} target="_blank" rel="noreferrer" className="mt-5 inline-flex items-center gap-1.5 text-[14px] font-medium text-teal-600 hover:underline">
            Open the original alert ({w.source_name}) <ExternalLink className="size-3.5" />
          </a>
          <p className="mt-1 text-[12px] text-slate">Licence: {w.license}. Ingested {formatDateTime(w.ingested_at)}.</p>

          <section className="mt-10">
            <div className="mb-3 flex items-end justify-between">
              <h2 className="text-[17px] font-semibold tracking-tight">What this alert connects to</h2>
              <span className="font-mono text-[11px] text-slate">{impact.query_id}</span>
            </div>
            <p className="mb-4 text-[13.5px] text-slate">
              These links are graph-derived: the alert's published area is matched to OpenStreetMap districts and neighbourhoods, then traversed to events, reports and infrastructure. They are not part of the official alert.
            </p>
            {[
              ["Upcoming events", impact.events, "/events/"],
              ["Open community reports", impact.issues, "/issues/"],
            ].map(([title, rows, href]: any) => (
              <div key={title} className="mb-5">
                <h3 className="mb-2 text-[14px] font-semibold">{title} ({rows.length})</h3>
                {rows.length === 0 ? (
                  <p className="text-[13px] text-slate">None in the affected area.</p>
                ) : (
                  <ul className="space-y-2">
                    {rows.map((r: Impact) => (
                      <li key={r.entity_id} className="rounded-xl border border-line bg-white p-3">
                        <Link href={href + r.entity_id} className="text-[14px] font-medium hover:underline">{r.title}</Link>
                        <p className="mt-1 flex items-center gap-1 text-[12px] text-slate"><GitBranch className="size-3.5" /> Alert —{r.path_rels.join("→")}— via {r.via}</p>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
            <h3 className="mb-2 text-[14px] font-semibold">Known infrastructure in the area ({impact.asset_total})</h3>
            <div className="flex flex-wrap gap-1.5">
              {impact.assets.slice(0, 30).map((a) => <Badge key={a.entity_id} tone="outline">{a.title}</Badge>)}
              {impact.asset_total > 30 && <Badge tone="neutral">+{impact.asset_total - 30} more</Badge>}
            </div>
          </section>
        </article>
        <aside className="space-y-5">
          <Card className="overflow-hidden">
            <div className="h-72"><MapView features={features} zoom={10} /></div>
            <p className="px-4 py-2.5 text-[12px] text-slate">{w.affected_neighborhoods.length} mapped neighbourhoods matched to the alert area.</p>
          </Card>
          <Card className="p-5">
            <h3 className="text-[13.5px] font-semibold">Affected areas</h3>
            <ul className="mt-2 space-y-1 text-[13px]">
              {w.affected_areas.map((a: any) => <li key={a.area_id}>{a.name} <span className="text-slate">· {a.basis}</span></li>)}
            </ul>
            <p className="mt-3 text-[12.5px] text-slate">{w.opted_in_residents} CityPulse residents who opted into area updates live here.</p>
            <Link href={`/connections?focus=${w.warning_id}`} className="mt-3 flex items-center gap-1.5 text-[13px] font-medium text-teal-600 hover:underline"><Network className="size-4" /> Explore in City Connections</Link>
          </Card>
        </aside>
      </div>
    </div>
  );
}
