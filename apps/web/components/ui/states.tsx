"use client";

import { AlertTriangle, DatabaseZap, RotateCw } from "lucide-react";
import * as React from "react";
import { ApiError } from "@/lib/api";
import { cn } from "@/lib/format";
import { Button } from "./button";
import { Card, Skeleton } from "./primitives";

export function EmptyState({
  icon,
  title,
  body,
  action,
  className,
}: {
  icon?: React.ReactNode;
  title: string;
  body?: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col items-center rounded-[var(--radius-card)] border border-dashed border-line-strong bg-white/60 px-6 py-12 text-center", className)}>
      {icon && <div className="mb-4 grid h-12 w-12 place-items-center rounded-full bg-teal-50 text-teal [&_svg]:size-5">{icon}</div>}
      <h3 className="text-[15px] font-semibold">{title}</h3>
      {body && <p className="mt-1.5 max-w-md text-[14px] leading-relaxed text-slate">{body}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

export function ErrorState({ error, onRetry, className }: { error: unknown; onRetry?: () => void; className?: string }) {
  const graphDown = error instanceof ApiError && error.graphUnavailable;
  const message = error instanceof Error ? error.message : "Something went wrong.";
  return (
    <div
      role="alert"
      className={cn(
        "flex items-start gap-3 rounded-[var(--radius-card)] border px-4 py-4",
        graphDown ? "border-amber/40 bg-amber-50" : "border-critical/30 bg-critical-50",
        className,
      )}
    >
      <div className={cn("mt-0.5", graphDown ? "text-amber" : "text-critical")}>{graphDown ? <DatabaseZap className="size-5" /> : <AlertTriangle className="size-5" />}</div>
      <div className="flex-1">
        <p className="text-[14px] font-semibold">{graphDown ? "City graph unavailable" : "Couldn't load this"}</p>
        <p className="mt-0.5 text-[13.5px] text-slate">
          {graphDown ? "CityPulse's connected features run on FalkorDB, which isn't reachable right now. Nothing is being shown from a fallback source." : message}
        </p>
      </div>
      {onRetry && (
        <Button size="sm" variant="outline" onClick={onRetry}>
          <RotateCw /> Retry
        </Button>
      )}
    </div>
  );
}

export function ListSkeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="space-y-3" aria-busy="true" aria-label="Loading">
      {Array.from({ length: rows }).map((_, i) => (
        <Card key={i} className="p-5">
          <Skeleton className="mb-3 h-3 w-24" />
          <Skeleton className="mb-2 h-4 w-3/4" />
          <Skeleton className="h-3 w-1/2" />
        </Card>
      ))}
    </div>
  );
}

export function PageHeader({ eyebrow, title, description, action }: { eyebrow?: string; title: React.ReactNode; description?: React.ReactNode; action?: React.ReactNode }) {
  return (
    <header className="mb-8 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
      <div className="max-w-2xl">
        {eyebrow && <div className="eyebrow mb-2">{eyebrow}</div>}
        <h1 className="font-display text-[34px] leading-[1.08] tracking-tight md:text-[42px]">{title}</h1>
        {description && <p className="mt-3 text-[15px] leading-relaxed text-slate">{description}</p>}
      </div>
      {action}
    </header>
  );
}
