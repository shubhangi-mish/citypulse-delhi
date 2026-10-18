"use client";

import { useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { cn } from "@/lib/format";
import type { GraphNode } from "@/lib/types";

export const LABEL_NAMES: Record<string, string> = {
  Issue: "Report",
  Event: "Event",
  Warning: "Official alert",
  Neighborhood: "Neighbourhood",
  InfrastructureAsset: "Infrastructure",
  Organization: "Organisation",
  AdministrativeArea: "District",
  CoordinationCase: "Coordination",
  Road: "Road",
  Venue: "Venue",
};

export function hrefFor(n: { id: string; label: string }) {
  if (n.label === "Issue") return `/issues/${n.id}`;
  if (n.label === "Event") return `/events/${n.id}`;
  if (n.label === "Warning") return `/warnings/${n.id}`;
  return `/connections?focus=${n.id}`;
}

export function GraphSearch({ className, onPick, placeholder = "Search places, reports, events, metro stations…" }: { className?: string; onPick?: (n: GraphNode) => void; placeholder?: string }) {
  const [q, setQ] = useState("");
  const [debounced, setDebounced] = useState("");
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(q.trim()), 250);
    return () => clearTimeout(t);
  }, [q]);
  useEffect(() => {
    const close = (e: MouseEvent) => !box.current?.contains(e.target as Node) && setOpen(false);
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);
  const res = useQuery({
    queryKey: ["graph-search", debounced],
    queryFn: () => api.get<{ items: GraphNode[] }>("/graph/search", { q: debounced }),
    enabled: debounced.length >= 2,
  });
  return (
    <div ref={box} className={cn("relative", className)}>
      <Search className="pointer-events-none absolute left-4 top-1/2 size-4 -translate-y-1/2 text-slate" />
      <input
        value={q}
        onChange={(e) => {
          setQ(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        placeholder={placeholder}
        aria-label="Search the city graph"
        className="h-12 w-full rounded-2xl border border-line-strong bg-white pl-11 pr-4 text-[15px] shadow-[var(--shadow-soft)] placeholder:text-slate/70 focus:border-teal focus:outline-none focus:ring-3 focus:ring-teal/15"
      />
      {open && debounced.length >= 2 && (
        <div className="absolute inset-x-0 top-14 z-30 overflow-hidden rounded-2xl border border-line bg-white shadow-[var(--shadow-lift)]">
          {res.isLoading ? (
            <p className="px-4 py-3 text-[13px] text-slate">Searching the graph…</p>
          ) : res.error ? (
            <p className="px-4 py-3 text-[13px] text-critical">Search unavailable.</p>
          ) : !res.data?.items.length ? (
            <p className="px-4 py-3 text-[13px] text-slate">Nothing in the city graph matches “{debounced}”.</p>
          ) : (
            <ul>
              {res.data.items.map((n) => (
                <li key={n.id}>
                  {onPick ? (
                    <button
                      className="flex w-full items-center justify-between gap-3 px-4 py-2.5 text-left hover:bg-paper-2"
                      onClick={() => {
                        onPick(n);
                        setOpen(false);
                        setQ("");
                      }}
                    >
                      <span className="truncate text-[14px]">{n.name}</span>
                      <span className="shrink-0 text-[11.5px] text-slate">{LABEL_NAMES[n.label] ?? n.label}</span>
                    </button>
                  ) : (
                    <Link href={hrefFor(n)} className="flex items-center justify-between gap-3 px-4 py-2.5 hover:bg-paper-2" onClick={() => setOpen(false)}>
                      <span className="truncate text-[14px]">{n.name}</span>
                      <span className="shrink-0 text-[11.5px] text-slate">{LABEL_NAMES[n.label] ?? n.label}</span>
                    </Link>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
