"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Bell, BellOff, CalendarDays, ExternalLink, HandHeart, MapPin, MessageSquare, Users } from "lucide-react";
import Link from "next/link";
import { CategoryIcon, ProvenanceBadge, SeverityBadge, StatusBadge } from "@/components/badges";
import { toast } from "@/components/toaster";
import { Button } from "@/components/ui/button";
import { Badge, Card } from "@/components/ui/primitives";
import { useIssueActions, useRequireProfile } from "@/features/issues/use-issue-actions";
import { api } from "@/lib/api";
import { EVENT_CATEGORIES, ISSUE_CATEGORIES, formatDate, formatDateTime, label, pluralize, timeAgo } from "@/lib/format";
import type { CaseCard, EventCard, FeedItem, IssueCard, WarningCard } from "@/lib/types";

export function FeedCard({ item }: { item: FeedItem }) {
  if (item.kind === "issue") return <IssueFeedCard item={item} />;
  if (item.kind === "event") return <EventFeedCard item={item} />;
  if (item.kind === "warning") return <WarningFeedCard item={item} />;
  return <CaseFeedCard item={item} />;
}

export function IssueFeedCard({ item, compact }: { item: IssueCard; compact?: boolean }) {
  const { support, follow } = useIssueActions(item.issue_id);
  const require = useRequireProfile();
  const v = item.viewer;
  return (
    <Card className="group p-5 transition-shadow hover:shadow-[var(--shadow-lift)]">
      <div className="flex items-start gap-3.5">
        <div className="grid size-10 shrink-0 place-items-center rounded-xl bg-teal-50 text-teal">
          <CategoryIcon category={item.category} className="size-[18px]" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-[12.5px] text-slate">
            <span className="font-medium text-ink">{v?.mine ? "You" : item.reported_by ?? "A resident"}</span> reported · {label(ISSUE_CATEGORIES, item.category)}
            {item.neighborhood && <> · {item.neighborhood}</>} · {timeAgo(item.created_at)}
          </p>
          <Link href={`/issues/${item.issue_id}`} className="mt-1 block text-[16px] font-semibold leading-snug tracking-tight hover:text-teal-600">
            {item.title}
          </Link>
          {!compact && <p className="mt-1 line-clamp-2 text-[14px] leading-relaxed text-slate">{item.description}</p>}
          <div className="mt-3 flex flex-wrap items-center gap-1.5">
            <StatusBadge status={item.status} />
            <ProvenanceBadge status={item.verification_status} />
            {item.in_coordination && (
              <Badge tone="teal">
                <Users /> Coordination active
              </Badge>
            )}
            {item.distance && (
              <Badge tone="outline">
                <MapPin /> {item.distance}
              </Badge>
            )}
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-line pt-3.5">
            <span className="mr-auto flex items-center gap-3.5 text-[13px] text-slate">
              <span className="flex items-center gap-1">
                <HandHeart className="size-4" /> {pluralize(item.support_count ?? 0, "affected", "affected")}
              </span>
              <span className="flex items-center gap-1">
                <MessageSquare className="size-4" /> {item.comment_count ?? 0}
              </span>
            </span>
            {!v?.mine && (
              <Button
                size="sm"
                variant={v?.supported ? "subtle" : "outline"}
                loading={support.isPending}
                aria-pressed={v?.supported}
                onClick={() => require(`/issues/${item.issue_id}`) && support.mutate(!v?.supported)}
              >
                <HandHeart /> {v?.supported ? "You're affected" : "I'm affected too"}
              </Button>
            )}
            {!v?.mine && (
              <Button
                size="sm"
                variant="ghost"
                loading={follow.isPending}
                aria-pressed={v?.following}
                onClick={() => require() && follow.mutate(!v?.following)}
              >
                {v?.following ? <BellOff /> : <Bell />} {v?.following ? "Following" : "Follow"}
              </Button>
            )}
            <Button size="sm" variant="ghost" asChild>
              <Link href={`/issues/${item.issue_id}`}>View</Link>
            </Button>
          </div>
        </div>
      </div>
    </Card>
  );
}

export function EventFeedCard({ item }: { item: EventCard }) {
  const d = new Date(item.start_time);
  return (
    <Card className="p-5 transition-shadow hover:shadow-[var(--shadow-lift)]">
      <div className="flex items-start gap-4">
        <div className="w-12 shrink-0 overflow-hidden rounded-xl border border-violet/20 text-center">
          <div className="bg-violet py-0.5 text-[10.5px] font-semibold uppercase tracking-wider text-white">
            {d.toLocaleString("en-IN", { month: "short", timeZone: "Asia/Kolkata" })}
          </div>
          <div className="bg-violet-50 py-1 text-[19px] font-semibold text-violet">{d.toLocaleString("en-IN", { day: "numeric", timeZone: "Asia/Kolkata" })}</div>
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-[12.5px] text-slate">
            {label(EVENT_CATEGORIES, item.category)} · {formatDateTime(item.start_time)}
          </p>
          <Link href={`/events/${item.event_id}`} className="mt-1 block text-[16px] font-semibold leading-snug tracking-tight hover:text-violet">
            {item.title}
          </Link>
          <p className="mt-1 text-[13.5px] text-slate">
            {item.venue}
            {item.neighborhood && ` · ${item.neighborhood}`}
          </p>
          <div className="mt-3 flex flex-wrap items-center gap-1.5">
            <ProvenanceBadge status={item.verification_status} />
            {item.source_type === "user_submitted" && <Badge tone="outline">{item.organizer_attestation ? "Resident-submitted" : "Shared from a listing"}</Badge>}
            {item.is_free === true ? <Badge tone="neutral">Free</Badge> : item.is_free === false ? <Badge tone="neutral">Paid</Badge> : null}
            {item.performer_gap && <Badge tone="amber">Performer cancelled · finding a replacement</Badge>}
            {item.warning_count > 0 && <Badge tone="amber">{pluralize(item.warning_count, "official alert")}</Badge>}
            {item.distance && (
              <Badge tone="outline">
                <MapPin /> {item.distance}
              </Badge>
            )}
          </div>
          <div className="mt-4 flex items-center gap-2 border-t border-line pt-3.5">
            <span className="mr-auto flex items-center gap-1 text-[13px] text-slate">
              <Users className="size-4" /> {pluralize(item.participant_count, "participant")}
              {item.viewer?.participating && <span className="ml-2 text-teal-600">· You're in</span>}
            </span>
            <Button size="sm" variant="ghost" asChild>
              <Link href={`/events/${item.event_id}`}>
                <CalendarDays /> View event
              </Link>
            </Button>
          </div>
        </div>
      </div>
    </Card>
  );
}

export function WarningFeedCard({ item }: { item: WarningCard }) {
  return (
    <Card className="relative overflow-hidden p-5 pl-6">
      <span className="absolute inset-y-0 left-0 w-1 bg-amber" aria-hidden="true" />
      <div className="flex flex-wrap items-center gap-1.5">
        <ProvenanceBadge status={item.verification_status} />
        <SeverityBadge severity={item.severity} />
        {item.warning_type && <Badge tone="neutral">{item.warning_type}</Badge>}
      </div>
      <Link href={`/warnings/${item.warning_id}`} className="mt-2 block text-[16px] font-semibold leading-snug tracking-tight hover:text-[#8a5c17]">
        {item.title}
      </Link>
      <p className="mt-1 text-[13px] text-slate">
        Issued by {item.issuing_authority} · until {formatDateTime(item.expires_at)}
      </p>
      {!!item.affected_neighborhoods?.length && (
        <p className="mt-2 text-[13px] text-slate">
          Covers {item.affected_neighborhoods.slice(0, 4).join(", ")}
          {(item.affected_count ?? 0) > 4 && ` and ${(item.affected_count ?? 0) - 4} more mapped places`}
        </p>
      )}
      <div className="mt-4 flex items-center gap-2 border-t border-line pt-3.5">
        <a href={item.source_url} target="_blank" rel="noreferrer" className="mr-auto flex items-center gap-1 text-[13px] font-medium text-teal-600 hover:underline">
          Official source <ExternalLink className="size-3.5" />
        </a>
        <Button size="sm" variant="ghost" asChild>
          <Link href={`/warnings/${item.warning_id}`}>Impact</Link>
        </Button>
      </div>
    </Card>
  );
}

export function CaseFeedCard({ item }: { item: CaseCard }) {
  const qc = useQueryClient();
  const require = useRequireProfile();
  const join = useMutation({
    mutationFn: () => api.post(`/coordination/cases/${item.case_id}/join`),
    onSuccess: () => {
      toast.success("You've joined this coordination effort.");
      qc.invalidateQueries({ queryKey: ["nearby"] });
    },
  });
  return (
    <Card className="border-teal/25 bg-gradient-to-br from-white to-teal-50/40 p-5">
      <div className="flex items-center gap-2 text-[12.5px] font-medium text-teal-600">
        <Users className="size-4" /> Community coordination · updated {timeAgo(item.updated_at)}
      </div>
      <h3 className="mt-1.5 text-[16px] font-semibold tracking-tight">{item.title}</h3>
      <ul className="mt-2 space-y-1">
        {item.issues.slice(0, 3).map((i) => (
          <li key={i.issue_id}>
            <Link href={`/issues/${i.issue_id}`} className="text-[13.5px] text-slate hover:text-ink hover:underline">
              ↳ {i.title}
            </Link>
          </li>
        ))}
      </ul>
      <div className="mt-4 flex items-center gap-2 border-t border-teal/15 pt-3.5">
        <span className="mr-auto text-[13px] text-slate">{pluralize(item.participant_count ?? 0, "resident")} helping · since {formatDate(item.created_at)}</span>
        <Button size="sm" variant="subtle" loading={join.isPending} onClick={() => require() && join.mutate()}>
          Join coordination
        </Button>
      </div>
    </Card>
  );
}
