"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { ErrorState } from "@/components/ui/states";
import { CmdHeader, Panel, Stat } from "@/features/command/ui";
import { api } from "@/lib/api";
import { timeAgo } from "@/lib/format";

export default function Overview() {
  const o = useQuery({ queryKey: ["cmd-overview"], queryFn: () => api.get<any>("/command/overview"), refetchInterval: 30_000 });
  const audit = useQuery({ queryKey: ["cmd-audit"], queryFn: () => api.get<{ items: any[] }>("/command/audit") });
  if (o.error) return <ErrorState error={o.error} onRetry={() => o.refetch()} />;
  const d = o.data;
  return (
    <div>
      <CmdHeader title="Overview" description="Live counts from the city graph. Zero means zero — nothing here is estimated." />
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-6">
        <Stat label="Open community reports" value={d?.open_reports} />
        <Stat label="Awaiting review" value={d?.awaiting_review} tone="amber" />
        <Stat label="Active official alerts" value={d?.active_warnings} tone="critical" />
        <Stat label="Upcoming events" value={d?.upcoming_events} />
        <Stat label="Open coordination cases" value={d?.open_cases} tone="teal" />
        <Stat label="Agent proposals to review" value={d?.pending_recommendations} tone="amber" />
      </div>
      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Panel title="Graph composition">
          <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-[13px] sm:grid-cols-3">
            {Object.entries(d?.graph?.nodes ?? {}).sort((a: any, b: any) => b[1] - a[1]).map(([k, v]: any) => (
              <div key={k} className="flex justify-between border-b border-line py-1"><span className="text-slate">{k}</span><span className="tabular-nums">{v.toLocaleString("en-IN")}</span></div>
            ))}
          </div>
          <p className="mt-4 text-[12px] text-slate">{Object.values(d?.graph?.relationships ?? {}).reduce((a: number, b: any) => a + b, 0).toLocaleString("en-IN")} relationships across {Object.keys(d?.graph?.relationships ?? {}).length} types.</p>
        </Panel>
        <Panel title="Recent sensitive actions" action={<Link href="/command/agents" className="text-[12.5px] text-teal-600">Agent activity</Link>}>
          {audit.data?.items.length ? (
            <ul className="space-y-2 text-[13px]">
              {audit.data.items.slice(0, 12).map((a, i) => (
                <li key={i} className="flex justify-between gap-3"><span><b className="font-medium">{a.actor_id}</b> {a.action.replace(/_/g, " ")} {a.target_id && <span className="font-mono text-[11.5px] text-slate">{a.target_id}</span>}</span><span className="shrink-0 text-slate">{timeAgo(Date.parse(a.created_at))}</span></li>
              ))}
            </ul>
          ) : (
            <p className="text-[13px] text-slate">No audited actions yet.</p>
          )}
        </Panel>
      </div>
    </div>
  );
}
