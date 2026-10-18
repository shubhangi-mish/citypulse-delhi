"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Check, ClipboardCheck, X } from "lucide-react";
import { useState } from "react";
import { toast } from "@/components/toaster";
import { Button } from "@/components/ui/button";
import { Badge, Input } from "@/components/ui/primitives";
import { api, ApiError } from "@/lib/api";
import { ACTION_TYPES, label, timeAgo } from "@/lib/format";

export interface ActionRow {
  action_id: string;
  action_type: string;
  status: string;
  description: string;
  proposed_by: string;
  approved_by: string | null;
  outcome: string | null;
  created_at: number;
  decision_id?: string | null;
  payload?: Record<string, any> | null;
}

const TONE: Record<string, any> = { proposed: "amber", approved: "teal", executed: "teal", completed: "positive", rejected: "outline" };

export function ActionCard({ a, invalidate }: { a: ActionRow; invalidate: string[][] }) {
  const qc = useQueryClient();
  const [outcome, setOutcome] = useState("");
  const refresh = () => invalidate.forEach((k) => qc.invalidateQueries({ queryKey: k }));
  const onError = (e: unknown) => toast.error(e instanceof ApiError ? e.message : "Failed.");
  const approve = useMutation({ mutationFn: () => api.post<{ execution: string }>(`/coordination/actions/${a.action_id}/approve`), onSuccess: (r) => { toast.success(`Approved — ${r.execution}`); refresh(); }, onError });
  const reject = useMutation({ mutationFn: (reason: string) => api.post(`/coordination/actions/${a.action_id}/reject`, { reason }), onSuccess: () => { toast.info("Rejected."); refresh(); }, onError });
  const record = useMutation({
    mutationFn: (success: boolean) => api.post<{ memory_id: string }>(`/coordination/actions/${a.action_id}/outcome`, { outcome, success }),
    onSuccess: (r) => { toast.success(`Outcome stored. Memory Agent wrote ${r.memory_id}.`); refresh(); },
    onError,
  });
  return (
    <div className="rounded-xl border border-line bg-white p-4">
      <div className="flex flex-wrap items-center gap-2">
        <p className="mr-auto text-[14px] font-semibold">{label(ACTION_TYPES, a.action_type)}</p>
        <Badge tone={TONE[a.status] ?? "neutral"}>{a.status}</Badge>
      </div>
      <p className="mt-1 text-[13.5px]">{a.description}</p>
      {a.payload?.message && <p className="mt-2 rounded-lg bg-paper-2 p-2.5 text-[13px]">“{a.payload.message}”</p>}
      {a.payload?.rationale && <p className="mt-2 text-[12.5px] text-slate"><b className="font-medium text-ink">Why:</b> {a.payload.rationale}</p>}
      <p className="mt-2 text-[11.5px] text-slate">
        Proposed by {a.proposed_by} · {timeAgo(a.created_at)}
        {a.approved_by && ` · approved by ${a.approved_by}`}
      </p>
      {a.outcome && <p className="mt-2 text-[13px]"><b className="font-medium">Outcome:</b> {a.outcome}</p>}
      {a.status === "proposed" && (
        <div className="mt-3 flex gap-2">
          <Button size="sm" variant="accent" loading={approve.isPending} onClick={() => approve.mutate()}><Check /> Approve & execute</Button>
          <Button size="sm" variant="ghost" loading={reject.isPending} onClick={() => { const r = prompt("Reason for rejecting?"); if (r && r.length >= 3) reject.mutate(r); }}><X /> Reject</Button>
        </div>
      )}
      {a.status === "executed" && (
        <div className="mt-3 flex flex-wrap gap-2">
          <Input value={outcome} onChange={(e) => setOutcome(e.target.value)} placeholder="What actually happened?" className="h-9 min-w-56 flex-1 text-[13.5px]" />
          <Button size="sm" variant="outline" disabled={outcome.length < 3} loading={record.isPending && record.variables === true} onClick={() => record.mutate(true)}><ClipboardCheck /> Worked</Button>
          <Button size="sm" variant="ghost" disabled={outcome.length < 3} loading={record.isPending && record.variables === false} onClick={() => record.mutate(false)}>Didn't work</Button>
        </div>
      )}
    </div>
  );
}
