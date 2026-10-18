# AI assistance disclosure

**Development.** This codebase was written with substantial help from Claude Code (Anthropic) in VS Code, working from a detailed product and architecture brief written by the participant. The AI scaffolded the monorepo, wrote backend and frontend code, the Cypher queries, tests and documentation, ran the test suites and the end-to-end browser test, and fixed the failures it found (for example FalkorDB's `exists()` behaviour, Overpass capacity back-off, a nested-form hydration bug). The participant directs the product, reviews and must understand the code, and makes the decisions marked **(review)** in `docs/decisions/log.md`.

**In the product.** The CityPulse agents (Context, Impact, Memory, Coordination) run deterministic graph tools over FalkorDB. An LLM (OpenAI or Gemini, optional via `LLM_PROVIDER`) is used only to phrase the coordinator summary and resident-facing messages. Every decision records which model (or "deterministic-rules (no LLM)") produced it. AI output is labelled, never presented as official fact, and every coordination action needs approval from an authenticated human coordinator.

**Data.** No AI-generated or synthetic city records exist in the production graph. Test fixtures exist only in isolated test graphs.
