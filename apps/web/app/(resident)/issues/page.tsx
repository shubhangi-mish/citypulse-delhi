"use client";

import { useQuery } from "@tanstack/react-query";
import { Megaphone, Plus } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/primitives";
import { EmptyState, ErrorState, ListSkeleton, PageHeader } from "@/components/ui/states";
import { IssueFeedCard } from "@/features/feed/feed-card";
import { api } from "@/lib/api";
import { ISSUE_CATEGORIES, ISSUE_STATUSES } from "@/lib/format";
import type { IssueCard } from "@/lib/types";

export default function IssuesPage() {
  const [category, setCategory] = useState("");
  const [status, setStatus] = useState("");
  const q = useQuery({
    queryKey: ["issues", category, status],
    queryFn: () => api.get<{ items: IssueCard[] }>("/issues", { category, status, limit: 100 }),
  });
  return (
    <div className="container-page max-w-4xl py-10">
      <PageHeader
        eyebrow="Community reports"
        title="Reports across Delhi"
        description="Every report here was submitted by a CityPulse resident. Corroboration counts come from real neighbours confirming they're affected."
        action={
          <Button asChild variant="accent">
            <Link href="/report">
              <Plus /> Report
            </Link>
          </Button>
        }
      />
      <div className="mb-6 grid grid-cols-2 gap-3 md:w-[480px]">
        <Select value={category} onChange={(e) => setCategory(e.target.value)} aria-label="Category">
          <option value="">All categories</option>
          {Object.entries(ISSUE_CATEGORIES).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </Select>
        <Select value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Status">
          <option value="">Any status</option>
          {Object.entries(ISSUE_STATUSES).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </Select>
      </div>
      {q.isLoading ? (
        <ListSkeleton />
      ) : q.error ? (
        <ErrorState error={q.error} onRetry={() => q.refetch()} />
      ) : q.data?.items.length ? (
        <div className="space-y-3">
          {q.data.items.map((i) => (
            <IssueFeedCard key={i.issue_id} item={i} />
          ))}
        </div>
      ) : (
        <EmptyState icon={<Megaphone />} title="No reports match" body={category || status ? "Try clearing the filters." : "No one has reported anything yet. Seen something that needs fixing?"} action={<Button asChild variant="accent"><Link href="/report">Report an issue</Link></Button>} />
      )}
    </div>
  );
}
