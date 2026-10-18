"use client";

import { useQuery } from "@tanstack/react-query";
import { Activity } from "lucide-react";
import Link from "next/link";
import { StatusBadge } from "@/components/badges";
import { Button } from "@/components/ui/button";
import { Badge, Card, SectionHeader } from "@/components/ui/primitives";
import { EmptyState, ErrorState, ListSkeleton, PageHeader } from "@/components/ui/states";
import { useNotifications, useProfile } from "@/hooks/use-profile";
import { api } from "@/lib/api";
import { ISSUE_CATEGORIES, formatDateTime, label, timeAgo } from "@/lib/format";

interface ActivityData {
  reported: { issue_id: string; title: string; status: string; category: string; support_count: number; created_at: number }[];
  following: { issue_id: string; title: string; status: string; category: string; support_count: number; relation: string[]; created_at: number }[];
  events: { event_id: string; title: string; start_time: number; status: string; relation: string[] }[];
  cases: { case_id: string; title: string; status: string }[];
}

function Row({ href, title, meta, right }: { href: string; title: string; meta: React.ReactNode; right?: React.ReactNode }) {
  return (
    <Link href={href} className="flex items-center justify-between gap-4 border-b border-line px-5 py-3.5 last:border-0 hover:bg-paper-2/60">
      <div className="min-w-0">
        <p className="truncate text-[14.5px] font-medium">{title}</p>
        <p className="text-[12.5px] text-slate">{meta}</p>
      </div>
      {right}
    </Link>
  );
}

export default function MyActivity() {
  const { profile, isLoading } = useProfile();
  const q = useQuery({ queryKey: ["activity"], queryFn: () => api.get<ActivityData>("/profiles/me/activity"), enabled: !!profile });
  const notes = useNotifications(!!profile);

  if (!isLoading && !profile)
    return (
      <div className="container-page max-w-2xl py-16">
        <EmptyState icon={<Activity />} title="Your activity lives here" body="Create a quick profile to track reports you've filed, issues you follow and events you've joined." action={<Button asChild><Link href="/onboarding?next=/my-activity">Continue as a resident</Link></Button>} />
      </div>
    );

  return (
    <div className="container-page max-w-4xl py-10">
      <PageHeader eyebrow="My activity" title="Your contributions" description="Everything you've reported, followed and joined — all stored as relationships in the city graph." />
      {q.isLoading ? (
        <ListSkeleton />
      ) : q.error ? (
        <ErrorState error={q.error} onRetry={() => q.refetch()} />
      ) : q.data ? (
        <div className="space-y-10">
          <section>
            <SectionHeader title={`Reported by you (${q.data.reported.length})`} />
            {q.data.reported.length ? (
              <Card>{q.data.reported.map((i) => <Row key={i.issue_id} href={`/issues/${i.issue_id}`} title={i.title} meta={<>{label(ISSUE_CATEGORIES, i.category)} · {timeAgo(i.created_at)} · {i.support_count} affected</>} right={<StatusBadge status={i.status} />} />)}</Card>
            ) : (
              <EmptyState title="You haven't reported anything yet" action={<Button asChild variant="accent"><Link href="/report">Report an issue</Link></Button>} />
            )}
          </section>
          <section>
            <SectionHeader title={`Following & affected (${q.data.following.length})`} />
            {q.data.following.length ? (
              <Card>{q.data.following.map((i) => <Row key={i.issue_id} href={`/issues/${i.issue_id}`} title={i.title} meta={i.relation.map((r) => (r === "SUPPORTS" ? "You're affected" : "Following")).join(" · ")} right={<StatusBadge status={i.status} />} />)}</Card>
            ) : (
              <p className="text-[13.5px] text-slate">Follow reports from Around You to track them here.</p>
            )}
          </section>
          <section>
            <SectionHeader title={`Events (${q.data.events.length})`} />
            {q.data.events.length ? (
              <Card>{q.data.events.map((e) => <Row key={e.event_id} href={`/events/${e.event_id}`} title={e.title} meta={formatDateTime(e.start_time)} right={<Badge tone="violet">{e.relation.includes("SUBMITTED") ? "Organiser" : "Participating"}</Badge>} />)}</Card>
            ) : (
              <p className="text-[13.5px] text-slate">No events yet.</p>
            )}
          </section>
          {q.data.cases.length > 0 && (
            <section>
              <SectionHeader title="Coordination you've joined" />
              <Card>{q.data.cases.map((c) => <div key={c.case_id} className="flex justify-between border-b border-line px-5 py-3.5 last:border-0"><span className="text-[14.5px] font-medium">{c.title}</span><Badge tone="teal">{c.status}</Badge></div>)}</Card>
            </section>
          )}
          <section>
            <SectionHeader title="Notifications" />
            {notes.data?.items.length ? (
              <Card>{notes.data.items.map((n) => <div key={n.id} className="border-b border-line px-5 py-3 last:border-0"><p className="text-[14px]">{n.message}</p><p className="text-[12px] text-slate">{timeAgo(Date.parse(n.created_at))}</p></div>)}</Card>
            ) : (
              <p className="text-[13.5px] text-slate">No notifications yet.</p>
            )}
          </section>
        </div>
      ) : null}
    </div>
  );
}
