"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Lock, ShieldCheck } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { LocationPicker, type PickedLocation } from "@/components/map/location-picker";
import { toast } from "@/components/toaster";
import { Button } from "@/components/ui/button";
import { Card, Field, Input } from "@/components/ui/primitives";
import { useProfile } from "@/hooks/use-profile";
import { api, ApiError } from "@/lib/api";

const schema = z.object({
  name: z.string().trim().min(1, "Tell us what to call you").max(80),
  email: z.string().trim().email("Enter a valid email"),
});

function Onboarding() {
  const router = useRouter();
  const next = useSearchParams().get("next") || "/";
  const qc = useQueryClient();
  const { profile } = useProfile();
  const [loc, setLoc] = useState<PickedLocation | null>(null);
  const [locError, setLocError] = useState<string | null>(null);
  const form = useForm<z.infer<typeof schema>>({ resolver: zodResolver(schema) });

  const create = useMutation({
    mutationFn: (v: z.infer<typeof schema>) =>
      api.post("/profiles", { ...v, address: loc!.address || "Pinned location", latitude: loc!.latitude, longitude: loc!.longitude, neighborhood_id: loc!.neighborhood_id }),
    onSuccess: async () => {
      await qc.invalidateQueries();
      toast.success("Welcome to CityPulse. Your neighbourhood is ready.");
      router.push(next);
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Could not create your profile."),
  });

  return (
    <div className="container-page grid gap-10 py-10 md:py-16 lg:grid-cols-[1fr_1.1fr]">
      <div className="lg:sticky lg:top-28 lg:self-start">
        <div className="eyebrow mb-3">Quick profile</div>
        <h1 className="font-display text-[44px] leading-[1.04] tracking-tight md:text-[56px]">
          Your neighbourhood,
          <br />
          <span className="italic text-teal">connected.</span>
        </h1>
        <p className="mt-5 max-w-md text-[15.5px] leading-relaxed text-slate">
          Tell us roughly where you live so CityPulse can show reports, events and official alerts around you, and connect you with neighbours working on the same things.
        </p>
        <ul className="mt-8 space-y-4 text-[14px]">
          <li className="flex gap-3">
            <Lock className="mt-0.5 size-4 shrink-0 text-teal" />
            <span>
              <b className="font-medium">Your address and email stay private.</b> Other residents never see them, and your home is never shown on any map.
            </span>
          </li>
          <li className="flex gap-3">
            <ShieldCheck className="mt-0.5 size-4 shrink-0 text-teal" />
            <span>
              <b className="font-medium">Private by default.</b> Your name appears on contributions only if you opt in later.
            </span>
          </li>
        </ul>
        <p className="mt-8 rounded-xl border border-amber/30 bg-amber-50 p-4 text-[13px] leading-relaxed text-[#6f4b13]">
          This is a passwordless quick profile tied to this browser — not verified identity. Your email is never used to sign in or recover a profile, so nobody can open your profile by typing your email.
        </p>
      </div>

      <Card className="p-6 md:p-8">
        {profile && (
          <div className="mb-6 rounded-xl bg-teal-50 p-4 text-[13.5px] text-teal-600">
            You already have a quick profile in this browser ({profile.name}). Creating another starts a separate profile.
          </div>
        )}
        <form
          className="space-y-5"
          onSubmit={form.handleSubmit((v) => {
            if (!loc) {
              setLocError("Choose your address or drop a pin.");
              return;
            }
            create.mutate(v);
          })}
        >
          <Field label="Name" htmlFor="name" error={form.formState.errors.name?.message}>
            <Input id="name" autoComplete="name" placeholder="How neighbours will see you, if you choose" {...form.register("name")} />
          </Field>
          <Field label="Email" htmlFor="email" error={form.formState.errors.email?.message} hint="Kept private. Used only for your own records.">
            <Input id="email" type="email" autoComplete="email" placeholder="you@example.com" {...form.register("email")} />
          </Field>
          <div>
            <LocationPicker
              value={loc}
              onChange={(v) => {
                setLoc(v);
                setLocError(null);
              }}
              addressLabel="Address or neighbourhood"
              privacyNote="Only this neighbourhood is ever shown publicly — never your pin."
            />
            {locError && <p className="mt-2 text-[12.5px] text-critical">{locError}</p>}
          </div>
          <Button type="submit" size="lg" className="w-full" loading={create.isPending}>
            Continue as a resident <ArrowRight />
          </Button>
        </form>
      </Card>
    </div>
  );
}

export default function Page() {
  return (
    <Suspense>
      <Onboarding />
    </Suspense>
  );
}
