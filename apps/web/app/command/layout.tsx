"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Bot, Brain, CalendarDays, Clapperboard, Database, FolderKanban, Gauge, Inbox, LogOut, Network, ShieldAlert } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { Logo } from "@/components/shell/logo";
import { Button } from "@/components/ui/button";
import { useOperator } from "@/hooks/use-profile";
import { api, ApiError } from "@/lib/api";
import { cn } from "@/lib/format";

const NAV = [
  { href: "/command", label: "Overview", icon: Gauge },
  { href: "/command/incidents", label: "Incident queue", icon: Inbox },
  { href: "/command/cases", label: "Coordination cases", icon: FolderKanban },
  { href: "/command/events", label: "Event coordination", icon: CalendarDays },
  { href: "/command/warnings", label: "Warning intelligence", icon: ShieldAlert },
  { href: "/command/graph", label: "Graph investigation", icon: Network },
  { href: "/command/agents", label: "Agent activity", icon: Bot },
  { href: "/command/memory", label: "City memory", icon: Brain },
  { href: "/command/sources", label: "Source health", icon: Database },
  { href: "/command/demo", label: "Demo scenario", icon: Clapperboard },
];

function Login() {
  const qc = useQueryClient();
  const [u, setU] = useState("");
  const [p, setP] = useState("");
  const login = useMutation({ mutationFn: () => api.post("/operator/login", { username: u, password: p }), onSuccess: () => qc.invalidateQueries({ queryKey: ["operator"] }) });
  return (
    <div className="grid min-h-dvh place-items-center bg-navy-950 px-4">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          login.mutate();
        }}
        className="w-full max-w-sm rounded-2xl border border-white/10 bg-navy p-7 text-white shadow-2xl"
      >
        <Logo inverted suffix="Command" />
        <p className="mt-5 text-[13.5px] leading-relaxed text-white/65">Sign-in for authorised CityPulse coordinators. Separate from resident quick profiles.</p>
        <label className="mt-6 block text-[13px] text-white/80">Username
          <input value={u} onChange={(e) => setU(e.target.value)} autoComplete="username" className="mt-1.5 h-11 w-full rounded-[10px] border border-white/15 bg-white/5 px-3 text-[15px] outline-none focus:border-[#5FC3BF]" />
        </label>
        <label className="mt-4 block text-[13px] text-white/80">Password
          <input type="password" value={p} onChange={(e) => setP(e.target.value)} autoComplete="current-password" className="mt-1.5 h-11 w-full rounded-[10px] border border-white/15 bg-white/5 px-3 text-[15px] outline-none focus:border-[#5FC3BF]" />
        </label>
        {login.error && <p className="mt-3 text-[13px] text-[#f19a9a]">{login.error instanceof ApiError ? login.error.message : "Sign-in failed."}</p>}
        <Button type="submit" variant="accent" className="mt-6 w-full" loading={login.isPending}>Sign in</Button>
        <Link href="/" className="mt-4 block text-center text-[12.5px] text-white/50 hover:text-white/80">← Back to resident app</Link>
      </form>
    </div>
  );
}

export default function CommandLayout({ children }: { children: React.ReactNode }) {
  const { username, isLoading } = useOperator();
  const path = usePathname();
  const qc = useQueryClient();
  if (isLoading) return <div className="min-h-dvh bg-navy-950" />;
  if (!username) return <Login />;
  return (
    <div className="min-h-dvh bg-[#f3f5f2] md:grid md:grid-cols-[248px_1fr]">
      <aside className="bg-navy-950 text-white md:sticky md:top-0 md:h-dvh">
        <div className="flex h-16 items-center px-5"><Logo inverted suffix="Command" /></div>
        <nav className="flex gap-1 overflow-x-auto px-3 pb-3 md:flex-col md:overflow-visible">
          {NAV.map((n) => {
            const on = n.href === "/command" ? path === "/command" : path.startsWith(n.href);
            return (
              <Link key={n.href} href={n.href} className={cn("flex shrink-0 items-center gap-2.5 rounded-lg px-3 py-2 text-[13.5px] text-white/65 hover:bg-white/5 hover:text-white", on && "bg-white/10 text-white")}>
                <n.icon className="size-4" /> {n.label}
              </Link>
            );
          })}
        </nav>
        <div className="hidden px-5 py-4 text-[12px] text-white/50 md:absolute md:bottom-0 md:block md:w-full">
          <p>Signed in as <b className="text-white/80">{username}</b></p>
          <button
            className="mt-2 flex items-center gap-1.5 hover:text-white"
            onClick={async () => {
              await api.post("/operator/logout");
              qc.invalidateQueries({ queryKey: ["operator"] });
            }}
          >
            <LogOut className="size-3.5" /> Sign out
          </button>
          <Link href="/" className="mt-2 block hover:text-white">Resident app ↗</Link>
        </div>
      </aside>
      <main className="min-w-0 px-4 py-6 md:px-8 md:py-8">{children}</main>
    </div>
  );
}
