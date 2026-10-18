# CityPulse Delhi — demo script, operating guide and hackathon map

Graph Hacks 2026 (WeMakeDevs × FalkorDB). Tracks entered: **Track 1 — Agents That Act on Connected Data** and **Track 2 — Agent Memory and Coordination**.

## 1. What the hackathon asks for, and what CityPulse does about it

| The brief says | What CityPulse does | Where to see it |
|---|---|---|
| "Agents see pieces, not the whole picture" | One FalkorDB graph connects residents, their professions, events, performers, complaints, official alerts, roads, neighbourhoods and organisations. Agents read all of it before acting. | `/connections`, "See graph connections" on an event |
| "They lose track of what happened in earlier sessions" | The Memory Agent writes an `AgentMemory` node when a case is solved. The next incident retrieves it with a graph query (Query F for reports, Query H for events). It survives restarts (tested). | `/command/memory`; the "Memory:" line in an agent's rationale |
| "They can't explain why they made a choice" | Every agent decision is a node: its inputs, the Cypher query file it used, the paths it followed, its sources, and who it handed off to. Every candidate artist has written reasons; excluded ones say why. | `/command/cases` → the case → action "Why:"; `/command/agents` → a decision |
| Work the graph must do: follow connections | Multi-hop: `Resident → Profession (family)`, `Event → FEATURES → Resident` (booking clash), `Issue → ON_ROAD/NEAR/LOCATED_IN → prior Issue → Case → Memory`. | `graph/queries/F`, `G`, `H` |
| Remember across sessions | `AgentMemory`, `CoordinationCase`, `CoordinationAction`, outcomes. | `/command/memory` |
| Share state between agents | Four agents chained by `INFORMED` edges; each writes its findings to the graph and the next reads them. | decision trace "Hand-off" |
| Connect people, projects, decisions | Person → profession → event/performer → complaint → case → action → agent decision → memory. | graph explorer on the event |
| Show the path behind an answer | Explanation paths with the query file name; graph explorer with edge provenance (source-verified / community / rule-inferred / AI). | decision trace; click an edge |
| Track 1: actions based on what the graph shows | Agents invite artists and notify attendees (graph edges + in-app notifications). Autopilot only when the organiser authorised it (`AUTHORIZED` edge); otherwise they propose and a coordinator approves. | event page "What CityPulse agents did" |
| Track 1: MCP tool selection, graph algorithms | **Not built.** Agents call fixed typed Cypher tools; only shortest-path is used. | — |
| Track 2: per-user/tenant memory, conversation history, high concurrency | **Not built.** One shared graph; no chat; not load-tested. | — |

## 2. The rules, one by one

| # | Rule | Status and what to say |
|---|---|---|
| 1 | Solo or team ≤ 4; one team each | Register once. |
| 2 | FalkorDB primary and central | Yes. Every feature that matters runs on it. |
| 3 | The graph does real work; product must not work without it | Stop FalkorDB and every connected feature returns "City graph unavailable" (HTTP 503), with no fallback database (`test_graph_dependency.py`). Optional 15-second shot: `docker compose stop falkordb`, reload, restart. |
| 4 | Run FalkorDB any way | Docker Compose. |
| 5 | Name every track | Track 1 and Track 2. |
| 6 | Only public, synthetic or your own data; no private/personal data in the graph | OpenStreetMap (ODbL), NDMA SACHET alerts (public domain), events you shared, and **fictional guests** (`example.com`). The only real personal data is the owner's own profile. Do not invite strangers to sign up on a public deployment. |
| 7 | Window: Oct 15 12:01 AM – Oct 18 11:59 PM IST | Submit before then. |
| 8 | Main work starts after the start | The project folder was created Oct 16. The repo's first commit is later because it was committed once the work was done. |
| 9 | Frameworks and public datasets allowed | FastAPI, Next.js, LangGraph, Mapbox, Cytoscape, OSM, NDMA. |
| 10 | Public repo, README + graph model, the Cypher the product depends on, demo video, deployment or local setup, the track | Repo is public. README has the graph diagram and setup. Cypher is in `graph/queries/A–H` and `graph/schema/schema.cypher`. **Video: you record it.** Local setup instructions are in the README. |
| 11 | Disclose AI assistance | `AI_USAGE.md`. |
| 12 | Understand and explain the code | See section 6. |
| 13 | Not entirely AI-generated without your contribution | Be honest in the video: you specified the product, the privacy and real-data rules, the scenario, and verified it; the AI wrote much of the code. Know the model (section 6). |
| 14–18 | Prizes, IP, conduct | Nothing to do. All libraries are open source. |

## 3. Before you press record (pre-flight)

1. Docker Desktop running; `docker compose up -d falkordb postgres`.
2. API: `cd apps/api && uv run uvicorn app.main:app --port 8000 --timeout-keep-alive 75`
3. Web: `cd apps/web && npm run dev` → http://localhost:3100
4. Open **five** browser windows, one per person, each already signed in (quick profiles have no password, so a person lives in the browser that created them):
   - **You (Shubhangi, organiser)**: your normal browser
   - **Aarav** (headliner), **Naina** (vocalist), **Ishita** (painter), **Rohan** (attendee)
5. A fresh, un-cancelled event is ready: *Monsoon Melodies — Hauz Khas* (Aarav booked, Rohan going, Tanvi volunteering, agent autopilot ON).
6. A coordinator tab: http://localhost:3100/command (sign in with your coordinator account).
7. Close notifications and other tabs; browser zoom 100%.

## 4. The video script (about 4:30)

**0:00–0:25 — Hook (Home page, map).** *"Delhi has plenty of problems that only get solved when the right people connect. CityPulse is a city graph on FalkorDB that connects residents, their professions, events, complaints and official alerts, with agents that act on that graph and remember what worked."* Show the live map and "The city graph today" card. *"Real data only: 580 OpenStreetMap neighbourhoods, nearly 3,000 mapped places, and official alerts from NDMA."*

**0:25–0:55 — The setup (organiser window = you).** Open *Monsoon Melodies — Hauz Khas*. Point at: Performers (Aarav, headliner), Participants with **professions** (Rohan, software engineer; Dr. Tanvi, paediatrician), and **Organiser controls** with the agent switch ON. *"I'm the organiser. I've authorised CityPulse agents to act for me if my performer drops out."* (Rule: human authorisation, recorded in the graph.)

**0:55–1:15 — The incident (Aarav's window).** *"My headliner now has a family emergency."* Click **I can't make it anymore** → confirm. *"Attendees are told straight away."*

**1:15–2:15 — The agents act (your window, then `/command`).**
- Your bell lights up. Open the event: **What CityPulse agents did**. *"I didn't click anything. The agents found two nearby artists and invited them, and told my attendees."*
- Go to `/command` → **Coordination cases** → open *Replace cancelled performer: Monsoon Melodies*. Under the **Invite replacement performers** action read the **Why:** line: *"Graph match (Query G): Naina Sethi, score 0.78: opted in to fill-in gigs, same artistic family (music) as the performer who cancelled, lives ~3.5 km away, no overlapping booking; Ishita Rao, 0.41…"* *"Not an LLM guessing: a graph traversal over professions, locations and bookings, and every choice has a written reason."*
- The same "Why:" ends with **"Memory: an earlier disruption (“Sunset Music Evening — Hauz Khas”) was resolved by a Hindustani classical vocalist."** *"The agents remembered the earlier event, retrieved from the graph (Query H)."*
- Then **Agent activity**: four decisions in one run (Context, Impact, Memory, Coordination). Open one: *"each agent hands off to the next, and records its query and its sources."*

**2:15–2:45 — The complaint (Rohan's window).** On the event page click **Report a problem with this event**. Category *Other*; location search "Hauz Khas Village"; title *The headliner pulled out of the music evening*; description *Many of us came for the singer and the library fundraiser depends on it. Can someone help find a replacement?* Submit. *"The complaint links to the event and joins the live case."*

**2:45–3:20 — The graph (your window).** On the event page click **See graph connections**. *"Here is the whole story as a graph: the event, its performers, the invitations, the complaint, the coordination case, and the four agent decisions."* Click an edge (INVITED or FEATURES) to show its provenance and basis. Point at the legend: source-verified, community, rule-inferred, AI. *"AI never masquerades as an official fact."*

**3:20–3:55 — The solution (Naina's window).** Her bell is red; open the event: *"You've been invited to step in."* Click **I can step in**. Switch to your window (it refreshes itself): Naina is the confirmed replacement, the banner is gone, the timeline says so, and the complaint has closed. Rohan's window shows "Good news: Naina Sethi will perform". Ishita's window shows "replacement found, thank you".

**3:55–4:30 — Close.** `/command` → **City memory**: *"What worked is now stored in the graph for next time."* Then: *"Track 1: agents that act on connected data, with the path behind every decision. Track 2: memory that persists and changes later recommendations, with hand-offs between four agents. Privacy-first, real data only, 27 integration tests against a real FalkorDB, open source."* Show the GitHub repo.

**2:30 short version:** hook → organiser setup → Aarav cancels → agents' decision trace → Naina steps in → graph → close.

## 5. If something goes wrong

| Symptom | Fix |
|---|---|
| A page is blank or "City graph unavailable" | Docker Desktop is closed. Start it, then `docker compose up -d falkordb postgres`. |
| Random "Couldn't load this" | Reload once. Start the API with `--timeout-keep-alive 75`. |
| A window signed out | Quick profiles are bound to the browser that created them; ask for the window to be reopened. |
| You already used the event | Create another event and re-add Aarav (Organiser controls → Add a performer), have Rohan join, switch autopilot on. |
| Map is grey | Wait a few seconds; check `NEXT_PUBLIC_MAPBOX_TOKEN` in `.env`. |

## 6. Questions you should be ready for (rule 12)

- **Why a graph?** The answer to "who can replace this performer?" depends on how people, professions, locations and bookings connect; a graph follows those in one query.
- **Show the model.** README diagram: Resident, Profession, Event, Issue, CoordinationCase, CoordinationAction, AgentDecision, AgentMemory, Source, Neighborhood. Key edges: `PRACTICES`, `FEATURES`, `INVITED`, `ABOUT_EVENT`, `ADDRESSES`, `AUTHORIZED`, `INFORMED`, `USED_MEMORY`, `SUMMARIZES`.
- **Query G** (`graph/queries/G_replacement_candidates.cypher`): artists who opted in, within 15 km, ranked by shared discipline family and proximity, excluding anyone with an overlapping `FEATURES` booking.
- **Query H**: resolved disruption cases and their outcomes, reached through `AgentMemory-SUMMARIZES->CoordinationCase-ADDRESSES->Event`.
- **Is the LLM deciding?** No. The agents run deterministic graph tools; an optional LLM only rewrites wording, and every decision records which mode ran.
- **Why is it safe?** Agents act without a coordinator only when the organiser authorised it (recorded as an edge). Otherwise they propose. Emails, addresses and home locations never appear in public responses.
- **What would you build next?** An MCP server exposing the graph tools, graph algorithms (centrality for reliable volunteers), per-organiser memory isolation.
