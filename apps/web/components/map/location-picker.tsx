"use client";

import { useQuery } from "@tanstack/react-query";
import { Crosshair, Loader2, MapPin, Search } from "lucide-react";
import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { cn } from "@/lib/format";
import type { Neighborhood } from "@/lib/types";
import { Button } from "../ui/button";
import { Input } from "../ui/primitives";

const MapView = dynamic(() => import("./map-view").then((m) => m.MapView), { ssr: false, loading: () => <div className="skeleton h-full w-full" /> });

export interface PickedLocation {
  latitude: number;
  longitude: number;
  address: string;
  neighborhood_id: string | null;
  neighborhood_name: string | null;
}

interface GeoResult {
  label: string;
  latitude: number;
  longitude: number;
}

export function LocationPicker({
  value,
  onChange,
  addressLabel = "Address or landmark",
  placeholder = "Search an address, landmark or locality in Delhi",
  mapHeight = "h-64",
  privacyNote,
}: {
  value: PickedLocation | null;
  onChange: (v: PickedLocation | null) => void;
  addressLabel?: string;
  placeholder?: string;
  mapHeight?: string;
  privacyNote?: React.ReactNode;
}) {
  const [query, setQuery] = useState(value?.address ?? "");
  const [submitted, setSubmitted] = useState("");
  const [locating, setLocating] = useState(false);
  const geo = useQuery({ queryKey: ["geo-config"], queryFn: () => api.get<{ provider: "mapbox" | "nominatim" }>("/geo/config"), staleTime: Infinity });
  const autocomplete = geo.data?.provider === "mapbox";

  // Mapbox supports type-ahead; Nominatim's usage policy does not, so search on submit there.
  useEffect(() => {
    if (!autocomplete) return;
    const t = setTimeout(() => setSubmitted(query.trim()), 350);
    return () => clearTimeout(t);
  }, [query, autocomplete]);

  const results = useQuery({
    queryKey: ["geo-search", submitted],
    queryFn: () => api.get<{ provider: string; attribution: string; results: GeoResult[] }>("/geo/search", { q: submitted }),
    enabled: submitted.length >= 3 && submitted !== value?.address,
  });

  const nearby = useQuery({
    queryKey: ["nbh-near", value?.latitude?.toFixed(4), value?.longitude?.toFixed(4)],
    queryFn: () => api.get<{ items: Neighborhood[] }>("/neighborhoods", { lat: value!.latitude, lng: value!.longitude }),
    enabled: !!value,
  });

  // default the neighbourhood to the nearest real OSM place
  useEffect(() => {
    if (value && !value.neighborhood_id && nearby.data?.items?.[0]) {
      const n = nearby.data.items[0];
      onChange({ ...value, neighborhood_id: n.neighborhood_id, neighborhood_name: n.name });
    }
  }, [nearby.data]); // eslint-disable-line react-hooks/exhaustive-deps

  const setPoint = (lat: number, lng: number, address?: string) =>
    onChange({ latitude: lat, longitude: lng, address: address ?? value?.address ?? query, neighborhood_id: null, neighborhood_name: null });

  const showResults = results.data && submitted && submitted !== value?.address;

  return (
    <div className="space-y-3">
      <div>
        <label className="mb-1.5 block text-[13.5px] font-medium">{addressLabel}</label>
        <div className="relative">
          <Search className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-slate" />
          <Input
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              if (value) onChange({ ...value, address: e.target.value });
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                setSubmitted(query.trim());
              }
            }}
            placeholder={placeholder}
            className="pl-10 pr-28"
            aria-label={addressLabel}
          />
          <div className="absolute right-1.5 top-1/2 flex -translate-y-1/2 gap-1">
            {!autocomplete && (
              <Button type="button" size="sm" variant="ghost" onClick={() => setSubmitted(query.trim())}>
                Search
              </Button>
            )}
            <Button
              type="button"
              size="icon"
              variant="ghost"
              className="size-8"
              title="Use my current location"
              aria-label="Use my current location"
              onClick={() => {
                if (!navigator.geolocation) return;
                setLocating(true);
                navigator.geolocation.getCurrentPosition(
                  (p) => {
                    setLocating(false);
                    setPoint(p.coords.latitude, p.coords.longitude, query || "My current location");
                  },
                  () => setLocating(false),
                  { enableHighAccuracy: true, timeout: 8000 },
                );
              }}
            >
              {locating ? <Loader2 className="animate-spin" /> : <Crosshair />}
            </Button>
          </div>
        </div>
        {results.isFetching && <p className="mt-2 text-[12.5px] text-slate">Searching…</p>}
        {results.error && <p className="mt-2 text-[12.5px] text-critical">{results.error instanceof ApiError ? results.error.message : "Search failed."}</p>}
        {showResults && (
          <ul className="mt-2 overflow-hidden rounded-xl border border-line bg-white">
            {results.data!.results.length === 0 && <li className="px-4 py-3 text-[13px] text-slate">No matches in Delhi. Try a landmark, or drop a pin on the map.</li>}
            {results.data!.results.map((r, i) => (
              <li key={i}>
                <button
                  type="button"
                  className="flex w-full items-start gap-2.5 px-4 py-2.5 text-left text-[13.5px] hover:bg-paper-2"
                  onClick={() => {
                    setQuery(r.label);
                    setSubmitted(r.label);
                    setPoint(r.latitude, r.longitude, r.label);
                  }}
                >
                  <MapPin className="mt-0.5 size-4 shrink-0 text-teal" />
                  {r.label}
                </button>
              </li>
            ))}
            <li className="border-t border-line px-4 py-1.5 text-[11px] text-slate">{results.data!.attribution}</li>
          </ul>
        )}
      </div>

      <div className={cn("overflow-hidden rounded-xl border border-line", mapHeight)}>
        <MapView center={value ? { latitude: value.latitude, longitude: value.longitude } : null} zoom={11} pick={value} onPick={(p) => setPoint(p.latitude, p.longitude)} />
      </div>
      <p className="text-[12.5px] text-slate">Click the map or drag the pin to correct the location.</p>

      {value && (
        <div className="rounded-xl border border-line bg-paper-2/60 p-3.5">
          <p className="mb-2 text-[13px] font-medium">Neighbourhood</p>
          {nearby.isLoading ? (
            <p className="text-[13px] text-slate">Finding the nearest mapped places…</p>
          ) : nearby.data?.items.length ? (
            <div className="flex flex-wrap gap-1.5">
              {nearby.data.items.slice(0, 6).map((n) => (
                <button
                  type="button"
                  key={n.neighborhood_id}
                  onClick={() => onChange({ ...value, neighborhood_id: n.neighborhood_id, neighborhood_name: n.name })}
                  className={cn(
                    "rounded-full border px-3 py-1 text-[12.5px]",
                    value.neighborhood_id === n.neighborhood_id ? "border-teal bg-teal-50 text-teal-600" : "border-line-strong bg-white hover:border-slate/50",
                  )}
                >
                  {n.name}
                  {n.district ? <span className="text-slate"> · {n.district}</span> : null}
                </button>
              ))}
            </div>
          ) : (
            <p className="text-[13px] text-slate">No mapped OpenStreetMap place within 5 km of this point.</p>
          )}
          {privacyNote && <p className="mt-2.5 text-[12px] text-slate">{privacyNote}</p>}
        </div>
      )}
    </div>
  );
}
