"use client";

import * as Popover from "@radix-ui/react-popover";
import { useQuery } from "@tanstack/react-query";
import { ChevronDown, Home, MapPin } from "lucide-react";
import { useState } from "react";
import { Input } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { cn } from "@/lib/format";
import type { Neighborhood } from "@/lib/types";

export function NeighborhoodPicker({
  value,
  onChange,
  homeLabel,
}: {
  value: { id: string; name: string } | null;
  onChange: (v: { id: string; name: string } | null) => void;
  homeLabel?: string | null;
}) {
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const res = useQuery({
    queryKey: ["nbh-search", q],
    queryFn: () => api.get<{ items: Neighborhood[] }>("/neighborhoods", { q: q || undefined }),
    enabled: open,
  });
  const current = value?.name ?? (homeLabel ? `Home · ${homeLabel}` : "Central Delhi");
  return (
    <Popover.Root open={open} onOpenChange={setOpen}>
      <Popover.Trigger className="inline-flex h-10 items-center gap-2 rounded-[10px] border border-line-strong bg-white px-3.5 text-[14px] font-medium hover:bg-paper-2">
        {value ? <MapPin className="size-4 text-teal" /> : <Home className="size-4 text-teal" />}
        <span className="max-w-48 truncate">{current}</span>
        <ChevronDown className="size-3.5 text-slate" />
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content align="start" sideOffset={6} className="z-50 w-80 rounded-xl border border-line bg-white p-2 shadow-[var(--shadow-lift)]">
          <Input autoFocus value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search 580 mapped neighbourhoods" className="h-10" />
          <ul className="mt-2 max-h-72 overflow-auto">
            {homeLabel !== undefined && (
              <li>
                <button
                  onClick={() => {
                    onChange(null);
                    setOpen(false);
                  }}
                  className={cn("flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-[14px] hover:bg-paper-2", !value && "bg-teal-50")}
                >
                  <Home className="size-4 text-teal" /> {homeLabel ? `Home (${homeLabel})` : "Central Delhi"}
                </button>
              </li>
            )}
            {res.data?.items.map((n) => (
              <li key={n.neighborhood_id}>
                <button
                  onClick={() => {
                    onChange({ id: n.neighborhood_id, name: n.name });
                    setOpen(false);
                  }}
                  className={cn("flex w-full items-center justify-between gap-2 rounded-lg px-3 py-2 text-left text-[14px] hover:bg-paper-2", value?.id === n.neighborhood_id && "bg-teal-50")}
                >
                  <span className="truncate">{n.name}</span>
                  {n.district && <span className="shrink-0 text-[11.5px] text-slate">{n.district}</span>}
                </button>
              </li>
            ))}
          </ul>
          <p className="border-t border-line px-3 pt-2 text-[11px] text-slate">Places © OpenStreetMap contributors</p>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}
