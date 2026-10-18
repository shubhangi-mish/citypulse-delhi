"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";

export type RadiusKm = 1 | 3 | 5 | 10;
export type FeedKind = "all" | "complaints" | "events" | "community" | "warnings" | "following";
export type Layer = "issues" | "events" | "warnings" | "infrastructure" | "neighborhoods";

interface DiscoveryState {
  radius: RadiusKm;
  neighborhood: { id: string; name: string } | null;
  kind: FeedKind;
  layers: Layer[];
  setRadius: (r: RadiusKm) => void;
  setNeighborhood: (n: { id: string; name: string } | null) => void;
  setKind: (k: FeedKind) => void;
  toggleLayer: (l: Layer) => void;
}

export const useDiscovery = create<DiscoveryState>()(
  persist(
    (set) => ({
      radius: 3,
      neighborhood: null,
      kind: "all",
      layers: ["issues", "events", "warnings"],
      setRadius: (radius) => set({ radius }),
      setNeighborhood: (neighborhood) => set({ neighborhood }),
      setKind: (kind) => set({ kind }),
      toggleLayer: (l) => set((s) => ({ layers: s.layers.includes(l) ? s.layers.filter((x) => x !== l) : [...s.layers, l] })),
    }),
    { name: "citypulse-discovery" },
  ),
);
