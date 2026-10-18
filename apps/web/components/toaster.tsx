"use client";

import { AnimatePresence, motion } from "framer-motion";
import { CheckCircle2, Info, XCircle } from "lucide-react";
import { create } from "zustand";

type Toast = { id: number; kind: "success" | "error" | "info"; text: string };
const useToasts = create<{ items: Toast[]; push: (t: Omit<Toast, "id">) => void; drop: (id: number) => void }>((set) => ({
  items: [],
  push: (t) => {
    const id = Date.now() + Math.random();
    set((s) => ({ items: [...s.items, { ...t, id }] }));
    setTimeout(() => set((s) => ({ items: s.items.filter((x) => x.id !== id) })), 4200);
  },
  drop: (id) => set((s) => ({ items: s.items.filter((x) => x.id !== id) })),
}));

export const toast = {
  success: (text: string) => useToasts.getState().push({ kind: "success", text }),
  error: (text: string) => useToasts.getState().push({ kind: "error", text }),
  info: (text: string) => useToasts.getState().push({ kind: "info", text }),
};

export function Toaster() {
  const { items, drop } = useToasts();
  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-20 z-[100] flex flex-col items-center gap-2 px-4 md:bottom-6" aria-live="polite">
      <AnimatePresence>
        {items.map((t) => (
          <motion.button
            key={t.id}
            onClick={() => drop(t.id)}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 8 }}
            className="pointer-events-auto flex max-w-md items-center gap-2.5 rounded-xl bg-navy px-4 py-3 text-left text-[14px] text-white shadow-[var(--shadow-lift)]"
          >
            {t.kind === "success" ? <CheckCircle2 className="size-4 text-[#7fd1c0]" /> : t.kind === "error" ? <XCircle className="size-4 text-[#f19a9a]" /> : <Info className="size-4" />}
            {t.text}
          </motion.button>
        ))}
      </AnimatePresence>
    </div>
  );
}
