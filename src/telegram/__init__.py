"""
src/telegram — new Telegram-facing features that sit on top of the existing
bot plumbing in src/org/telegram.py (bot instance, per-agent tokens/topics,
command routing). This package holds the features themselves; the bot
wiring/command registration stays in src.org.telegram.

ceo_report.py — Ava's daily CEO report (Revenue, TikTok ad spend/ROAS,
bottlenecks, executed agent commands), scheduled + on-demand via /report.
"""
