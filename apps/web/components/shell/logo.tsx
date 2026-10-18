import { cn } from "@/lib/format";

export function LogoMark({ className, inverted }: { className?: string; inverted?: boolean }) {
  return (
    <svg viewBox="0 0 32 32" className={cn("size-8", className)} aria-hidden="true">
      <rect width="32" height="32" rx="9" fill={inverted ? "#ffffff" : "#172B45"} />
      <path
        d="M5 17.5h5.2l2.6-6.5 4.4 11 2.9-7.2 1.6 2.7H27"
        fill="none"
        stroke={inverted ? "#157C83" : "#5FC3BF"}
        strokeWidth="2.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function Logo({ inverted, suffix }: { inverted?: boolean; suffix?: string }) {
  return (
    <span className="flex items-center gap-2.5">
      <LogoMark inverted={inverted} />
      <span className={cn("text-[17px] font-semibold tracking-tight", inverted ? "text-white" : "text-navy")}>
        CityPulse
        <span className={cn("ml-1.5 font-display text-[19px] font-normal italic", inverted ? "text-[#7fd1c0]" : "text-teal")}>{suffix ?? "Delhi"}</span>
      </span>
    </span>
  );
}
