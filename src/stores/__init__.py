"""Multi-store configuration — per-store Shopify credentials and cached brand state."""
from __future__ import annotations

import json
import os
import sqlite3
import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

_DB_PATH = Path(os.environ.get("TRACES_DB_PATH", "./data/traces.db"))


@dataclass
class StoreConfig:
    store_id: str
    name: str
    shopify_domain: str
    shopify_access_token: str
    platform: str = "shopify"  # future: "woocommerce" | "etsy" | ...
    niche: str = ""
    store_brand: dict = field(default_factory=dict)
    store_designed: bool = False  # has the design loop genuinely completed for this store?
    active: bool = True
    created_at: str = ""
    payplus_api_key: str = ""   # PayPlus payment gateway — set after manual app install
    payplus_secret: str = ""    # PayPlus secret key
    installed_theme: str = ""   # e.g. "dawn", "craft", "sense"
    description: str = ""       # free text: what the store contains today + what it should become.
                                 # Embedded into the vector store so agents can RAG over it.
    storefront_api_token: str = ""  # Storefront API access token for the Hydrogen frontend
    oxygen_deploy_token: str = ""   # Shopify Oxygen deployment token for the Hydrogen storefront
    storefront_slug: str = ""       # slug used for the host-side storefront/theme folder
    theme_access_password: str = "" # Theme Access app password (shptka_…) — needed for `shopify theme dev`


# ContextVar: which store is active for this async task
_current_store: ContextVar[StoreConfig | None] = ContextVar("current_store", default=None)


def init_stores_table() -> None:
    with sqlite3.connect(_DB_PATH) as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS stores (
                store_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                shopify_domain TEXT NOT NULL,
                shopify_access_token TEXT NOT NULL,
                platform TEXT DEFAULT 'shopify',
                niche TEXT DEFAULT '',
                store_brand TEXT DEFAULT '{}',
                active INTEGER DEFAULT 1,
                created_at TEXT NOT NULL,
                payplus_api_key TEXT DEFAULT '',
                payplus_secret TEXT DEFAULT '',
                installed_theme TEXT DEFAULT '',
                description TEXT DEFAULT '',
                storefront_api_token TEXT DEFAULT '',
                oxygen_deploy_token TEXT DEFAULT '',
                storefront_slug TEXT DEFAULT '',
                theme_access_password TEXT DEFAULT '',
                store_designed INTEGER DEFAULT 0
            )
        """)
        # Migrations: add columns added after initial schema
        for col, default in [
            ("platform", "'shopify'"),
            ("payplus_api_key", "''"),
            ("payplus_secret", "''"),
            ("installed_theme", "''"),
            ("description", "''"),
            ("storefront_api_token", "''"),
            ("oxygen_deploy_token", "''"),
            ("storefront_slug", "''"),
            ("theme_access_password", "''"),
            ("store_designed", "0"),
        ]:
            try:
                con.execute(f"ALTER TABLE stores ADD COLUMN {col} TEXT DEFAULT {default}")
            except Exception:
                pass
        con.commit()


_SELECT_COLS = (
    "store_id, name, shopify_domain, shopify_access_token, platform, niche, "
    "store_brand, active, created_at, payplus_api_key, payplus_secret, installed_theme, description, "
    "storefront_api_token, oxygen_deploy_token, storefront_slug, theme_access_password, store_designed"
)


def _row_to_store(r: tuple) -> StoreConfig:
    return StoreConfig(
        store_id=r[0], name=r[1], shopify_domain=r[2],
        shopify_access_token=r[3], platform=r[4] or "shopify",
        niche=r[5], store_brand=json.loads(r[6] or "{}"),
        active=bool(r[7]), created_at=r[8],
        payplus_api_key=r[9] or "", payplus_secret=r[10] or "",
        installed_theme=r[11] or "", description=r[12] or "",
        storefront_api_token=r[13] or "", oxygen_deploy_token=r[14] or "",
        storefront_slug=r[15] or "", theme_access_password=r[16] or "",
        store_designed=bool(int(r[17] or 0)),
    )


def list_stores() -> list[StoreConfig]:
    with sqlite3.connect(_DB_PATH) as con:
        rows = con.execute(
            f"SELECT {_SELECT_COLS} FROM stores ORDER BY created_at DESC"
        ).fetchall()
    return [_row_to_store(r) for r in rows]


def get_store(store_id: str) -> StoreConfig | None:
    with sqlite3.connect(_DB_PATH) as con:
        row = con.execute(
            f"SELECT {_SELECT_COLS} FROM stores WHERE store_id = ?",
            (store_id,),
        ).fetchone()
    return _row_to_store(row) if row else None


def save_store(store: StoreConfig) -> None:
    with sqlite3.connect(_DB_PATH) as con:
        con.execute(
            """INSERT OR REPLACE INTO stores
               (store_id, name, shopify_domain, shopify_access_token, platform, niche,
                store_brand, active, created_at, payplus_api_key, payplus_secret, installed_theme, description,
                storefront_api_token, oxygen_deploy_token, storefront_slug, theme_access_password, store_designed)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                store.store_id, store.name, store.shopify_domain,
                store.shopify_access_token, store.platform, store.niche,
                json.dumps(store.store_brand), int(store.active), store.created_at,
                store.payplus_api_key, store.payplus_secret, store.installed_theme, store.description,
                store.storefront_api_token, store.oxygen_deploy_token, store.storefront_slug,
                store.theme_access_password, int(store.store_designed),
            ),
        )
        con.commit()


def delete_store(store_id: str) -> bool:
    with sqlite3.connect(_DB_PATH) as con:
        cur = con.execute("DELETE FROM stores WHERE store_id = ?", (store_id,))
        con.commit()
    return cur.rowcount > 0


def update_store_brand(store_id: str, brand: dict) -> None:
    """Persist the brand brief generated by store_setup back to the store record."""
    with sqlite3.connect(_DB_PATH) as con:
        con.execute(
            "UPDATE stores SET store_brand = ?, niche = ? WHERE store_id = ?",
            (json.dumps(brand), brand.get("niche", ""), store_id),
        )
        con.commit()


def update_store_designed(store_id: str, designed: bool) -> None:
    """Persist whether the design loop has genuinely completed for this store.

    Previously this was never persisted at all — every run derived it as
    `bool(cached_brand)`, so any store with a saved brand brief was treated as
    permanently "designed" and the design loop silently never ran again,
    even on a store whose theme was never actually customized."""
    with sqlite3.connect(_DB_PATH) as con:
        con.execute(
            "UPDATE stores SET store_designed = ? WHERE store_id = ?",
            (int(designed), store_id),
        )
        con.commit()


_STOREFRONT_COLS = ("storefront_api_token", "oxygen_deploy_token", "storefront_slug", "theme_access_password")


def update_store_storefront(store_id: str, **fields) -> None:
    """Update any of the Hydrogen storefront columns (only the provided ones)."""
    updates = {k: v for k, v in fields.items() if k in _STOREFRONT_COLS and v is not None}
    if not updates:
        return
    set_clause = ", ".join(f"{col} = ?" for col in updates)
    params = list(updates.values()) + [store_id]
    with sqlite3.connect(_DB_PATH) as con:
        con.execute(f"UPDATE stores SET {set_clause} WHERE store_id = ?", params)
        con.commit()
