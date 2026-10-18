"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Download, Trash2, User } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { LocationPicker, type PickedLocation } from "@/components/map/location-picker";
import { toast } from "@/components/toaster";
import { Button } from "@/components/ui/button";
import { Card, Field, Input, Switch } from "@/components/ui/primitives";
import { EmptyState, PageHeader } from "@/components/ui/states";
import { useProfile } from "@/hooks/use-profile";
import { api, ApiError } from "@/lib/api";
import type { Profile } from "@/lib/types";

function Toggle({ title, body, checked, onChange }: { title: string; body: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="flex items-start justify-between gap-6 border-b border-line py-4 last:border-0">
      <span>
        <span className="block text-[14.5px] font-medium">{title}</span>
        <span className="mt-0.5 block text-[13px] leading-relaxed text-slate">{body}</span>
      </span>
      <Switch checked={checked} onCheckedChange={onChange} />
    </label>
  );
}

export default function ProfilePage() {
  const { profile, isLoading } = useProfile();
  const qc = useQueryClient();
  const router = useRouter();
  const [name, setName] = useState<string | null>(null);
  const [moving, setMoving] = useState(false);
  const [loc, setLoc] = useState<PickedLocation | null>(null);
  const update = useMutation({
    mutationFn: (body: Partial<Profile> & { location?: any }) => api.patch<Profile>("/profiles/me", body),
    onSuccess: () => {
      toast.success("Saved.");
      qc.invalidateQueries();
      setMoving(false);
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Could not save."),
  });
  const del = useMutation({
    mutationFn: () => api.del("/profiles/me"),
    onSuccess: async () => {
      await qc.invalidateQueries();
      toast.success("Your profile was deleted.");
      router.push("/");
    },
  });

  if (!isLoading && !profile)
    return (
      <div className="container-page max-w-2xl py-16">
        <EmptyState icon={<User />} title="No profile in this browser" action={<Button asChild><Link href="/onboarding">Continue as a resident</Link></Button>} />
      </div>
    );
  if (!profile) return null;

  return (
    <div className="container-page max-w-3xl py-10">
      <PageHeader eyebrow="Profile & privacy" title="Your quick profile" description="Passwordless and tied to this browser. It isn't verified identity, and your email is never used to sign in." />
      <div className="space-y-6">
        <Card className="p-6">
          <div className="grid gap-4 sm:grid-cols-[1fr_auto] sm:items-end">
            <Field label="Name" htmlFor="name">
              <Input id="name" value={name ?? profile.name} onChange={(e) => setName(e.target.value)} />
            </Field>
            <Button disabled={!name || name === profile.name} loading={update.isPending} onClick={() => update.mutate({ name: name! })}>Save</Button>
          </div>
          <dl className="mt-5 grid gap-3 text-[14px] sm:grid-cols-2">
            <div><dt className="text-[12px] text-slate">Email (private)</dt><dd>{profile.email}</dd></div>
            <div><dt className="text-[12px] text-slate">Neighbourhood (public)</dt><dd>{profile.neighborhood_name ?? "Not matched"}</dd></div>
            <div className="sm:col-span-2"><dt className="text-[12px] text-slate">Address (private — never shown to others)</dt><dd>{profile.address}</dd></div>
          </dl>
          {!moving ? (
            <Button variant="outline" size="sm" className="mt-4" onClick={() => setMoving(true)}>Change address</Button>
          ) : (
            <div className="mt-5 space-y-3">
              <LocationPicker value={loc} onChange={setLoc} addressLabel="New address" />
              <div className="flex gap-2">
                <Button disabled={!loc} loading={update.isPending} onClick={() => update.mutate({ location: { address: loc!.address || "Pinned location", latitude: loc!.latitude, longitude: loc!.longitude, neighborhood_id: loc!.neighborhood_id } })}>Save address</Button>
                <Button variant="ghost" onClick={() => setMoving(false)}>Cancel</Button>
              </div>
            </div>
          )}
        </Card>

        <Card className="p-6">
          <p className="text-[14.5px] font-medium">Work & availability</p>
          <p className="mt-0.5 text-[13px] text-slate">If you're an artist or performer, opt in to fill-in gigs: when an event nearby loses its performer, CityPulse agents can invite you. Your exact home is never shared.</p>
          <div className="mt-4 grid gap-4 sm:grid-cols-[1fr_auto] sm:items-end">
            <Field label="What do you do?" htmlFor="prof">
              <Input id="prof" defaultValue={profile.profession ?? ""} placeholder="e.g. Hindustani classical vocalist, painter, comedian" onBlur={(e) => e.target.value !== (profile.profession ?? "") && update.mutate({ profession: e.target.value })} />
            </Field>
          </div>
          <label className="mt-4 flex items-start justify-between gap-6">
            <span className="text-[13.5px]">Open to fill-in performances for nearby events <span className="block text-[12.5px] text-slate">Invitations arrive in your notifications; you choose whether to accept.</span></span>
            <Switch checked={!!profile.open_to_gigs} onCheckedChange={(v) => update.mutate({ open_to_gigs: v })} />
          </label>
        </Card>

        <Card className="px-6 py-2">
          <Toggle
            title="Public profile"
            body="Lets your profile appear in Around You → neighbours contributing nearby. Your home, email and exact address are never shown."
            checked={profile.public_visibility === "public"}
            onChange={(v) => update.mutate({ public_visibility: v ? "public" : "private" })}
          />
          <Toggle
            title="Show my name on contributions"
            body="When on (and your profile is public), your name appears on reports and events. You can still post any report anonymously."
            checked={profile.display_name_opt_in}
            onChange={(v) => update.mutate({ display_name_opt_in: v })}
          />
          <Toggle
            title="Area updates"
            body="Count me among residents who want in-app updates when an official alert covers my neighbourhood."
            checked={profile.area_updates_opt_in}
            onChange={(v) => update.mutate({ area_updates_opt_in: v })}
          />
        </Card>

        <Card className="flex flex-wrap items-center justify-between gap-4 p-6">
          <div>
            <p className="text-[14.5px] font-medium">Your data</p>
            <p className="text-[13px] text-slate">Download everything CityPulse stores about your profile and activity.</p>
          </div>
          <Button variant="outline" asChild><a href="/api/v1/profiles/me/export" download="citypulse-my-data.json"><Download /> Export</a></Button>
        </Card>

        <Card className="border-critical/30 p-6">
          <p className="text-[14.5px] font-medium text-critical">Delete profile</p>
          <p className="mt-1 text-[13px] leading-relaxed text-slate">Removes your profile, home location and comments from the graph. Reports you filed stay public as civic records but are no longer linked to you. This can't be undone.</p>
          <Button variant="danger" className="mt-4" loading={del.isPending} onClick={() => confirm("Delete your CityPulse profile permanently?") && del.mutate()}>
            <Trash2 /> Delete my profile
          </Button>
        </Card>
      </div>
    </div>
  );
}
