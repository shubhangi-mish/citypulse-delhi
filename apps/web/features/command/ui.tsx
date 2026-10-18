import { cn } from "@/lib/format";

export function CmdHeader({ title, description, action }: { title: string; description?: string; action?: React.ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-[24px] font-semibold tracking-tight">{title}</h1>
        {description && <p className="mt-1 max-w-2xl text-[13.5px] text-slate">{description}</p>}
      </div>
      {action}
    </div>
  );
}

export function Panel({ title, children, className, action }: { title?: string; children: React.ReactNode; className?: string; action?: React.ReactNode }) {
  return (
    <section className={cn("rounded-xl border border-line bg-white", className)}>
      {title && (
        <div className="flex items-center justify-between border-b border-line px-4 py-3">
          <h2 className="text-[13px] font-semibold uppercase tracking-wider text-slate">{title}</h2>
          {action}
        </div>
      )}
      <div className="p-4">{children}</div>
    </section>
  );
}

export function Stat({ label, value, tone }: { label: string; value: number | string | undefined; tone?: "amber" | "teal" | "critical" }) {
  return (
    <div className="rounded-xl border border-line bg-white p-4">
      <p className="text-[12px] text-slate">{label}</p>
      <p className={cn("mt-1 text-[28px] font-semibold tabular-nums", tone === "amber" && "text-amber", tone === "teal" && "text-teal", tone === "critical" && "text-critical")}>{value ?? "—"}</p>
    </div>
  );
}
