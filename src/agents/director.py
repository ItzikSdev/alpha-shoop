"""Director Agent — routes to the correct worker via the LiteLLM proxy."""
from __future__ import annotations

import json
import re

from langchain_core.messages import HumanMessage, SystemMessage

from src.agents.state import AgentState
from src.config import get_settings
from src.llm import get_llm
from src.embeddings import query_store_knowledge
from src.mcp_tools.shopify_analytics import get_sales_summary
from src.tracing import agent_log
from src.tracing.context import current_node

_SYSTEM_PROMPT = """\
You are the Director Agent in an autonomous e-commerce arbitrage system.
Your job is to orchestrate store creation and coordinate all worker agents.
ALL store information and credentials are saved to platform-app at http://localhost:5173/stores

📋 YOUR RESPONSIBILITIES:
1. Coordinate worker agents in the correct sequence
2. Ensure admin_token is securely saved to PostgreSQL (encrypted)
3. Pass store_id to all downstream agents
4. Update platform-app /stores with real-time status
5. Monitor for errors and retry if needed

Workers available:
- store_setup       : Create store on platform → get admin_token → save to DB with encryption
- design_agent      : Mode 1: generate design spec+CSS. Mode 2: review & approve
- frontend_agent    : Implement design spec → push theme to store using admin_token
- trend_scraper     : Find trending products with 10-30% markup, psychological pricing
- ecommerce_manager : Create products on store using admin_token
- marketing_agent   : Launch campaigns (Google Ads / Meta Ads)
- fulfillment_agent : Place supplier orders and track shipments
- END               : Task complete, update platform-app status to ✅ LIVE

🔐 CREDENTIAL MANAGEMENT:
When store_setup creates store:
- Receive: {store_id, admin_token, api_key, shop_url}
- Action: Encrypt admin_token with AES-256
- Store: INSERT into PostgreSQL stores table
- Pass: store_id to all downstream agents (they query DB for token)
- Update: platform-app /stores with new store info

🌐 PLATFORM-APP INTEGRATION:
After each step, update http://localhost:5173/stores with:
- store_status: 'pending' → 'designing' → 'deploying' → 'active'
- design_status: 'pending' → 'approved' → 'deployed'
- product_count: updated as products are added
- revenue: updated in real-time
- last_updated: timestamp

ROUTING RULES (apply in order):
1. NEW STORE REQUEST → store_setup (always first)
   - Get admin_token from Shopify
   - Save encrypted token to PostgreSQL
   - Update platform-app status: 'setting_up'

2. After store_setup → design_agent (Mode 1: generate spec)
   - Query DB with store_id (get admin_token if needed)
   - Update platform-app status: 'designing'

3. design_spec ready AND design_approved is false → frontend_agent
   - Get admin_token from PostgreSQL using store_id
   - Push theme to store
   - Update platform-app status: 'deploying_theme'

4. frontend_agent complete AND design_approved is false → design_agent (Mode 2: review)
   - Review and approve design
   - Update platform-app status: 'theme_approved'

5. design_approved is true → trend_scraper
   - Query DB for store_id (pass credentials if multi-platform)
   - Find trending products
   - Update platform-app status: 'finding_products'

6. Products found → ecommerce_manager
   - Get admin_token from PostgreSQL using store_id
   - Create products on store
   - Update platform-app status: 'adding_products'
   - Update product_count in platform-app

7. Products created → marketing_agent (if task includes [MARKETING])
   - Launch campaigns
   - Update platform-app status: 'running_campaigns'

8. All complete → END
   - Update platform-app status: '✅ LIVE & READY'
   - Final revenue calculation
   - Store is now live and accepting orders

DESIGN LOOP RULES:
- design_agent Mode 1 ALWAYS before frontend_agent
- frontend_agent ALWAYS after design_agent Mode 1
- design_agent Mode 2 ALWAYS after frontend_agent
- Loop max 3 times, then force design_approved=true
- Update platform-app after each loop iteration

ERROR HANDLING:
- If store_setup fails → END with error in platform-app
- If design fails → retry with modified specs max 2 times
- If frontend fails → retry theme deployment max 2 times
- If trend_scraper fails → use fallback trending products
- Any unrecoverable error → log to platform-app and END

🚀 EXAMPLE: CREATE NEW STORE
User action: POST /api/v1/stores {platform: 'shopify', store_name: 'My Shop'}
You (Director Agent):
  1. Route → store_setup
  2. store_setup creates Shopify store, returns admin_token
  3. Store admin_token encrypted in PostgreSQL
  4. Update platform-app /stores with new store entry
  5. Route → design_agent (Mode 1)
  6. design_agent generates design spec
  7. Update platform-app: 'design_spec_ready'
  8. Route → frontend_agent
  9. frontend_agent gets admin_token from DB, pushes theme
  10. Update platform-app: 'theme_deployed'
  11. Route → design_agent (Mode 2: review)
  12. design_agent approves or requests changes
  13. If approved → trend_scraper
  14. trend_scraper finds products
  15. Update platform-app product_count
  16. Route → ecommerce_manager
  17. ecommerce_manager creates products using admin_token
  18. Update platform-app: '✅ LIVE - 150 products, $5,234 revenue'

TOTAL TIME: ~15-25 minutes
RESULT: Store fully configured, live, and visible in platform-app /stores

SOURCING LOOP RULES:
- If ecommerce_manager rejects all candidates as off-niche, it sets sourcing_feedback
  (not error) and increments sourcing_attempts — route back to trend_scraper to retry
  with relaxed search terms, do NOT route to END in this case
- This retry loop repeats max 3 times (sourcing_attempts), then ecommerce_manager sets
  a hard error itself and the run should end

HEALTH MONITORING RULES (apply when task contains [MONITOR]):
9.  If store has 0 products → route to trend_scraper (need products before we can sell)
10. If store health is "no_sales" and products exist → route to marketing_agent (drive traffic)
11. If store health is "low" (some sales, low revenue) → route to trend_scraper (more/better products)
12. If store health is "healthy" → route to END (store is doing well)

If "Store knowledge" is present in the context, it is the owner's own description of
what the store currently contains and what it should become — treat it as ground
truth about scope/assortment (e.g. "should carry boys AND girls clothing separately")
and factor it into routing (e.g. route to trend_scraper again if the description
implies missing categories even when some products already exist).

Current limits (HARD guardrails, never override):
- Max daily ad spend: ${max_ad_spend_daily} USD
- Max single order: ${max_order_value} USD

If the last worker reported an error, do not call it again — route to END.

Respond with ONLY a JSON object: {{"next": "<worker_name>", "reasoning": "<one sentence>"}}
"""


async def director_node(state: AgentState) -> dict:
    """LangGraph node: Director decides the next worker to call."""
    current_node.set("director")
    if state.get("kill_switch_triggered"):
        return {"next_agent": "END", "director_reasoning": "Kill-switch is active."}

    # Hard stop: if any worker returned an error, never loop — end immediately.
    # The LLM tends to retry the same worker which causes infinite loops.
    if state.get("error"):
        reason = f"Worker error — stopping: {state['error']}"
        agent_log(reason, "warning")
        return {"next_agent": "END", "director_reasoning": reason}

    settings = get_settings()
    llm = get_llm("director", temperature=0.0)

    # Fetch store health if this is a monitor run and we haven't fetched it yet
    health = state.get("store_health")
    task = state.get("task", "")
    if "[MONITOR]" in task and health is None:
        agent_log("Fetching store revenue and sales data...", "info")
        health = await get_sales_summary(days=7)
        agent_log(
            f"Store health: {health['status']} | {health['order_count']} orders | ${health['revenue_usd']} revenue (7d)",
            "action",
        )

    # Agentic RAG: pull relevant store knowledge (what it contains + what it should become)
    # once per run, scoped to this store, semantically matched against the task.
    knowledge = state.get("store_knowledge")
    store_id = state.get("store_id")
    if knowledge is None:
        knowledge = await query_store_knowledge(task, store_id=store_id, top_k=2) if store_id else []
        if knowledge:
            agent_log(f"Retrieved store knowledge ({len(knowledge)} match(es)) via RAG", "info")

    system = _SYSTEM_PROMPT.format(
        max_ad_spend_daily=settings.max_ad_spend_daily_usd,
        max_order_value=settings.max_order_value_usd,
    )

    health_line = ""
    if health:
        health_line = (
            f"Store health (7 days): status={health['status']} | "
            f"orders={health['order_count']} | revenue=${health['revenue_usd']}\n"
        )

    knowledge_line = ""
    if knowledge:
        knowledge_line = "Store knowledge (from owner's description, via RAG):\n" + "\n".join(
            f"  - {k['document'][:300]}" for k in knowledge
        ) + "\n"

    design_spec = state.get("design_spec")
    context = (
        f"Task: {task}\n"
        + knowledge_line +
        f"Store brand set: {'yes — ' + state['store_brand'].get('store_name','?') if state.get('store_brand') else 'NO — must run store_setup first'}\n"
        f"design_spec: {'set (' + str(len(design_spec.get('quality_checklist',[]))) + ' criteria)' if design_spec else 'null — design_agent Mode 1 not run yet'}\n"
        f"design_approved: {state.get('design_approved', False)}\n"
        f"design_iterations: {state.get('design_iterations', 0)}\n"
        f"frontend_report: {'set' if state.get('frontend_report') else 'null'}\n"
        f"store_designed (loop complete): {'yes' if state.get('store_designed') else 'no'}\n"
        f"Products found (scraper batch): {len(state.get('trending_products', []))}\n"
        f"Shopify products created this run: {len(state.get('shopify_products_created', []))}\n"
        f"sourcing_attempts: {state.get('sourcing_attempts', 0)}/3\n"
        f"sourcing_feedback: {state.get('sourcing_feedback') or 'none — no retry needed'}\n"
        f"Budget remaining: ${state.get('budget_remaining_usd', 0):.2f}\n"
        + health_line +
        f"Last error: {state.get('error') or 'none'}\n"
    )

    agent_log("Deciding next step...", "info")
    response = await llm.ainvoke([SystemMessage(content=system), HumanMessage(content=context)])
    raw = str(response.content).strip()
    raw = re.sub(r'^```(?:json)?\s*', '', raw)
    raw = re.sub(r'\s*```\s*$', '', raw)
    try:
        parsed = json.loads(raw.strip())
        next_node = parsed["next"]
        reasoning = parsed.get("reasoning", "")
    except (json.JSONDecodeError, KeyError, ValueError) as exc:
        # LLM occasionally returns empty/malformed content (rate limit, truncation).
        # Don't crash the whole graph run — end gracefully so the run shows as
        # completed-but-incomplete rather than a hard failure with a stack trace.
        reasoning = f"Director response unparseable ({exc}) — ending run safely"
        agent_log(reasoning, "error")
        return {
            "next_agent": "END",
            "director_reasoning": reasoning,
            "store_health": health,
            "store_knowledge": knowledge,
        }

    agent_log(f"→ {next_node}  ({reasoning})", "action")

    return {
        "next_agent": next_node,
        "director_reasoning": reasoning,
        "store_health": health,
        "store_knowledge": knowledge,
        "messages": [response],
    }


def route_director(state: AgentState) -> str:
    """Conditional edge: maps next_agent to the correct LangGraph node."""
    return state.get("next_agent", "END")
