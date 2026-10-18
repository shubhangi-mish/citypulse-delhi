"use client";

import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { PageHeader } from "@/components/ui/states";
import { GraphExplorer } from "@/features/graph/graph-explorer";

function Connections() {
  const focus = useSearchParams().get("focus");
  return (
    <div className="container-page py-10">
      <PageHeader
        eyebrow="City connections"
        title="How Delhi connects"
        description="Every report, event and alert in CityPulse lives in a FalkorDB graph alongside OpenStreetMap neighbourhoods, districts, roads and infrastructure. Explore any part of it — one neighbourhood at a time, never the whole city at once."
      />
      <GraphExplorer initialFocus={focus} />
    </div>
  );
}

export default function Page() {
  return (
    <Suspense>
      <Connections />
    </Suspense>
  );
}
