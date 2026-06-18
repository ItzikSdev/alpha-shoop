"""LangGraph StateGraph definition — wires all agents together."""
from __future__ import annotations
from langgraph.graph import StateGraph, END
from src.agents.state import AgentState
from src.agents.director import director_node, route_director
from src.agents.workers.store_setup import store_setup_node
from src.agents.workers.trend_scraper import trend_scraper_node
from src.agents.workers.ecommerce import ecommerce_node
from src.agents.workers.marketing import marketing_node
from src.agents.workers.fulfillment import fulfillment_node


def build_graph() -> object:
    """
    Build and compile the LangGraph StateGraph.

    Flow:
        director → [store_setup | trend_scraper | ecommerce_manager | marketing_agent | fulfillment_agent | END]
        each worker → director (loop back for next routing decision)
    """
    builder = StateGraph(AgentState)

    builder.add_node("director", director_node)
    builder.add_node("store_setup", store_setup_node)
    builder.add_node("trend_scraper", trend_scraper_node)
    builder.add_node("ecommerce_manager", ecommerce_node)
    builder.add_node("marketing_agent", marketing_node)
    builder.add_node("fulfillment_agent", fulfillment_node)

    builder.set_entry_point("director")

    builder.add_conditional_edges(
        "director",
        route_director,
        {
            "store_setup": "store_setup",
            "trend_scraper": "trend_scraper",
            "ecommerce_manager": "ecommerce_manager",
            "marketing_agent": "marketing_agent",
            "fulfillment_agent": "fulfillment_agent",
            "END": END,
        },
    )

    for worker in ("store_setup", "trend_scraper", "ecommerce_manager", "marketing_agent", "fulfillment_agent"):
        builder.add_edge(worker, "director")

    return builder.compile()


graph = build_graph()
