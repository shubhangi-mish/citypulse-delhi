"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowRight, EyeOff, Info, MapPin } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { CategoryIcon } from "@/components/badges";
import { LocationPicker, type PickedLocation } from "@/components/map/location-picker";
import { toast } from "@/components/toaster";
import { Button } from "@/components/ui/button";
import { Card, Field, Input, Segmented, Switch, Textarea } from "@/components/ui/primitives";
import { EmptyState, PageHeader } from "@/components/ui/states";
import { useProfile } from "@/hooks/use-profile";
import { api, ApiError } from "@/lib/api";
import { ASSET_TYPES, ISSUE_CATEGORIES, cn, label } from "@/lib/format";

function Step({ n, title, children }: { n: number; title: string; children: React.ReactNode }) {
  return (
    <section className="relative border-l border-line pb-10 pl-8 last:pb-0">
      <span className="absolute -left-3.5 top-0 grid size-7 place-items-center rounded-full border border-line-strong bg-white text-[12.5px] font-semibold">{n}</span>
      <h2 className="mb-4 pt-0.5 text-[16px] font-semibold tracking-tight">{title}</h2>
      {children}
    </section>
  );
}

export default function ReportPage() {
  const router = useRouter();
  const { profile, isLoading } = useProfile();
  const [category, setCategory] = useState<string | null>(null);
  const [loc, setLoc] = useState<PickedLocation | null>(null);
  const [assetId, setAssetId] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [precision, setPrecision] = useState<"approximate" | "neighborhood">("approximate");
  const [anonymous, setAnonymous] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});

  const assets = useQuery({
    queryKey: ["assets-near", loc?.latitude.toFixed(4), loc?.longitude.toFixed(4)],
    queryFn: () => api.get<{ items: { asset_id: string; name: string; asset_type: string; distance_m: number }[] }>("/issues/assets-near", { lat: loc!.latitude, lng: loc!.longitude }),
    enabled: !!loc,
  });

  const submit = useMutation({
    mutationFn: () =>
      api.post<{ issue_id: string; message: string }>("/issues", {
        category,
        title,
        description,
        latitude: loc!.latitude,
        longitude: loc!.longitude,
        precision,
        anonymous,
        concerns_asset_id: assetId,
        event_id: typeof window !== "undefined" ? new URLSearchParams(window.location.search).get("event") : null,
      }),
    onSuccess: (r) => {
      toast.success("Submitted to the CityPulse community.");
      router.push(`/issues/${r.issue_id}?new=1`);
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Could not submit."),
  });

  if (!isLoading && !profile) {
    return (
      <div className="container-page max-w-2xl py-16">
        <EmptyState
          icon={<MapPin />}
          title="Create a quick profile to report"
          body="Reports are connected to your neighbourhood so others nearby can find and confirm them. Your address and email are never shown."
          action={
            <Button asChild>
              <Link href="/onboarding?next=/report">Continue as a resident</Link>
            </Button>
          }
        />
      </div>
    );
  }

  const validate = () => {
    const e: Record<string, string> = {};
    if (!category) e.category = "Pick a category.";
    if (!loc) e.loc = "Choose where it is.";
    if (title.trim().length < 5) e.title = "At least 5 characters.";
    if (description.trim().length < 10) e.description = "Add a little more detail (10+ characters).";
    setErrors(e);
    return !Object.keys(e).length;
  };

  return (
    <div className="container-page max-w-3xl py-10">
      <PageHeader eyebrow="Report" title="Report an issue" description="Share what you've seen. Neighbours can confirm it, and the city graph connects it to nearby reports, places and official alerts." />

      <div className="mb-8 flex gap-3 rounded-xl border border-line bg-white p-4 text-[13.5px] leading-relaxed text-slate">
        <Info className="mt-0.5 size-4 shrink-0 text-teal" />
        <p>
          Your report is <b className="font-medium text-ink">submitted to the CityPulse community</b>. It is not filed with MCD, DJB, PWD, Delhi Police or any government department, and CityPulse does not issue official complaint numbers.
        </p>
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (validate()) submit.mutate();
        }}
      >
        <Step n={1} title="What kind of issue?">
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-5">
            {Object.entries(ISSUE_CATEGORIES).map(([k, v]) => (
              <button
                type="button"
                key={k}
                onClick={() => setCategory(k)}
                aria-pressed={category === k}
                className={cn(
                  "flex flex-col items-start gap-2 rounded-xl border bg-white p-3 text-left text-[13px] font-medium transition-colors",
                  category === k ? "border-teal bg-teal-50 text-teal-600 ring-2 ring-teal/15" : "border-line hover:border-line-strong",
                )}
              >
                <CategoryIcon category={k} className="size-5" />
                {v}
              </button>
            ))}
          </div>
          {errors.category && <p className="mt-2 text-[12.5px] text-critical">{errors.category}</p>}
        </Step>

        <Step n={2} title="Where is it?">
          <LocationPicker
            value={loc}
            onChange={(v) => {
              setLoc(v);
              setAssetId(null);
            }}
            addressLabel="Location"
            placeholder="Search a street, landmark or locality"
          />
          {errors.loc && <p className="mt-2 text-[12.5px] text-critical">{errors.loc}</p>}
          {loc && !!assets.data?.items.length && (
            <div className="mt-4">
              <p className="mb-2 text-[13px] font-medium">Is it about one of these mapped places? (optional)</p>
              <div className="flex flex-wrap gap-1.5">
                {assets.data.items.slice(0, 8).map((a) => (
                  <button
                    type="button"
                    key={a.asset_id}
                    onClick={() => setAssetId(assetId === a.asset_id ? null : a.asset_id)}
                    className={cn("rounded-full border px-3 py-1 text-[12.5px]", assetId === a.asset_id ? "border-teal bg-teal-50 text-teal-600" : "border-line-strong bg-white")}
                  >
                    {a.name} <span className="text-slate">· {label(ASSET_TYPES, a.asset_type)} · {a.distance_m} m</span>
                  </button>
                ))}
              </div>
              <p className="mt-1.5 text-[11.5px] text-slate">From OpenStreetMap. Selecting one links your report to it in the city graph.</p>
            </div>
          )}
        </Step>

        <Step n={3} title="Describe it">
          <div className="space-y-4">
            <Field label="Title" htmlFor="title" error={errors.title} hint={`${title.length}/120`}>
              <Input id="title" maxLength={120} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Knee-deep waterlogging at the market crossing" />
            </Field>
            <Field label="What's happening?" htmlFor="desc" error={errors.description} hint="Since when, how severe, who's affected. Avoid personal details about others.">
              <Textarea id="desc" maxLength={4000} value={description} onChange={(e) => setDescription(e.target.value)} />
            </Field>
          </div>
        </Step>

        <Step n={4} title="Visibility">
          <div className="space-y-5">
            <div>
              <p className="mb-2 text-[13.5px] font-medium">Public location precision</p>
              <Segmented
                value={precision}
                onChange={setPrecision}
                options={[
                  { value: "approximate", label: "Approximate (~100 m)" },
                  { value: "neighborhood", label: "Neighbourhood only" },
                ]}
              />
              <p className="mt-1.5 text-[12px] text-slate">The exact point is used only for nearby matching inside the graph; the public map shows the generalised location.</p>
            </div>
            <label className="flex items-start justify-between gap-6 rounded-xl border border-line bg-white p-4">
              <span>
                <span className="flex items-center gap-2 text-[14px] font-medium">
                  <EyeOff className="size-4 text-slate" /> Post anonymously
                </span>
                <span className="mt-0.5 block text-[12.5px] text-slate">
                  {profile?.display_name_opt_in && profile.public_visibility === "public"
                    ? "Your profile normally shows your name on contributions. Turn this on to hide it for this report."
                    : "Your profile is private, so your name won't be shown either way."}
                </span>
              </span>
              <Switch checked={anonymous} onCheckedChange={setAnonymous} />
            </label>
          </div>
        </Step>

        <div className="mt-10 flex items-center justify-end gap-3 border-t border-line pt-6">
          <Button type="button" variant="ghost" onClick={() => router.back()}>
            Cancel
          </Button>
          <Button type="submit" size="lg" variant="accent" loading={submit.isPending}>
            Submit to CityPulse community <ArrowRight />
          </Button>
        </div>
      </form>
    </div>
  );
}
