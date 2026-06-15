"""LangGraph StateGraph definition — wires all agents together."""
from __future__ import annotations
from langgraph.graph import StateGraph, END
from src.agents.state import AgentState
from src.agents.director import director_node, route_director
from src.agents.workers.trend_scraper import trend_scraper_node
from src.agents.workers.ecommerce import ecommerce_node
from src.agents.workers.marketing import marketing_node
from src.agents.workers.fulfillment import fulfillment_node


def build_graph() -> object:
    """
    Build and compile the LangGraph StateGraph.

    Flow:
        director → [trend_scraper | ecommerce_manager | marketing_agent | fulfillment_agent | END]
        each worker → director (loop back for next routing decision)
    """
    builder = StateGraph(AgentState)

    # Register nodes
    builder.add_node("director", director_node)
    builder.add_node("trend_scraper", trend_scraper_node)
    builder.add_node("ecommerce_manager", ecommerce_node)
    builder.add_node("marketing_agent", marketing_node)
    builder.add_node("fulfillment_agent", fulfillment_node)

    # Entry point
    builder.set_entry_point("director")

    # Director routes to workers (or END)
    builder.add_conditional_edges(
        "director",
        route_director,
        {
            "trend_scraper": "trend_scraper",
            "ecommerce_manager": "ecommerce_manager",
            "marketing_agent": "marketing_agent",
            "fulfillment_agent": "fulfillment_agent",
            "END": END,
        },
    )

    # Every worker loops back to director
    for worker in ("trend_scraper", "ecommerce_manager", "marketing_agent", "fulfillment_agent"):
        builder.add_edge(worker, "director")

    return builder.compile()


# Singleton compiled graph (import and use directly)
graph = build_graph()
