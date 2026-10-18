"use client";

import * as Dropdown from "@radix-ui/react-dropdown-menu";
import * as Popover from "@radix-ui/react-popover";
import { useQueryClient } from "@tanstack/react-query";
import { Bell, CalendarPlus, ChevronDown, Compass, Home, Info, LogOut, Map, MapPin, Megaphone, Network, Plus, Settings, User } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useNotifications, useProfile } from "@/hooks/use-profile";
import { api } from "@/lib/api";
import { cn, timeAgo } from "@/lib/format";
import { Button } from "../ui/button";
import { Logo } from "./logo";

const NAV = [
  { href: "/", label: "Home" },
  { href: "/explore", label: "Explore" },
  { href: "/around-you", label: "Around You" },
  { href: "/events", label: "Events" },
  { href: "/warnings", label: "Warnings" },
  { href: "/my-activity", label: "My Activity" },
];
const MORE = [
  { href: "/connections", label: "City Connections", icon: Network },
  { href: "/profile", label: "Profile & privacy", icon: Settings },
  { href: "/about", label: "About CityPulse", icon: Info },
];
const MOBILE = [
  { href: "/", label: "Home", icon: Home },
  { href: "/explore", label: "Explore", icon: Map },
  { href: "/around-you", label: "Around", icon: Compass },
  { href: "/report", label: "Report", icon: Plus },
  { href: "/profile", label: "Profile", icon: User },
];

function active(path: string, href: string) {
  return href === "/" ? path === "/" : path.startsWith(href);
}

export function ResidentShell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const { profile } = useProfile();

  return (
    <div className="min-h-dvh pb-20 md:pb-0">
      {profile?.demo && (
        <div className="sticky top-0 z-50 flex flex-wrap items-center justify-center gap-x-4 gap-y-1 bg-amber px-4 py-2 text-[13px] font-medium text-white">
          <span>You're viewing CityPulse as <b>{profile.name}</b>{profile.profession ? ` (${profile.profession})` : ""} — a synthetic demo persona.</span>
          <BackToMe />
        </div>
      )}
      <header className="sticky top-0 z-40 border-b border-line/80 bg-paper/85 backdrop-blur-md">
        <div className="container-page flex h-16 items-center gap-6">
          <Link href="/" aria-label="CityPulse Delhi home">
            <Logo />
          </Link>
          <nav className="hidden items-center gap-0.5 lg:flex" aria-label="Main">
            {NAV.map((n) => (
              <Link
                key={n.href}
                href={n.href}
                className={cn(
                  "rounded-lg px-3 py-2 text-[14px] font-medium text-slate transition-colors hover:text-ink",
                  active(path, n.href) && "text-ink",
                )}
              >
                <span className={cn("relative", active(path, n.href) && "after:absolute after:-bottom-[21px] after:left-0 after:h-0.5 after:w-full after:rounded-full after:bg-teal")}>{n.label}</span>
              </Link>
            ))}
            <Dropdown.Root>
              <Dropdown.Trigger className="flex items-center gap-1 rounded-lg px-3 py-2 text-[14px] font-medium text-slate hover:text-ink">
                More <ChevronDown className="size-3.5" />
              </Dropdown.Trigger>
              <Dropdown.Portal>
                <Dropdown.Content align="start" sideOffset={8} className="z-50 min-w-52 rounded-xl border border-line bg-white p-1.5 shadow-[var(--shadow-lift)]">
                  {MORE.map((m) => (
                    <Dropdown.Item key={m.href} asChild>
                      <Link href={m.href} className="flex items-center gap-2.5 rounded-lg px-3 py-2 text-[14px] outline-none data-[highlighted]:bg-paper-2">
                        <m.icon className="size-4 text-slate" /> {m.label}
                      </Link>
                    </Dropdown.Item>
                  ))}
                </Dropdown.Content>
              </Dropdown.Portal>
            </Dropdown.Root>
          </nav>
          <div className="ml-auto flex items-center gap-2">
            <CreateMenu />
            {profile ? <NotificationBell /> : null}
            {profile ? (
              <ProfileMenu name={profile.name} neighborhood={profile.neighborhood_name} />
            ) : (
              <Button asChild size="sm" variant="outline">
                <Link href="/onboarding">Continue as a resident</Link>
              </Button>
            )}
          </div>
        </div>
      </header>

      <main>{children}</main>

      <footer className="mt-24 hidden border-t border-line py-10 md:block">
        <div className="container-page flex flex-wrap items-center justify-between gap-4 text-[13px] text-slate">
          <span>
            CityPulse Delhi is an independent community platform. Reports are shared with the CityPulse community, not filed with government departments.
          </span>
          <span>
            Map data © OpenStreetMap contributors · Alerts: NDMA SACHET · <Link className="underline" href="/about">Sources & privacy</Link>
          </span>
        </div>
      </footer>

      <nav aria-label="Mobile" className="fixed inset-x-0 bottom-0 z-40 border-t border-line bg-white/95 pb-[env(safe-area-inset-bottom)] backdrop-blur md:hidden">
        <div className="grid grid-cols-5">
          {MOBILE.map((m) => {
            const on = active(path, m.href);
            const isReport = m.href === "/report";
            if (isReport) {
              return (
                <Dropdown.Root key={m.href}>
                  <Dropdown.Trigger className="flex flex-col items-center gap-1 py-2.5 text-[11px] font-medium text-slate" aria-label="Add a report or event">
                    <span className="-mt-1 grid size-8 place-items-center rounded-full bg-teal text-white">
                      <Plus className="size-4" />
                    </span>
                    Add
                  </Dropdown.Trigger>
                  <Dropdown.Portal>
                    <Dropdown.Content side="top" sideOffset={10} className="z-50 min-w-56 rounded-xl border border-line bg-white p-1.5 shadow-[var(--shadow-lift)]">
                      <CreateItems />
                    </Dropdown.Content>
                  </Dropdown.Portal>
                </Dropdown.Root>
              );
            }
            return (
              <Link key={m.href} href={m.href} className={cn("flex flex-col items-center gap-1 py-2.5 text-[11px] font-medium", on ? "text-teal" : "text-slate")}>
                <span className={cn("grid place-items-center", isReport && "size-8 -mt-1 rounded-full bg-teal text-white")}>
                  <m.icon className={cn(isReport ? "size-4" : "size-5")} />
                </span>
                {m.label}
              </Link>
            );
          })}
        </div>
      </nav>
    </div>
  );
}

function BackToMe() {
  const qc = useQueryClient();
  const router = useRouter();
  return (
    <button
      className="rounded-full bg-white/20 px-3 py-0.5 hover:bg-white/30"
      onClick={async () => {
        await api.post("/demo/restore-session");
        await qc.invalidateQueries();
        router.push("/command/demo");
      }}
    >
      Back to my account
    </button>
  );
}

function CreateItems() {
  return (
    <>
      <Dropdown.Item asChild>
        <Link href="/report" className="flex items-start gap-3 rounded-lg px-3 py-2.5 outline-none data-[highlighted]:bg-paper-2">
          <Megaphone className="mt-0.5 size-4 text-teal" />
          <span>
            <span className="block text-[14px] font-medium">Report an issue</span>
            <span className="block text-[12px] text-slate">Something that needs fixing</span>
          </span>
        </Link>
      </Dropdown.Item>
      <Dropdown.Item asChild>
        <Link href="/events/create" className="flex items-start gap-3 rounded-lg px-3 py-2.5 outline-none data-[highlighted]:bg-paper-2">
          <CalendarPlus className="mt-0.5 size-4 text-violet" />
          <span>
            <span className="block text-[14px] font-medium">Share an event</span>
            <span className="block text-[12px] text-slate">A cleanup, meeting, workshop…</span>
          </span>
        </Link>
      </Dropdown.Item>
    </>
  );
}

function CreateMenu() {
  return (
    <Dropdown.Root>
      <Dropdown.Trigger asChild>
        <Button size="sm" variant="accent" className="hidden md:inline-flex">
          <Plus /> Add <ChevronDown className="size-3.5" />
        </Button>
      </Dropdown.Trigger>
      <Dropdown.Portal>
        <Dropdown.Content align="end" sideOffset={8} className="z-50 min-w-60 rounded-xl border border-line bg-white p-1.5 shadow-[var(--shadow-lift)]">
          <CreateItems />
        </Dropdown.Content>
      </Dropdown.Portal>
    </Dropdown.Root>
  );
}

function ProfileMenu({ name, neighborhood }: { name: string; neighborhood: string | null }) {
  const qc = useQueryClient();
  const router = useRouter();
  const initials = name
    .split(" ")
    .map((p) => p[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
  return (
    <Dropdown.Root>
      <Dropdown.Trigger className="flex items-center gap-2 rounded-full p-0.5 pr-2 hover:bg-paper-2" aria-label="Profile menu">
        <span className="grid size-8 place-items-center rounded-full bg-teal-50 text-[12px] font-semibold text-teal-600">{initials}</span>
        <span className="hidden text-left leading-tight xl:block">
          <span className="block text-[13px] font-medium">{name}</span>
          {neighborhood && <span className="block text-[11.5px] text-slate">{neighborhood}</span>}
        </span>
      </Dropdown.Trigger>
      <Dropdown.Portal>
        <Dropdown.Content align="end" sideOffset={8} className="z-50 min-w-56 rounded-xl border border-line bg-white p-1.5 shadow-[var(--shadow-lift)]">
          <div className="px-3 py-2 text-[12px] text-slate">
            Quick profile · <span className="text-amber">not identity-verified</span>
          </div>
          {[
            { href: "/my-activity", label: "My activity", icon: MapPin },
            { href: "/profile", label: "Profile & privacy", icon: Settings },
          ].map((m) => (
            <Dropdown.Item key={m.href} asChild>
              <Link href={m.href} className="flex items-center gap-2.5 rounded-lg px-3 py-2 text-[14px] outline-none data-[highlighted]:bg-paper-2">
                <m.icon className="size-4 text-slate" /> {m.label}
              </Link>
            </Dropdown.Item>
          ))}
          <Dropdown.Item
            onSelect={async () => {
              if (!confirm("Quick profiles can't be recovered by email. If you leave this session you won't be able to get back to this profile. Continue?")) return;
              await api.post("/profiles/me/sign-out");
              await qc.invalidateQueries();
              router.push("/");
            }}
            className="flex cursor-pointer items-center gap-2.5 rounded-lg px-3 py-2 text-[14px] outline-none data-[highlighted]:bg-paper-2"
          >
            <LogOut className="size-4 text-slate" /> Leave this browser session
          </Dropdown.Item>
        </Dropdown.Content>
      </Dropdown.Portal>
    </Dropdown.Root>
  );
}

function NotificationBell() {
  const { data } = useNotifications(true);
  const qc = useQueryClient();
  const unread = data?.unread ?? 0;
  return (
    <Popover.Root
      onOpenChange={async (open) => {
        if (!open && unread) {
          await api.post("/profiles/me/notifications/read");
          qc.invalidateQueries({ queryKey: ["notifications"] });
        }
      }}
    >
      <Popover.Trigger className="relative grid size-9 place-items-center rounded-full hover:bg-paper-2" aria-label={`Notifications${unread ? `, ${unread} unread` : ""}`}>
        <Bell className="size-[18px]" />
        {unread > 0 && <span className="absolute right-1.5 top-1.5 size-2 rounded-full bg-critical ring-2 ring-paper" />}
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content align="end" sideOffset={8} className="z-50 w-80 rounded-xl border border-line bg-white p-2 shadow-[var(--shadow-lift)]">
          <div className="px-2 py-1.5 text-[13px] font-semibold">Notifications</div>
          {!data?.items.length ? (
            <p className="px-2 py-6 text-center text-[13px] text-slate">Nothing yet. Follow a report or join an event to get updates here.</p>
          ) : (
            <ul className="max-h-96 overflow-auto">
              {data.items.map((n) => (
                <li key={n.id}>
                  <Link
                    href={n.entity_id.startsWith("evt_") ? `/events/${n.entity_id}` : n.entity_id.startsWith("iss_") ? `/issues/${n.entity_id}` : "/my-activity"}
                    className={cn("block rounded-lg px-2 py-2 hover:bg-paper-2", !n.read && "bg-teal-50/60")}
                  >
                    <p className="text-[13.5px] leading-snug">{n.message}</p>
                    <p className="mt-0.5 text-[11.5px] text-slate">{timeAgo(Date.parse(n.created_at))}</p>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}
