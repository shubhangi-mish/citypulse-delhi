"use client";

import * as SwitchPrimitive from "@radix-ui/react-switch";
import * as React from "react";
import { cn } from "@/lib/format";

export function Card({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("rounded-[var(--radius-card)] border border-line bg-white shadow-[var(--shadow-soft)]", className)} {...props} />;
}

export function SectionHeader({ eyebrow, title, action, className }: { eyebrow?: string; title: React.ReactNode; action?: React.ReactNode; className?: string }) {
  return (
    <div className={cn("mb-4 flex items-end justify-between gap-4", className)}>
      <div>
        {eyebrow && <div className="eyebrow mb-1">{eyebrow}</div>}
        <h2 className="text-lg font-semibold tracking-tight">{title}</h2>
      </div>
      {action}
    </div>
  );
}

type Tone = "neutral" | "teal" | "amber" | "critical" | "positive" | "navy" | "violet" | "outline";
const tones: Record<Tone, string> = {
  neutral: "bg-paper-2 text-slate",
  teal: "bg-teal-50 text-teal-600",
  amber: "bg-amber-50 text-[#8a5c17]",
  critical: "bg-critical-50 text-critical",
  positive: "bg-positive-50 text-positive",
  navy: "bg-navy text-white",
  violet: "bg-violet-50 text-violet",
  outline: "border border-line-strong text-slate",
};

export function Badge({ tone = "neutral", className, ...props }: React.HTMLAttributes<HTMLSpanElement> & { tone?: Tone }) {
  return <span className={cn("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11.5px] font-medium [&_svg]:size-3", tones[tone], className)} {...props} />;
}

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(({ className, ...props }, ref) => (
  <input
    ref={ref}
    className={cn(
      "h-11 w-full rounded-[10px] border border-line-strong bg-white px-3.5 text-[15px] placeholder:text-slate/70 focus:border-teal focus:outline-none focus:ring-3 focus:ring-teal/15 disabled:opacity-60",
      className,
    )}
    {...props}
  />
));
Input.displayName = "Input";

export const Textarea = React.forwardRef<HTMLTextAreaElement, React.TextareaHTMLAttributes<HTMLTextAreaElement>>(({ className, ...props }, ref) => (
  <textarea
    ref={ref}
    className={cn(
      "min-h-28 w-full rounded-[10px] border border-line-strong bg-white px-3.5 py-3 text-[15px] placeholder:text-slate/70 focus:border-teal focus:outline-none focus:ring-3 focus:ring-teal/15",
      className,
    )}
    {...props}
  />
));
Textarea.displayName = "Textarea";

export const Select = React.forwardRef<HTMLSelectElement, React.SelectHTMLAttributes<HTMLSelectElement>>(({ className, ...props }, ref) => (
  <select
    ref={ref}
    className={cn(
      "h-11 w-full appearance-none rounded-[10px] border border-line-strong bg-white bg-[url('data:image/svg+xml;utf8,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%2212%22 height=%2212%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22%2364748b%22 stroke-width=%222%22><path d=%22m6 9 6 6 6-6%22/></svg>')] bg-[right_0.9rem_center] bg-no-repeat px-3.5 pr-9 text-[15px] focus:border-teal focus:outline-none focus:ring-3 focus:ring-teal/15",
      className,
    )}
    {...props}
  />
));
Select.displayName = "Select";

export function Field({ label, hint, error, children, htmlFor }: { label: string; hint?: React.ReactNode; error?: string; children: React.ReactNode; htmlFor?: string }) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={htmlFor} className="block text-[13.5px] font-medium text-ink">
        {label}
      </label>
      {children}
      {error ? <p className="text-[12.5px] text-critical">{error}</p> : hint ? <p className="text-[12.5px] text-slate">{hint}</p> : null}
    </div>
  );
}

export function Switch({ checked, onCheckedChange, id, disabled }: { checked: boolean; onCheckedChange: (v: boolean) => void; id?: string; disabled?: boolean }) {
  return (
    <SwitchPrimitive.Root
      id={id}
      checked={checked}
      disabled={disabled}
      onCheckedChange={onCheckedChange}
      className="relative h-6 w-10 shrink-0 rounded-full bg-line-strong transition-colors data-[state=checked]:bg-teal disabled:opacity-50"
    >
      <SwitchPrimitive.Thumb className="block h-5 w-5 translate-x-0.5 rounded-full bg-white shadow transition-transform data-[state=checked]:translate-x-[18px]" />
    </SwitchPrimitive.Root>
  );
}

export function Segmented<T extends string | number>({
  value,
  onChange,
  options,
  className,
  size = "md",
  ariaLabel,
}: {
  value: T;
  onChange: (v: T) => void;
  options: { value: T; label: React.ReactNode }[];
  className?: string;
  size?: "sm" | "md";
  ariaLabel?: string;
}) {
  return (
    <div role="radiogroup" aria-label={ariaLabel} className={cn("inline-flex rounded-[11px] border border-line bg-paper-2 p-0.5", className)}>
      {options.map((o) => (
        <button
          key={String(o.value)}
          role="radio"
          aria-checked={value === o.value}
          onClick={() => onChange(o.value)}
          className={cn(
            "rounded-[9px] font-medium text-slate transition-colors hover:text-ink",
            size === "sm" ? "px-2.5 py-1 text-[12.5px]" : "px-3.5 py-1.5 text-[13.5px]",
            value === o.value && "bg-white text-ink shadow-[0_1px_2px_rgb(23_43_69/0.1)]",
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function Chip({ active, onClick, children }: { active?: boolean; onClick?: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        "inline-flex h-8 shrink-0 items-center gap-1.5 rounded-full border px-3 text-[13px] font-medium transition-colors [&_svg]:size-3.5",
        active ? "border-navy bg-navy text-white" : "border-line-strong bg-white text-ink hover:border-slate/50",
      )}
    >
      {children}
    </button>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("skeleton rounded-md", className)} />;
}

export function Divider({ className }: { className?: string }) {
  return <div className={cn("h-px bg-line", className)} />;
}
