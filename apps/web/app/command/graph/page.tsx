"use client";

import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { CmdHeader } from "@/features/command/ui";
import { GraphExplorer } from "@/features/graph/graph-explorer";

function G() {
  return (
    <div>
      <CmdHeader title="Graph investigation" description="Traverse FalkorDB around any entity. Private residents stay anonymised here too; there is no free-form Cypher console." />
      <GraphExplorer initialFocus={useSearchParams().get("focus")} heightClass="h-[680px]" />
    </div>
  );
}

export default function Page() {
  return <Suspense><G /></Suspense>;
}
