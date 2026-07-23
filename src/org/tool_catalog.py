"""
Real tool catalogs per agent, grouped for the live activity diagram (platform-app
`/agents/live`). Keyed by agent name so each agent can expose its own tool set — today
only Sol has a real tool-use loop (src/org/agent_loop.py), see src/org/seed.py for the
roster. Kept in sync by hand with `_TOOLS` in agent_loop.py — small, stable list.
"""
from __future__ import annotations

AGENT_TOOL_GROUPS: dict[str, dict[str, list[str]]] = {
    "Sol": {
        "store_code": ["list_store_files", "read_store_file", "write_store_file", "edit_store_file", "shell"],
        "shopify": ["shopify_list_products", "shopify_admin", "shopify_publish_products"],
        "sourcing": ["cj_search_products", "cj_add_product", "cj_product_inventory", "cj_track_shipment"],
        # RAG (Redis): Corpus A = search_local_catalog/rag_ingest (seen CJ candidates,
        # written as a side effect of cj_search_products/cj_add_product — see
        # _ingest_cj_candidate in agent_loop.py); Corpus B = search_playbook/refresh_playbook
        # (Sol's own playbook docs). rag_ingest isn't an LLM-callable tool — it's the
        # synthetic name _record_step uses to surface that silent write on the timeline.
        "knowledge": ["search_local_catalog", "rag_ingest", "search_playbook", "refresh_playbook"],
        "comms": ["send_customer_email", "check_inbox", "mark_email_handled"],
    },
}


def tool_groups_for(agent_name: str) -> dict[str, list[str]]:
    return AGENT_TOOL_GROUPS.get(agent_name, {})


def tool_group(agent_name: str, tool_name: str) -> str:
    for group, tools in tool_groups_for(agent_name).items():
        if tool_name in tools:
            return group
    return "other"
