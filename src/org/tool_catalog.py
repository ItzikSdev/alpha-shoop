"""
Real tool catalogs per agent, grouped for the live activity diagram (platform-app
`/agents/live`) and for the FalkorDB knowledge graph (src/graph/knowledge_graph.py's
`seed_org_graph`, which draws a CAN_USE edge per entry). Keyed by agent name so each
agent exposes its own tool set — see src/org/seed.py for the roster.

Sol is the only one with a generic LLM tool-use loop (src/org/agent_loop.py, kept in
sync by hand with its `_TOOLS`); the other agents' "tools" are the concrete functions
their own handlers call (src/org/conversation.py `_agent_act_*`, src/org/fulfillment.py,
src/tiktok_mcp/server.py). Listing them here is what makes the whole company visible in
the graph instead of just whoever happens to have executed something.
"""
from __future__ import annotations

AGENT_TOOL_GROUPS: dict[str, dict[str, list[str]]] = {
    "Sol": {
        "shopify": ["shopify_list_products", "shopify_admin", "shopify_publish_products"],
        "sourcing": ["cj_search_products", "cj_add_product", "cj_product_inventory",
                     "cj_track_shipment", "cj_stock_sweep"],
        # Peer delegation — the edge that was missing from the graph entirely: Sol
        # can now reach the teammate who owns what he doesn't (media, warehouse)
        # instead of working around a blocked product.
        "teamwork": ["ask_teammate"],
        # RAG (Redis): Corpus A = search_local_catalog/rag_ingest (seen CJ candidates,
        # written as a side effect of cj_search_products/cj_add_product — see
        # _ingest_cj_candidate in agent_loop.py); Corpus B = search_playbook/refresh_playbook
        # (Sol's own playbook docs). rag_ingest isn't an LLM-callable tool — it's the
        # synthetic name _record_step uses to surface that silent write on the timeline.
        "knowledge": ["search_local_catalog", "rag_ingest", "search_playbook", "refresh_playbook"],
    },
    "Ava": {
        # The CEO's "tools" are her decision types (src/org/executor.py) — `assign`
        # is the one that reaches other agents.
        "management": ["assign", "set_goal", "record_lesson", "flag_blocker", "cancel_stuck_runs"],
        "operations": ["boost_store", "create_ticket", "close_ticket"],
        "shopify": ["shopify_admin"],
    },
    "Reel": {
        # generate_video (Wan2.2 scripted-ad pipeline) removed 2026-08-20 —
        # Wan2.2/ComfyUI was retired (owner decision, quality). Rotation video
        # (Veo) is the only real video pipeline left; images cover the rest.
        "video": ["generate_rotation_video", "approve_video", "reject_video"],
        "image": ["generate_image"],
        "catalog": ["list_video_candidates"],
    },
    "Nora": {
        "inbox": ["process_central_inbox", "check_inbox", "mark_email_handled"],
        "comms": ["send_customer_email"],
        "knowledge": ["search_store_products_rag"],
    },
    "Milo": {
        # No LLM tool-loop — these are plain functions his deterministic
        # process_order() (src/org/fulfillment.py) calls directly, triggered
        # by the Shopify order webhook. cj_product_inventory/cj_track_shipment
        # were listed here before but are actually Sol's (agent_loop.py's
        # _TOOLS) — Milo has no mechanism to call them. send_customer_email
        # doesn't exist for anyone (removed from Sol's tools, never Milo's);
        # his real email call is send_email (src/mcp_tools/email.py).
        "fulfillment": ["place_supplier_order", "fulfill_shopify_order"],
        "comms": ["send_email"],
    },
    "Kai": {
        # Read-only by charter — no campaign create/edit/pause tool exists on purpose.
        "ads_auth": ["tiktok_ads_login", "tiktok_ads_complete_auth", "tiktok_ads_auth_status"],
        "ads_reporting": ["get_ads_report", "list_campaigns"],
        "ads_manual": ["read_ads_export", "ads_export_status"],
    },
    "Nova": {
        # create_ticket/close_ticket-only by charter — same authority every other
        # non-CEO agent has, no assign/ask_teammate/dispatch_to_agent. Read-only
        # reporting matches Kai's scope so a weekly check is grounded in real
        # numbers, not a guess.
        "oversight": ["create_ticket", "close_ticket"],
        "knowledge": ["search_playbook", "search_local_catalog", "read_org_docs"],
        "ads_reporting": ["get_ads_report", "list_campaigns"],
        "shopify_reporting": ["get_sales_summary"],
        # Outside-world context (competitor pricing, marketing trends, industry
        # benchmarks) via Serper — real web results, never invented. Read-only,
        # same as everything else above: informs a create_ticket/record_lesson,
        # never itself an action.
        "market_research": ["search_web", "search_market_prices"],
        # Read-only FalkorDB queries over the org's own knowledge graph — no
        # CAN_USE edge for a repeatedly-attempted tool, a tool that keeps
        # failing, a delegation with no follow-up. Feeds Nova's weekly
        # create_ticket, never a write to the graph itself. NOT tool-creation:
        # Nova can point at a gap, she cannot register a new tool for herself
        # or anyone else — that stays a human-reviewed code change.
        "diagnostics": ["find_capability_gaps"],
    },
}


def all_tool_names() -> dict[str, list[str]]:
    """{agent_name: [every tool they can use]} — flattened across groups.
    Used to seed the knowledge graph's CAN_USE edges."""
    return {
        agent: [t for tools in groups.values() for t in tools]
        for agent, groups in AGENT_TOOL_GROUPS.items()
    }


def tool_groups_for(agent_name: str) -> dict[str, list[str]]:
    return AGENT_TOOL_GROUPS.get(agent_name, {})


def tool_group(agent_name: str, tool_name: str) -> str:
    for group, tools in tool_groups_for(agent_name).items():
        if tool_name in tools:
            return group
    return "other"
