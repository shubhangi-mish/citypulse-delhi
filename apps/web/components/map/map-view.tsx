"use client";
import type * as GeoJSON from "geojson";

import mapboxgl from "mapbox-gl";
import { MapPinOff } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/format";

export const MAPBOX_TOKEN = process.env.NEXT_PUBLIC_MAPBOX_TOKEN || "";
export const DELHI: [number, number] = [77.209, 28.6139];

export const KIND_COLORS: Record<string, string> = {
  issue: "#157C83",
  event: "#6D5BB8",
  warning: "#C98B31",
  infrastructure: "#64748B",
  neighborhood: "#172B45",
};

export type MapFeature = GeoJSON.Feature<GeoJSON.Point, { kind: string; id: string; title: string; [k: string]: any }>;

interface Props {
  center?: { latitude: number; longitude: number } | null;
  zoom?: number;
  features?: MapFeature[];
  radiusKm?: number | null;
  selectedId?: string | null;
  onSelect?: (f: MapFeature | null) => void;
  pick?: { latitude: number; longitude: number } | null;
  onPick?: (p: { latitude: number; longitude: number }) => void;
  onBoundsChange?: (b: { min_lat: number; min_lng: number; max_lat: number; max_lng: number }) => void;
  className?: string;
  interactive?: boolean;
}

function circle(lng: number, lat: number, km: number): GeoJSON.Feature<GeoJSON.Polygon> {
  const pts: [number, number][] = [];
  for (let i = 0; i <= 64; i++) {
    const a = (i / 64) * 2 * Math.PI;
    pts.push([lng + (km / (111.32 * Math.cos((lat * Math.PI) / 180))) * Math.cos(a), lat + (km / 110.574) * Math.sin(a)]);
  }
  return { type: "Feature", geometry: { type: "Polygon", coordinates: [pts] }, properties: {} };
}

const KINDS = ["neighborhood", "infrastructure", "issue", "event", "warning"] as const;

export function MapView({ center, zoom = 12, features = [], radiusKm, selectedId, onSelect, pick, onPick, onBoundsChange, className, interactive = true }: Props) {
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<mapboxgl.Map | null>(null);
  const pickMarker = useRef<mapboxgl.Marker | null>(null);
  const [ready, setReady] = useState(false);
  const handlers = useRef({ onSelect, onPick, onBoundsChange });
  handlers.current = { onSelect, onPick, onBoundsChange };

  useEffect(() => {
    if (!MAPBOX_TOKEN || !el.current || map.current) return;
    mapboxgl.accessToken = MAPBOX_TOKEN;
    const m = new mapboxgl.Map({
      container: el.current,
      style: "mapbox://styles/mapbox/light-v11",
      center: center ? [center.longitude, center.latitude] : DELHI,
      zoom,
      interactive,
      attributionControl: true,
      cooperativeGestures: false,
    });
    map.current = m;
    if (interactive) m.addControl(new mapboxgl.NavigationControl({ showCompass: false }), "top-right");

    m.on("load", () => {
      m.addSource("radius", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
      m.addLayer({ id: "radius-fill", type: "fill", source: "radius", paint: { "fill-color": "#157C83", "fill-opacity": 0.06 } });
      m.addLayer({ id: "radius-line", type: "line", source: "radius", paint: { "line-color": "#157C83", "line-width": 1.5, "line-dasharray": [2, 2] } });

      for (const kind of KINDS) {
        const clustered = kind === "issue" || kind === "infrastructure";
        m.addSource(`src-${kind}`, {
          type: "geojson",
          data: { type: "FeatureCollection", features: [] },
          ...(clustered ? { cluster: true, clusterRadius: 42, clusterMaxZoom: 14 } : {}),
          promoteId: "id",
        });
        const color = KIND_COLORS[kind];
        if (clustered) {
          m.addLayer({
            id: `cluster-${kind}`,
            type: "circle",
            source: `src-${kind}`,
            filter: ["has", "point_count"],
            paint: { "circle-color": color, "circle-opacity": 0.88, "circle-radius": ["step", ["get", "point_count"], 15, 10, 19, 50, 24], "circle-stroke-width": 3, "circle-stroke-color": "#fff" },
          });
          m.addLayer({
            id: `cluster-count-${kind}`,
            type: "symbol",
            source: `src-${kind}`,
            filter: ["has", "point_count"],
            layout: { "text-field": ["get", "point_count_abbreviated"], "text-size": 12, "text-font": ["DIN Pro Medium", "Arial Unicode MS Bold"] },
            paint: { "text-color": "#fff" },
          });
        }
        if (kind === "neighborhood") {
          m.addLayer({
            id: `pt-${kind}`,
            type: "symbol",
            source: `src-${kind}`,
            minzoom: 11.5,
            layout: { "text-field": ["get", "title"], "text-size": 11, "text-font": ["DIN Pro Medium", "Arial Unicode MS Regular"], "text-letter-spacing": 0.04 },
            paint: { "text-color": "#172B45", "text-halo-color": "#fff", "text-halo-width": 1.4, "text-opacity": 0.7 },
          });
          continue;
        }
        m.addLayer({
          id: `pt-${kind}`,
          type: "circle",
          source: `src-${kind}`,
          filter: ["!", ["has", "point_count"]],
          paint: {
            "circle-color": kind === "warning" ? ["match", ["get", "severity"], "Extreme", "#C74848", "Severe", "#C74848", color] : color,
            "circle-radius": kind === "infrastructure" ? ["interpolate", ["linear"], ["zoom"], 11, 3, 15, 6] : ["case", ["boolean", ["feature-state", "selected"], false], 10, 7],
            "circle-stroke-width": kind === "infrastructure" ? 1 : ["case", ["boolean", ["feature-state", "selected"], false], 4, 2.5],
            "circle-stroke-color": "#fff",
            "circle-opacity": kind === "warning" ? 0.75 : 1,
          },
        });
      }

      const clickable = KINDS.filter((k) => k !== "neighborhood").map((k) => `pt-${k}`);
      m.on("click", (e) => {
        const hits = m.queryRenderedFeatures(e.point, { layers: clickable });
        const clusters = m.queryRenderedFeatures(e.point, { layers: ["cluster-issue", "cluster-infrastructure"] });
        if (clusters.length) {
          m.easeTo({ center: e.lngLat, zoom: m.getZoom() + 2 });
          return;
        }
        if (hits.length) {
          handlers.current.onSelect?.(hits[0] as unknown as MapFeature);
        } else if (handlers.current.onPick) {
          handlers.current.onPick({ latitude: e.lngLat.lat, longitude: e.lngLat.lng });
        } else {
          handlers.current.onSelect?.(null);
        }
      });
      for (const layer of [...clickable, "cluster-issue", "cluster-infrastructure"]) {
        m.on("mouseenter", layer, () => (m.getCanvas().style.cursor = "pointer"));
        m.on("mouseleave", layer, () => (m.getCanvas().style.cursor = ""));
      }
      const emitBounds = () => {
        const b = m.getBounds();
        if (b) handlers.current.onBoundsChange?.({ min_lat: b.getSouth(), min_lng: b.getWest(), max_lat: b.getNorth(), max_lng: b.getEast() });
      };
      m.on("moveend", emitBounds);
      emitBounds();
      setReady(true);
    });
    return () => {
      m.remove();
      map.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // data
  useEffect(() => {
    const m = map.current;
    if (!m || !ready) return;
    for (const kind of KINDS) {
      const src = m.getSource(`src-${kind}`) as mapboxgl.GeoJSONSource | undefined;
      src?.setData({ type: "FeatureCollection", features: features.filter((f) => f.properties.kind === kind) });
    }
  }, [features, ready]);

  // centre + radius
  useEffect(() => {
    const m = map.current;
    if (!m || !ready || !center) return;
    m.easeTo({ center: [center.longitude, center.latitude], duration: 600 });
    const src = m.getSource("radius") as mapboxgl.GeoJSONSource | undefined;
    src?.setData(radiusKm ? circle(center.longitude, center.latitude, radiusKm) : { type: "FeatureCollection", features: [] });
    if (radiusKm) {
      const z = { 1: 14, 3: 12.6, 5: 11.9, 10: 10.9 }[radiusKm as 1 | 3 | 5 | 10] ?? 12;
      m.easeTo({ center: [center.longitude, center.latitude], zoom: z, duration: 600 });
    }
  }, [center?.latitude, center?.longitude, radiusKm, ready]); // eslint-disable-line react-hooks/exhaustive-deps

  // selection highlight
  useEffect(() => {
    const m = map.current;
    if (!m || !ready) return;
    for (const kind of ["issue", "event", "warning"]) m.removeFeatureState({ source: `src-${kind}` });
    if (selectedId) {
      const kind = selectedId.startsWith("iss_") ? "issue" : selectedId.startsWith("evt_") ? "event" : selectedId.startsWith("wrn_") ? "warning" : null;
      if (kind) m.setFeatureState({ source: `src-${kind}`, id: selectedId }, { selected: true });
    }
  }, [selectedId, ready, features]);

  // picked location marker
  useEffect(() => {
    const m = map.current;
    if (!m || !ready) return;
    if (!pick) {
      pickMarker.current?.remove();
      pickMarker.current = null;
      return;
    }
    if (!pickMarker.current) {
      pickMarker.current = new mapboxgl.Marker({ color: "#157C83", draggable: true })
        .setLngLat([pick.longitude, pick.latitude])
        .addTo(m);
      pickMarker.current.on("dragend", () => {
        const p = pickMarker.current!.getLngLat();
        handlers.current.onPick?.({ latitude: p.lat, longitude: p.lng });
      });
    } else {
      pickMarker.current.setLngLat([pick.longitude, pick.latitude]);
    }
    m.easeTo({ center: [pick.longitude, pick.latitude], zoom: Math.max(m.getZoom(), 15), duration: 500 });
  }, [pick?.latitude, pick?.longitude, ready]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!MAPBOX_TOKEN) {
    return (
      <div className={cn("relative grid place-items-center overflow-hidden bg-[#e9ece6]", className)}>
        <svg className="absolute inset-0 h-full w-full opacity-40" aria-hidden="true">
          <defs>
            <pattern id="grid" width="28" height="28" patternUnits="userSpaceOnUse">
              <path d="M28 0H0V28" fill="none" stroke="#cfd4cc" strokeWidth="1" />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#grid)" />
        </svg>
        <div className="relative mx-6 max-w-sm rounded-xl border border-line bg-white/90 p-5 text-center shadow-[var(--shadow-soft)]">
          <MapPinOff className="mx-auto mb-2 size-5 text-slate" />
          <p className="text-[14px] font-semibold">Map needs a Mapbox token</p>
          <p className="mt-1 text-[13px] leading-relaxed text-slate">
            Set <code className="rounded bg-paper-2 px-1">NEXT_PUBLIC_MAPBOX_TOKEN</code> in <code className="rounded bg-paper-2 px-1">.env</code>. Everything else, including radius discovery, keeps working.
          </p>
        </div>
      </div>
    );
  }
  return <div ref={el} className={cn("h-full w-full", className)} role="application" aria-label="Map of Delhi" />;
}
