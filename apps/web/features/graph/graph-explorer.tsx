"use client";

import cytoscape, { type Core } from "cytoscape";
import { Expand, ExternalLink, Route, X } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "@/components/toaster";
import { Button } from "@/components/ui/button";
import { Badge, Card, Chip } from "@/components/ui/primitives";
import { ErrorState } from "@/components/ui/states";
import { GraphSearch, LABEL_NAMES, hrefFor } from "@/features/search/graph-search";
import { api } from "@/lib/api";
import { cn } from "@/lib/format";
import type { GraphEdge, GraphNode } from "@/lib/types";

export const NODE_COLORS: Record<string, string> = {
  Issue: "#157C83",
  Event: "#6D5BB8",
  Warning: "#C98B31",
  Neighborhood: "#172B45",
  AdministrativeArea: "#33507a",
  InfrastructureAsset: "#64748B",
  Organization: "#8a6d3b",
  Road: "#9aa5b4",
  Venue: "#8f84c9",
  Resident: "#b8c2cc",
  CoordinationCase: "#27846B",
  CoordinationAction: "#4fa58c",
  AgentDecision: "#d39b45",
  AgentMemory: "#b5722a",
  Source: "#2b3f5c",
  Coordinator: "#27846B",
  Profession: "#b8456b",
};
const EDGE_CLASS: Record<string, { color: string; label: string; style: "solid" | "dashed" | "dotted" }> = {
  verified: { color: "#172B45", label: "Source-verified", style: "solid" },
  community: { color: "#157C83", label: "Community-reported", style: "solid" },
  inferred: { color: "#6D5BB8", label: "Graph-inferred (rule)", style: "dashed" },
  coordination: { color: "#27846B", label: "Coordination", style: "solid" },
  ai: { color: "#C98B31", label: "AI agent", style: "dotted" },
};

export function GraphExplorer({ initialFocus, heightClass = "h-[620px]", dark }: { initialFocus?: string | null; heightClass?: string; dark?: boolean }) {
  const el = useRef<HTMLDivElement>(null);
  const cy = useRef<Core | null>(null);
  const centerId = useRef<string | null>(null);
  const nodes = useRef(new Map<string, GraphNode>());
  const edges = useRef(new Map<string, GraphEdge>());
  const [selected, setSelected] = useState<GraphNode | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<GraphEdge | null>(null);
  const [classes, setClasses] = useState<string[]>(Object.keys(EDGE_CLASS));
  const [pathFrom, setPathFrom] = useState<GraphNode | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [count, setCount] = useState({ n: 0, e: 0 });

  useEffect(() => {
    if (!el.current) return;
    const c = cytoscape({
      container: el.current,
      minZoom: 0.2,
      maxZoom: 1.4,
      style: [
        {
          selector: "node",
          style: {
            "background-color": "data(color)",
            label: "data(short)",
            "font-size": 10,
            "font-family": "Geist, sans-serif",
            color: dark ? "#e7ecf2" : "#172B45",
            "text-valign": "bottom",
            "text-margin-y": 5,
            "text-wrap": "ellipsis",
            "text-max-width": "110px",
            width: "data(size)",
            height: "data(size)",
            "border-width": 2,
            "border-color": dark ? "#0f1d30" : "#ffffff",
          },
        },
        { selector: "node.center", style: { "border-width": 4, "border-color": "#5FC3BF" } },
        { selector: "node:selected", style: { "border-width": 4, "border-color": "#C98B31" } },
        {
          selector: "edge",
          style: {
            width: 1.4,
            "line-color": "data(color)",
            "target-arrow-color": "data(color)",
            "target-arrow-shape": "triangle",
            "arrow-scale": 0.7,
            "curve-style": "bezier",
            "line-style": "data(lineStyle)" as any,
            opacity: 0.75,
            label: "data(type)",
            "font-size": 7,
            color: dark ? "#9fb0c4" : "#64748B",
            "text-rotation": "autorotate",
            "text-background-color": dark ? "#0f1d30" : "#F7F8F6",
            "text-background-opacity": 1,
            "text-background-padding": "1px",
          },
        },
        { selector: ".path", style: { "line-color": "#C74848", "target-arrow-color": "#C74848", width: 3.5, opacity: 1, "border-color": "#C74848", "border-width": 4 } },
        { selector: ".faded", style: { opacity: 0.12 } },
      ],
    });
    c.on("tap", "node", (e) => {
      setSelectedEdge(null);
      setSelected(nodes.current.get(e.target.id()) ?? null);
    });
    c.on("tap", "edge", (e) => {
      setSelected(null);
      setSelectedEdge(edges.current.get(e.target.id()) ?? null);
    });
    c.on("dbltap", "node", (e) => expand(e.target.id()));
    cy.current = c;
    return () => c.destroy();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const sync = useCallback(() => {
    const c = cy.current;
    if (!c) return;
    const added: string[] = [];
    for (const n of nodes.current.values()) {
      if (!c.getElementById(n.id).length) {
        c.add({ group: "nodes", data: { id: n.id, short: n.name, color: NODE_COLORS[n.label] ?? "#94a3b8", size: ["Issue", "Event", "Warning", "CoordinationCase"].includes(n.label) ? 30 : n.label === "Resident" ? 16 : 22 } });
        added.push(n.id);
      }
    }
    for (const e of edges.current.values()) {
      if (!c.getElementById(e.id).length && c.getElementById(e.source).length && c.getElementById(e.target).length) {
        const k = EDGE_CLASS[e.class] ?? EDGE_CLASS.community;
        c.add({ group: "edges", data: { id: e.id, source: e.source, target: e.target, type: e.type, color: k.color, lineStyle: k.style, cls: e.class } });
      }
    }
    c.edges().forEach((ed) => {
      ed.style("display", classes.includes(ed.data("cls")) ? "element" : "none");
    });
    if (added.length) {
      const focus = centerId.current;
      const layout =
        c.nodes().length <= 40
          ? { name: "concentric", concentric: (n: any) => (n.id() === focus ? 100 : n.degree()), levelWidth: () => 1, minNodeSpacing: 70, spacingFactor: 1.5, animate: true, animationDuration: 400, fit: true, padding: 50 }
          : { name: "cose", animate: false, nodeRepulsion: () => 60000, idealEdgeLength: () => 140, fit: true, padding: 40 };
      c.layout(layout as any).run();
    }
    setCount({ n: c.nodes().length, e: c.edges().length });
  }, [classes]);

  useEffect(() => sync(), [classes, sync]);

  const expand = useCallback(
    async (id: string, reset = false) => {
      try {
        setError(null);
        if (reset) centerId.current = id;
        const r = await api.get<{ center: string; nodes: GraphNode[]; edges: GraphEdge[] }>(`/graph/entities/${id}/neighbors`, { limit: 60 });
        if (reset) {
          nodes.current.clear();
          edges.current.clear();
          cy.current?.elements().remove();
        }
        r.nodes.forEach((n) => nodes.current.set(n.id, n));
        r.edges.forEach((e) => edges.current.set(e.id, e));
        sync();
        cy.current?.nodes().removeClass("center");
        cy.current?.getElementById(id).addClass("center");
        if (reset) setSelected(nodes.current.get(id) ?? null);
      } catch (e) {
        setError(e);
      }
    },
    [sync],
  );

  useEffect(() => {
    if (initialFocus) expand(initialFocus, true);
  }, [initialFocus, expand]);

  const findPath = async (to: GraphNode) => {
    if (!pathFrom) return;
    const r = await api.get<{ found: boolean; nodes: GraphNode[]; rels: string[] }>("/graph/path", { a: pathFrom.id, b: to.id });
    if (!r.found) {
      toast.info("No connecting path within 5 hops.");
      return;
    }
    const c = cy.current!;
    r.nodes.forEach((n) => nodes.current.set(n.id, n));
    for (let i = 0; i < r.rels.length; i++) {
      const a = r.nodes[i].id, b = r.nodes[i + 1].id;
      const existing = [...edges.current.values()].find((e) => (e.source === a && e.target === b) || (e.source === b && e.target === a));
      if (!existing) edges.current.set(`${a}-${r.rels[i]}-${b}`, { id: `${a}-${r.rels[i]}-${b}`, source: a, target: b, type: r.rels[i], class: "community", meaning: r.rels[i] });
    }
    sync();
    c.elements().removeClass("path").addClass("faded");
    for (let i = 0; i < r.nodes.length; i++) {
      c.getElementById(r.nodes[i].id).removeClass("faded").addClass("path");
      if (i < r.rels.length) {
        c.edges().filter((e) => (e.source().id() === r.nodes[i].id && e.target().id() === r.nodes[i + 1].id) || (e.source().id() === r.nodes[i + 1].id && e.target().id() === r.nodes[i].id)).removeClass("faded").addClass("path");
      }
    }
    toast.success(`Path: ${r.nodes.map((n) => n.name).join(" → ")}`);
    setPathFrom(null);
  };

  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
      <div className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <GraphSearch className="w-full max-w-md" placeholder="Pick a report, event, alert, neighbourhood, asset…" onPick={(n) => expand(n.id, true)} />
          <span className={cn("text-[12px]", dark ? "text-white/60" : "text-slate")}>{count.n} nodes · {count.e} relationships · double-click a node to expand</span>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {Object.entries(EDGE_CLASS).map(([k, v]) => (
            <Chip key={k} active={classes.includes(k)} onClick={() => setClasses(classes.includes(k) ? classes.filter((x) => x !== k) : [...classes, k])}>
              <span className="h-0.5 w-4" style={{ background: v.color, borderTop: v.style !== "solid" ? `2px ${v.style} ${v.color}` : undefined }} /> {v.label}
            </Chip>
          ))}
          <Button size="sm" variant="ghost" onClick={() => cy.current?.elements().removeClass("path faded")}>Clear highlight</Button>
        </div>
        {error ? <ErrorState error={error} /> : null}
        <div className={cn("relative overflow-hidden rounded-[var(--radius-card)] border", dark ? "border-white/10 bg-navy-950" : "border-line bg-[radial-gradient(#e2e5df_1px,transparent_1px)] [background-size:18px_18px] bg-white", heightClass)}>
          <div className="absolute inset-0">
            <div ref={el} className="h-full w-full" aria-label="Interactive graph" />
          </div>
          {count.n === 0 && (
            <div className="absolute inset-0 grid place-items-center p-6 text-center">
              <p className={cn("max-w-sm text-[14px]", dark ? "text-white/60" : "text-slate")}>Search for anything in Delhi's city graph to see how it connects — neighbourhoods, metro stations, reports, events, official alerts and coordination.</p>
            </div>
          )}
        </div>
        <div className="flex flex-wrap gap-x-4 gap-y-1.5">
          {Object.entries(NODE_COLORS).slice(0, 12).map(([k, c]) => (
            <span key={k} className={cn("flex items-center gap-1.5 text-[11.5px]", dark ? "text-white/60" : "text-slate")}>
              <span className="size-2.5 rounded-full" style={{ background: c }} /> {LABEL_NAMES[k] ?? k.replace(/([a-z])([A-Z])/g, "$1 $2")}
            </span>
          ))}
        </div>
      </div>

      <Card className={cn("h-fit p-5", dark && "border-white/10 bg-navy-800 text-white")}>
        {selected ? (
          <div>
            <div className="flex items-start justify-between gap-2">
              <Badge tone="neutral" className={dark ? "bg-white/10 text-white" : ""}>{LABEL_NAMES[selected.label] ?? selected.label}</Badge>
              <button onClick={() => setSelected(null)} aria-label="Close"><X className="size-4 opacity-60" /></button>
            </div>
            <h3 className="mt-2 text-[16px] font-semibold leading-snug">{selected.name}</h3>
            <dl className="mt-3 space-y-1.5 text-[12.5px]">
              {Object.entries(selected.props)
                .filter(([k, v]) => v !== null && v !== "" && !k.endsWith("_id") && typeof v !== "object")
                .slice(0, 12)
                .map(([k, v]) => (
                  <div key={k} className="grid grid-cols-[110px_1fr] gap-2">
                    <dt className="opacity-60">{k.replace(/_/g, " ")}</dt>
                    <dd className="break-words">{typeof v === "number" && v > 1e12 ? new Date(v).toLocaleString("en-IN") : String(v)}</dd>
                  </div>
                ))}
            </dl>
            <div className="mt-4 flex flex-wrap gap-2">
              {selected.expandable !== false && <Button size="sm" variant={dark ? "dark" : "outline"} onClick={() => expand(selected.id)}><Expand /> Expand</Button>}
              {["Issue", "Event", "Warning"].includes(selected.label) && <Button size="sm" variant={dark ? "dark" : "outline"} asChild><Link href={hrefFor(selected)}><ExternalLink /> Open</Link></Button>}
              {selected.expandable !== false &&
                (pathFrom && pathFrom.id !== selected.id ? (
                  <Button size="sm" variant="accent" onClick={() => findPath(selected)}><Route /> Path from {pathFrom.name.slice(0, 18)}</Button>
                ) : (
                  <Button size="sm" variant="ghost" onClick={() => { setPathFrom(selected); toast.info("Now select another node and choose 'Path from…'."); }}><Route /> Find path from here</Button>
                ))}
            </div>
            {selected.label === "Resident" && <p className="mt-3 text-[12px] opacity-70">Residents appear only as private nodes unless they opted into a public, named profile. They can't be expanded.</p>}
          </div>
        ) : selectedEdge ? (
          <div>
            <Badge tone="neutral">{selectedEdge.type}</Badge>
            <p className="mt-2 text-[14px]">
              <b>{nodes.current.get(selectedEdge.source)?.name}</b> <span className="opacity-70">{selectedEdge.meaning}</span> <b>{nodes.current.get(selectedEdge.target)?.name}</b>
            </p>
            <dl className="mt-3 space-y-1 text-[12.5px]">
              <div>Provenance class: <b>{EDGE_CLASS[selectedEdge.class]?.label}</b></div>
              {selectedEdge.basis && <div>Basis: {selectedEdge.basis}</div>}
              {selectedEdge.verification_status && <div>Status: {selectedEdge.verification_status}</div>}
              {selectedEdge.score != null && <div>Score: {selectedEdge.score}</div>}
              {selectedEdge.reasons?.map((r) => <div key={r}>• {r}</div>)}
            </dl>
          </div>
        ) : (
          <div className="text-[13.5px] leading-relaxed opacity-80">
            <p className="font-semibold">How to read this</p>
            <ul className="mt-2 space-y-1.5 text-[12.5px]">
              <li>Solid navy edges come from documented sources (OSM boundaries, official alerts).</li>
              <li>Teal edges were created by residents (reported, affected, follows).</li>
              <li>Dashed violet edges are deterministic graph rules (nearest place, same road, time overlap).</li>
              <li>Dotted amber edges were written by AI agents and always need human review.</li>
            </ul>
            <p className="mt-3 text-[12.5px]">Click a node or edge to inspect its provenance.</p>
          </div>
        )}
      </Card>
    </div>
  );
}
