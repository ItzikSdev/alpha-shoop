"""Marketing Agent — launches Google Ads campaigns for new Shopify products."""
from __future__ import annotations
from langchain_core.messages import HumanMessage
from src.agents.state import AgentState
from src.config import get_settings
from src.mcp_tools.ads import create_google_campaign, get_campaign_metrics
from src.guardrails.kill_switch import KillSwitch

_kill_switch = KillSwitch()


async def marketing_node(state: AgentState) -> dict:
    """LangGraph node: creates campaigns and tracks spend against guardrail."""
    settings = get_settings()
    budget_per_campaign = min(
        state.get("budget_remaining_usd", 0) / max(len(state.get("shopify_products_created", [])), 1),
        50.0,  # cap per campaign
    )

    campaign_ids: list[str] = []
    total_spend = state.get("total_ad_spend_usd", 0.0)

    for product_id in state.get("shopify_products_created", []):
        result = await create_google_campaign(
            campaign_name=f"AS-{product_id[:8]}",
            daily_budget_usd=budget_per_campaign,
            keywords=["dropshipping", "buy online"],
            target_countries=["US"],
        )
        campaign_id = result.get("campaign_id", "")
        if campaign_id:
            campaign_ids.append(campaign_id)

            metrics = await get_campaign_metrics(campaign_id=campaign_id, date_range="LAST_7_DAYS")
            total_spend += metrics.get("spend_usd", 0.0)

            # Guardrail: check daily spend limit
            try:
                _kill_switch.record_spend(metrics.get("spend_usd", 0.0), settings.max_ad_spend_daily_usd)
            except ValueError:
                return {
                    "campaign_ids": campaign_ids,
                    "total_ad_spend_usd": total_spend,
                    "kill_switch_triggered": True,
                    "messages": [HumanMessage(content="KILL SWITCH: daily ad spend limit exceeded")],
                }

    return {
        "campaign_ids": campaign_ids,
        "total_ad_spend_usd": total_spend,
        "budget_remaining_usd": state.get("budget_remaining_usd", 0) - total_spend,
        "messages": [HumanMessage(content=f"Launched {len(campaign_ids)} campaigns, ${total_spend:.2f} spent")],
    }
