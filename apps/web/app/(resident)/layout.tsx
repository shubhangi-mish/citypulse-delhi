import { ResidentShell } from "@/components/shell/resident-shell";

export default function ResidentLayout({ children }: { children: React.ReactNode }) {
  return <ResidentShell>{children}</ResidentShell>;
}
