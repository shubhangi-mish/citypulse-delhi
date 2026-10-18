"use client";

import { useMutation } from "@tanstack/react-query";
import { ArrowRight, CalendarPlus } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { LocationPicker, type PickedLocation } from "@/components/map/location-picker";
import { toast } from "@/components/toaster";
import { Button } from "@/components/ui/button";
import { Card, Field, Input, Select, Switch, Textarea } from "@/components/ui/primitives";
import { EmptyState, PageHeader } from "@/components/ui/states";
import { useProfile } from "@/hooks/use-profile";
import { api, ApiError } from "@/lib/api";
import { EVENT_CATEGORIES } from "@/lib/format";

function toMs(date: string, time: string) {
  // Interpret as IST regardless of browser timezone.
  return Date.parse(`${date}T${time}:00+05:30`);
}

export default function CreateEvent() {
  const router = useRouter();
  const { profile, isLoading } = useProfile();
  const [f, setF] = useState({
    title: "",
    description: "",
    category: "community_meeting",
    date: "",
    start: "10:00",
    end: "12:00",
    venue_name: "",
    organizer_name: "",
    organizer_contact: "",
    organization_name: "",
    is_free: true,
    setting: "outdoor",
    accessibility: "",
    registration_url: "",
    attestation: false,
  });
  const [loc, setLoc] = useState<PickedLocation | null>(null);
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setF({ ...f, [k]: e.target.value });

  const submit = useMutation({
    mutationFn: () =>
      api.post<{ event_id: string }>("/events", {
        title: f.title,
        description: f.description,
        category: f.category,
        start_time: toMs(f.date, f.start),
        end_time: toMs(f.date, f.end),
        venue_name: f.venue_name,
        venue_address: loc?.address || f.venue_name,
        latitude: loc?.latitude,
        longitude: loc?.longitude,
        organizer_name: f.organizer_name,
        organizer_contact: f.organizer_contact,
        organization_name: f.organization_name || null,
        is_free: f.is_free,
        setting: f.setting,
        accessibility: f.accessibility || null,
        registration_url: f.registration_url || null,
        attestation: f.attestation,
      }),
    onSuccess: (r) => {
      toast.success("Event published as community-submitted.");
      router.push(`/events/${r.event_id}`);
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Could not publish."),
  });

  if (!isLoading && !profile)
    return (
      <div className="container-page max-w-2xl py-16">
        <EmptyState icon={<CalendarPlus />} title="Create a quick profile to share an event" action={<Button asChild><Link href="/onboarding?next=/events/create">Continue as a resident</Link></Button>} />
      </div>
    );

  const valid = f.title.length >= 5 && f.description.length >= 20 && f.date && f.venue_name && loc && f.organizer_name && f.organizer_contact.length >= 5 && f.attestation && toMs(f.date, f.end) > toMs(f.date, f.start);

  return (
    <div className="container-page max-w-3xl py-10">
      <PageHeader eyebrow="Events" title="Share a genuine event" description="Events you share are labelled “resident-submitted”. They are not presented as officially verified." />
      <form
        className="space-y-6"
        onSubmit={(e) => {
          e.preventDefault();
          if (valid) submit.mutate();
        }}
      >
        <Card className="space-y-4 p-6">
          <Field label="Event title" htmlFor="t">
            <Input id="t" value={f.title} onChange={set("title")} maxLength={140} placeholder="e.g. Saturday morning park cleanup" />
          </Field>
          <Field label="Description" htmlFor="d" hint="What will happen, who it's for, what to bring.">
            <Textarea id="d" value={f.description} onChange={set("description")} maxLength={5000} />
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Category" htmlFor="c">
              <Select id="c" value={f.category} onChange={set("category")}>
                {Object.entries(EVENT_CATEGORIES).map(([k, v]) => (
                  <option key={k} value={k}>
                    {v}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Setting" htmlFor="s">
              <Select id="s" value={f.setting} onChange={set("setting")}>
                <option value="outdoor">Outdoor</option>
                <option value="indoor">Indoor</option>
                <option value="mixed">Mixed</option>
              </Select>
            </Field>
          </div>
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label="Date" htmlFor="date">
              <Input id="date" type="date" value={f.date} onChange={set("date")} min={new Date().toISOString().slice(0, 10)} />
            </Field>
            <Field label="Starts (IST)" htmlFor="st">
              <Input id="st" type="time" value={f.start} onChange={set("start")} />
            </Field>
            <Field label="Ends (IST)" htmlFor="en">
              <Input id="en" type="time" value={f.end} onChange={set("end")} />
            </Field>
          </div>
        </Card>

        <Card className="space-y-4 p-6">
          <Field label="Venue name" htmlFor="v">
            <Input id="v" value={f.venue_name} onChange={set("venue_name")} placeholder="e.g. Community park, Block C" />
          </Field>
          <LocationPicker value={loc} onChange={setLoc} addressLabel="Venue location" placeholder="Search the venue address" />
        </Card>

        <Card className="space-y-4 p-6">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Organiser name" htmlFor="on">
              <Input id="on" value={f.organizer_name} onChange={set("organizer_name")} />
            </Field>
            <Field label="Organiser contact" htmlFor="oc" hint="Visible only to you (the organiser) and CityPulse coordinators.">
              <Input id="oc" value={f.organizer_contact} onChange={set("organizer_contact")} placeholder="Email or phone" />
            </Field>
          </div>
          <Field label="Organisation (optional)" htmlFor="org" hint="e.g. your RWA or community group.">
            <Input id="org" value={f.organization_name} onChange={set("organization_name")} />
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Registration link (optional)" htmlFor="reg">
              <Input id="reg" type="url" value={f.registration_url} onChange={set("registration_url")} placeholder="https://" />
            </Field>
            <Field label="Accessibility (optional)" htmlFor="acc">
              <Input id="acc" value={f.accessibility} onChange={set("accessibility")} placeholder="e.g. step-free access, seating" />
            </Field>
          </div>
          <label className="flex items-center justify-between gap-4">
            <span className="text-[14px] font-medium">Free to attend</span>
            <Switch checked={f.is_free} onCheckedChange={(v) => setF({ ...f, is_free: v })} />
          </label>
        </Card>

        <label className="flex items-start gap-3 rounded-xl border border-amber/40 bg-amber-50 p-4 text-[13.5px] leading-relaxed">
          <input type="checkbox" className="mt-1 size-4 accent-[#157C83]" checked={f.attestation} onChange={(e) => setF({ ...f, attestation: e.target.checked })} />
          <span>I confirm this is a genuine event that I'm organising or am authorised to share, and the details are accurate.</span>
        </label>

        <div className="flex justify-end">
          <Button type="submit" size="lg" variant="accent" disabled={!valid} loading={submit.isPending}>
            Publish event <ArrowRight />
          </Button>
        </div>
      </form>
    </div>
  );
}
