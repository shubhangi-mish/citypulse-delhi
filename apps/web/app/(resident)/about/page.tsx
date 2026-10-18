"use client";

import { useQuery } from "@tanstack/react-query";
import { ExternalLink } from "lucide-react";
import { ProvenanceBadge } from "@/components/badges";
import { Badge, Card } from "@/components/ui/primitives";
import { ErrorState, ListSkeleton, PageHeader } from "@/components/ui/states";
import { api } from "@/lib/api";
import { timeAgo } from "@/lib/format";

const INGESTION: Record<string, { label: string; tone: any }> = {
  active: { label: "Ingested", tone: "positive" },
  live: { label: "Live", tone: "positive" },
  display_only: { label: "Display only", tone: "teal" },
  not_ingested: { label: "Evaluated · not ingested", tone: "outline" },
};

export default function About() {
  const q = useQuery({ queryKey: ["sources-status"], queryFn: () => api.get<{ items: any[]; graph_available: boolean }>("/sources/status") });
  return (
    <div className="container-page max-w-4xl py-10">
      <PageHeader
        eyebrow="About CityPulse"
        title="Independent, source-backed, privacy-first"
        description="CityPulse Delhi is an independent community coordination platform. It is not a government service, and it doesn't file complaints with MCD, NDMC, DJB, PWD, Delhi Police or any department."
      />
      <div className="grid gap-4 md:grid-cols-3">
        {[
          ["Real data only", "No invented residents, reports, events or alerts. Empty means nothing has happened yet — not that we hid placeholders."],
          ["Every record has a source", "Each item carries its source, licence, timestamps and a verification status, from Official source to AI inference."],
          ["Your home stays private", "Emails and addresses are never shown. Public locations are generalised; names appear only if you opt in."],
        ].map(([t, b]) => (
          <Card key={t} className="p-5">
            <p className="text-[14.5px] font-semibold">{t}</p>
            <p className="mt-1.5 text-[13.5px] leading-relaxed text-slate">{b}</p>
          </Card>
        ))}
      </div>

      <h2 className="mb-4 mt-12 text-[20px] font-semibold tracking-tight">Data sources</h2>
      {q.isLoading ? (
        <ListSkeleton />
      ) : q.error ? (
        <ErrorState error={q.error} />
      ) : (
        <div className="space-y-3">
          {q.data!.items.map((s) => (
            <Card key={s.source_id} className="p-5">
              <div className="flex flex-wrap items-center gap-2">
                <p className="mr-auto text-[15px] font-semibold">{s.name}</p>
                <Badge tone={INGESTION[s.ingestion]?.tone}>{INGESTION[s.ingestion]?.label ?? s.ingestion}</Badge>
                <ProvenanceBadge status={s.verification_status} />
              </div>
              <p className="mt-2 text-[13px] text-slate">{s.data_types?.join(", ")}</p>
              <dl className="mt-3 grid gap-x-6 gap-y-1.5 text-[12.5px] sm:grid-cols-2">
                <div><dt className="inline text-slate">Licence: </dt><dd className="inline">{s.license}</dd></div>
                <div><dt className="inline text-slate">Access: </dt><dd className="inline">{s.access_method}</dd></div>
                <div><dt className="inline text-slate">Refresh: </dt><dd className="inline">{s.refresh}</dd></div>
                <div><dt className="inline text-slate">Last success: </dt><dd className="inline">{s.last_success_at ? timeAgo(Date.parse(s.last_success_at)) : "—"}{s.graph_records != null && ` · ${s.graph_records.toLocaleString("en-IN")} graph records`}</dd></div>
                <div className="sm:col-span-2"><dt className="inline text-slate">Limitations: </dt><dd className="inline">{s.limitations}</dd></div>
              </dl>
              {s.url?.startsWith("http") && <a href={s.url} target="_blank" rel="noreferrer" className="mt-2 inline-flex items-center gap-1 text-[12.5px] font-medium text-teal-600 hover:underline">{s.url} <ExternalLink className="size-3" /></a>}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
