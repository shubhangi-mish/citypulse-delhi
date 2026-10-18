"use client";

import { useQuery } from "@tanstack/react-query";
import { Layers, Network, X } from "lucide-react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useEffect, useState } from "react";
import { KIND_COLORS, type MapFeature } from "@/components/map/map-view";
import { Badge, Card } from "@/components/ui/primitives";
import { ErrorState } from "@/components/ui/states";
import { GraphSearch, LABEL_NAMES, hrefFor } from "@/features/search/graph-search";
import { api } from "@/lib/api";
import { ASSET_TYPES, cn, label } from "@/lib/format";
import { type Layer, useDiscovery } from "@/lib/store";
import type { GraphEdge, GraphNode } from "@/lib/types";

const MapView = dynamic(() => import("@/components/map/map-view").then((m) => m.MapView), { ssr: false, loading: () => <div className="skeleton h-full w-full" /> });

const LAYERS: { id: Layer; label: string; color: string }[] = [
  { id: "issues", label: "Reports", color: KIND_COLORS.issue },
  { id: "events", label: "Events", color: KIND_COLORS.event },
  { id: "warnings", label: "Official alerts", color: KIND_COLORS.warning },
  { id: "infrastructure", label: "Infrastructure", color: KIND_COLORS.infrastructure },
  { id: "neighborhoods", label: "Neighbourhood names", color: KIND_COLORS.neighborhood },
];

const LAYER_KIND: Record<Layer, string> = { issues: "issue", events: "event", warnings: "warning", infrastructure: "infrastructure", neighborhoods: "neighborhood" };

export default function Explore() {
  const { layers, toggleLayer } = useDiscovery();
  const [bounds, setBounds] = useState<{ min_lat: number; min_lng: number; max_lat: number; max_lng: number } | null>(null);
  const [debounced, setDebounced] = useState(bounds);
  const [selected, setSelected] = useState<MapFeature | null>(null);
  const [focus, setFocus] = useState<{ latitude: number; longitude: number } | null>(null);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(bounds), 300);
    return () => clearTimeout(t);
  }, [bounds]);

  const data = useQuery({
    queryKey: ["map-layers", layers.join(","), debounced && Object.values(debounced).map((v) => v.toFixed(3)).join(",")],
    queryFn: () => api.get<{ features: MapFeature[]; attribution: string }>("/map/layers", { layers: layers.join(","), ...(debounced ?? {}) }),
    placeholderData: (p) => p,
  });
  const selId = selected?.properties.kind === "warning" ? null : selected?.properties.id;
  const neighbors = useQuery({
    queryKey: ["neighbors", selId],
    queryFn: () => api.get<{ nodes: GraphNode[]; edges: GraphEdge[] }>(`/graph/entities/${selId}/neighbors`),
    enabled: !!selId,
  });

  const counts = (data.data?.features ?? []).reduce<Record<string, number>>((a, f) => ((a[f.properties.kind] = (a[f.properties.kind] ?? 0) + 1), a), {});

  return (
    <div className="relative h-[calc(100dvh-4rem-5rem)] md:h-[calc(100dvh-4rem)]">
      <MapView features={data.data?.features ?? []} onSelect={setSelected} selectedId={selected?.properties.id} onBoundsChange={setBounds} center={focus} zoom={11} />

      <div className="pointer-events-none absolute inset-x-0 top-0 flex flex-col gap-3 p-3 md:p-4">
        <GraphSearch
          className="pointer-events-auto w-full max-w-md"
          placeholder="Search a place, metro station or report…"
          onPick={(n) => {
            const lat = n.props.latitude ?? n.props.public_lat;
            const lng = n.props.longitude ?? n.props.public_lng;
            if (lat && lng) setFocus({ latitude: lat, longitude: lng });
            else window.location.href = hrefFor(n);
          }}
        />
        <Card className="pointer-events-auto w-fit p-3">
          <div className="mb-2 flex items-center gap-1.5 text-[12px] font-semibold text-slate"><Layers className="size-3.5" /> Layers</div>
          <div className="flex flex-wrap gap-1.5 md:flex-col">
            {LAYERS.map((l) => (
              <label key={l.id} className="flex cursor-pointer items-center gap-2 rounded-md px-1 py-0.5 text-[13px]">
                <input type="checkbox" className="accent-[#157C83]" checked={layers.includes(l.id)} onChange={() => toggleLayer(l.id)} />
                <span className="size-2.5 rounded-full" style={{ background: l.color }} />
                {l.label}
                {layers.includes(l.id) && <span className="text-slate tabular-nums">{counts[LAYER_KIND[l.id]] ?? 0}</span>}
              </label>
            ))}
          </div>
        </Card>
        {data.error && <ErrorState className="pointer-events-auto max-w-md" error={data.error} />}
      </div>

      {selected && (
        <Card className="absolute inset-x-3 bottom-3 max-h-[55%] overflow-auto p-5 md:inset-x-auto md:bottom-auto md:right-4 md:top-4 md:w-[360px] md:max-h-[calc(100%-2rem)]">
          <button onClick={() => setSelected(null)} className="absolute right-3 top-3 grid size-8 place-items-center rounded-full hover:bg-paper-2" aria-label="Close">
            <X className="size-4" />
          </button>
          <Badge tone="neutral" className="mb-2">{{ issue: "Community report", event: "Event", warning: "Official alert area", infrastructure: label(ASSET_TYPES, selected.properties.category) }[selected.properties.kind] ?? selected.properties.kind}</Badge>
          <h2 className="pr-8 text-[17px] font-semibold leading-snug">{selected.properties.title}</h2>
          {selected.properties.kind === "warning" && <p className="mt-1 text-[13px] text-slate">Covers {selected.properties.area} · {selected.properties.severity}</p>}
          {selected.properties.kind === "issue" && <p className="mt-1 text-[13px] text-slate">{selected.properties.support} residents affected · {selected.properties.status?.replace(/_/g, " ")}</p>}
          <div className="mt-3 flex gap-3 text-[13.5px] font-medium">
            {selected.properties.kind === "issue" && <Link className="text-teal-600 hover:underline" href={`/issues/${selected.properties.id}`}>Open report</Link>}
            {selected.properties.kind === "event" && <Link className="text-teal-600 hover:underline" href={`/events/${selected.properties.id}`}>Open event</Link>}
            {selected.properties.kind === "warning" && <Link className="text-teal-600 hover:underline" href={`/warnings/${selected.properties.id}`}>Open alert</Link>}
            {selId && <Link className="flex items-center gap-1 text-teal-600 hover:underline" href={`/connections?focus=${selId}`}><Network className="size-4" /> Connections</Link>}
          </div>
          {selId && (
            <div className="mt-4 border-t border-line pt-4">
              <p className="eyebrow mb-2">Connected in the graph</p>
              {neighbors.isLoading ? (
                <div className="skeleton h-16 rounded-lg" />
              ) : neighbors.data ? (
                <ul className="space-y-1.5">
                  {neighbors.data.edges.slice(0, 12).map((e) => {
                    const other = neighbors.data!.nodes.find((n) => n.id === (e.source === selId ? e.target : e.source));
                    return (
                      <li key={e.id} className="flex items-start gap-2 text-[13px]">
                        <span className={cn("mt-1.5 size-1.5 shrink-0 rounded-full", { verified: "bg-navy", community: "bg-teal", inferred: "bg-violet", coordination: "bg-positive", ai: "bg-amber" }[e.class])} />
                        <span>
                          <span className="text-slate">{e.meaning}</span> <b className="font-medium">{other?.name}</b>{" "}
                          <span className="text-[11.5px] text-slate">({LABEL_NAMES[other?.label ?? ""] ?? other?.label})</span>
                        </span>
                      </li>
                    );
                  })}
                  {neighbors.data.edges.length === 0 && <li className="text-[13px] text-slate">No connections yet.</li>}
                </ul>
              ) : null}
            </div>
          )}
        </Card>
      )}
      <p className="pointer-events-none absolute bottom-1 left-2 hidden text-[10.5px] text-slate md:block">{data.data?.attribution}</p>
    </div>
  );
}
