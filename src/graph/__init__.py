"""
src/graph — LangGraph orchestration + the FalkorDB visual knowledge graph.

Stage 1 (built): local-Qwen3 LLM helper (`llm.py`) + the FalkorDB client
(`knowledge_graph.py`) that logs agent/tool/event relations, e.g.
`(Sol:Agent)-[:GENERATED]->(Banner:Media)`. Wired into `src.org.agent_loop`
as a best-effort, non-blocking hook — a knowledge-graph outage never breaks
an agent run.

Stage 2 (future, not yet built): a standalone LangGraph `StateGraph` pipeline
with fixed (non-LLM-routed) edges, kept deliberately separate from the live
org daemon (`src.org.daemon`/`executor`/`heartbeat`) — see
docs/architecture.md and src/agents/orchestrator.py's docstring for why an
LLM-routed graph was tried once already and rolled back after a runaway-loop
incident.

Stage 3 (future, not yet built): the inter-agent Telegram debate loop and
fact-extraction into the knowledge graph, gated through src.org.proposals.
"""
