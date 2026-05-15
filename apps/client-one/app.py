"""
Client One v2 - Clienteling Intelligence Platform
Flask app that serves the CLIENT ONE UI and proxies customer_360 Cube queries.
"""

import os
import re
from datetime import datetime
from decimal import Decimal
from typing import Any

import redshift_connector
import requests
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")
CUBE_LOAD_URL = f"{BACKEND_URL}/api/v1/cube/load"

# Redshift direct connection (for purchase history not available in Cube)
RS_HOST     = os.environ.get("REDSHIFT_HOST",     "localhost")
RS_PORT     = int(os.environ.get("REDSHIFT_PORT", "10005"))
RS_DATABASE = os.environ.get("REDSHIFT_DATABASE", "dev")
RS_USER     = os.environ.get("REDSHIFT_USER",     "utkarsh.parekh")
RS_PASSWORD = os.environ.get("REDSHIFT_PASSWORD", "password")


def _rs_connect():
    return redshift_connector.connect(
        host=RS_HOST, port=RS_PORT, database=RS_DATABASE,
        user=RS_USER, password=RS_PASSWORD, ssl=False, timeout=30,
    )

# Dimensions to fetch for customer search results (lightweight)
SEARCH_DIMENSIONS = [
    "customer_360.customer_id",
    "customer_360.first_name",
    "customer_360.last_name",
    "customer_360.email",
    "customer_360.phone",
    "customer_360.loyalty_tier_name",
    "customer_360.days_since_last_order",
    "customer_360.total_revenue_l3y",
    "customer_360.city",
    "customer_360.country_code",
]

# Dimensions to fetch for full customer profile
PROFILE_DIMENSIONS = [
    # identity
    "customer_360.customer_id",
    "customer_360.first_name",
    "customer_360.last_name",
    "customer_360.birthdate",
    # contact
    "customer_360.email",
    "customer_360.phone",
    # address
    "customer_360.city",
    "customer_360.state",
    "customer_360.country_code",
    "customer_360.zip_code",
    # loyalty
    "customer_360.loyalty_enrolled",
    "customer_360.loyalty_tier_name",
    "customer_360.membership_expires_at",
    # contact prefs (dimensions only — reachable counts are measures, fetched separately)
    "customer_360.email_subscribed",
    "customer_360.sms_subscribed",
    "customer_360.push_enabled",
    "customer_360.preferred_comm_channel",
    "customer_360.total_channels_subscribed",
    # geo
    "customer_360.digital_geo_segment",
    "customer_360.omni_geo_segment",
    "customer_360.domestic_international_customer",
    # RFM (pre-computed snapshot)
    "customer_360.first_order_date",
    "customer_360.last_order_date",
    "customer_360.days_since_last_order",
    "customer_360.orders_last_52_weeks",
    "customer_360.revenue_last_52_weeks",
    "customer_360.total_orders_l3y",
    "customer_360.total_revenue_l3y",
]

# Measures (fetched in a separate query to avoid JOIN fan-out with dimension query)
PROFILE_MEASURES = [
    "customer_360.total_revenue_l3y_sum",
    "customer_360.revenue_last_52_weeks_sum",
    "customer_360.order_line_fact_order_count",
    "customer_360.order_line_fact_line_revenue_sum",
    "customer_360.order_line_fact_qty_sum",
    "customer_360.email_reachable_count",
    "customer_360.sms_reachable_count",
    "customer_360.push_reachable_count",
]


def _cube_load(query: dict[str, Any]) -> list[dict]:
    """Execute a Cube query via the backend proxy. Returns list of row dicts."""
    try:
        resp = requests.post(CUBE_LOAD_URL, json={"query": query}, timeout=30)
        resp.raise_for_status()
        return resp.json().get("data", [])
    except requests.RequestException as exc:
        app.logger.error("Cube query failed: %s", exc)
        raise


def _normalize_key(key: str) -> str:
    """Strip cube view prefix from a dotted key: 'customer_360.first_name' → 'first_name'."""
    return key.split(".")[-1]


def _flatten_row(row: dict) -> dict:
    """Convert Cube's dotted keys to plain keys."""
    return {_normalize_key(k): v for k, v in row.items()}


_TIER_LABELS = {
    "tier1": "Silver",
    "tier2": "Gold",
    "tier3": "Platinum",
    "tier4": "Obsidian",
    "tier5": "Diamond",
    "tier6": "VIC",
}


def _fmt_tier(raw: str | None) -> str:
    """Map raw tier keys (tier1…tier6) to display names, or title-case the raw value."""
    if not raw:
        return ""
    return _TIER_LABELS.get(raw.lower(), raw.replace("_", " ").title())


def _phone_digits(raw: str) -> str:
    """Extract digits only from a phone string for loose matching."""
    return re.sub(r"\D", "", raw or "")


def _is_phone_query(q: str) -> bool:
    digits = _phone_digits(q)
    return len(digits) >= 7


def _is_email_query(q: str) -> bool:
    return "@" in q


@app.route("/")
def index():
    return render_template("index.html", backend_url=BACKEND_URL)


@app.route("/api/customers/search")
def search_customers():
    """Search customer_360 by name, email, or phone."""
    q = (request.args.get("q") or "").strip()
    if len(q) < 2:
        return jsonify({"customers": []})

    filters: list[dict] = []

    if _is_email_query(q):
        filters.append({
            "member": "customer_360.email_norm",
            "operator": "contains",
            "values": [q.lower()],
        })
    elif _is_phone_query(q):
        digits = _phone_digits(q)
        filters.append({
            "member": "customer_360.phone_norm",
            "operator": "contains",
            "values": [digits],
        })
    else:
        parts = q.split()
        if len(parts) >= 2:
            # Full name query (e.g. "Debra Silverman") — AND first+last for precision
            filters.append({
                "member": "customer_360.first_name",
                "operator": "contains",
                "values": [parts[0]],
            })
            filters.append({
                "member": "customer_360.last_name",
                "operator": "contains",
                "values": [parts[-1]],
            })
        else:
            # Single token — search first OR last name
            filters.append({
                "or": [
                    {
                        "member": "customer_360.first_name",
                        "operator": "contains",
                        "values": [q],
                    },
                    {
                        "member": "customer_360.last_name",
                        "operator": "contains",
                        "values": [q],
                    },
                ]
            })

    query = {
        "dimensions": SEARCH_DIMENSIONS,
        "filters": filters,
        "limit": 10,
        "order": {"customer_360.total_revenue_l3y": "desc"},
    }

    try:
        rows = _cube_load(query)
    except Exception:
        return jsonify({"error": "Cube unavailable"}), 503

    customers = [_flatten_row(r) for r in rows]
    # Redshift DESC puts NULLs first — re-sort so non-zero LTV leads
    customers.sort(key=lambda c: _safe_float(c.get("total_revenue_l3y")) or 0.0, reverse=True)
    return jsonify({"customers": customers})


@app.route("/api/customers/<customer_id>")
def get_customer(customer_id: str):
    """Fetch full customer_360 profile for a given customer_id."""
    id_filter = [{"member": "customer_360.customer_id", "operator": "equals", "values": [customer_id]}]

    # Query 1: dimensions only — never returns 0 rows due to missing order_line_fact join
    try:
        rows = _cube_load({"dimensions": PROFILE_DIMENSIONS, "filters": id_filter, "limit": 1})
    except Exception:
        return jsonify({"error": "Cube unavailable"}), 503

    if not rows:
        return jsonify({"error": "Customer not found"}), 404

    customer = _flatten_row(rows[0])

    # Query 2: measures only — separate query so missing order data doesn't kill the profile
    try:
        mrows = _cube_load({"measures": PROFILE_MEASURES, "filters": id_filter, "limit": 1})
        if mrows:
            customer.update(_flatten_row(mrows[0]))
    except Exception:
        app.logger.warning("Measures query failed for customer %s — continuing without", customer_id)

    customer["loyalty_tier_display"] = _fmt_tier(customer.get("loyalty_tier_name"))
    customer["_intel"] = _generate_intel(customer)
    return jsonify(customer)


@app.route("/api/customers/lookup/phone")
def lookup_by_phone():
    """Look up a customer by phone number."""
    phone = (request.args.get("phone") or "").strip()
    if not phone:
        return jsonify({"customers": []})

    digits = _phone_digits(phone)
    if len(digits) < 7:
        return jsonify({"customers": []})

    query = {
        "dimensions": SEARCH_DIMENSIONS,
        "filters": [
            {
                "member": "customer_360.phone_norm",
                "operator": "contains",
                "values": [digits],
            }
        ],
        "limit": 5,
        "order": {"customer_360.total_revenue_l3y": "desc"},
    }

    try:
        rows = _cube_load(query)
    except Exception:
        return jsonify({"error": "Cube unavailable"}), 503

    customers = [_flatten_row(r) for r in rows]
    return jsonify({"customers": customers})


# Country code → flag emoji
_FLAG = {
    "US": "🇺🇸", "GB": "🇬🇧", "CA": "🇨🇦", "AU": "🇦🇺", "FR": "🇫🇷",
    "DE": "🇩🇪", "JP": "🇯🇵", "KR": "🇰🇷", "CN": "🇨🇳", "MX": "🇲🇽",
    "BR": "🇧🇷", "IN": "🇮🇳", "SG": "🇸🇬", "AE": "🇦🇪", "SA": "🇸🇦",
    "IT": "🇮🇹", "ES": "🇪🇸", "NL": "🇳🇱", "CH": "🇨🇭", "HK": "🇭🇰",
    "TW": "🇹🇼", "TH": "🇹🇭", "MY": "🇲🇾", "NZ": "🇳🇿", "SE": "🇸🇪",
}


def _flag(code: str | None) -> str:
    return _FLAG.get((code or "").upper(), "🌐")


def _channel_label(raw: str | None) -> str:
    """Normalize digital_vs_retail to DIGITAL or RETAIL."""
    v = (raw or "").lower()
    if "retail" in v:
        return "retail"
    return "digital"


@app.route("/api/customers/<customer_id>/purchases")
def get_purchases(customer_id: str):
    """Fetch order line item history for a customer from Redshift gold table."""
    try:
        conn = _rs_connect()
        cur = conn.cursor()
        cur.execute("""
            SELECT
                order_date,
                order_id,
                order_name,
                product_title,
                color,
                variant_title,
                product_size,
                digital_vs_retail,
                destination_country_code,
                store_name,
                destination_city,
                gross_sales_usd,
                order_quantity,
                product_category,
                subcategory,
                is_sfs_order
            FROM gold.gold_omni_order_line_item_detail
            WHERE customer_id = %s
            ORDER BY order_date DESC, order_id DESC
            LIMIT 100
        """, (int(customer_id),))
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
        conn.close()
    except Exception as exc:
        app.logger.error("Redshift purchases query failed: %s", exc)
        return jsonify({"error": "Purchase history unavailable"}), 503

    items = []
    order_ids: set = set()
    countries: set = set()
    channels: set = set()

    for row in rows:
        r = dict(zip(cols, row))
        oid = r["order_id"]
        order_ids.add(oid)

        cc = (r["destination_country_code"] or "").upper()
        if cc:
            countries.add(cc)

        ch = _channel_label(r["digital_vs_retail"])
        channels.add(ch)

        # Build display label: "Product Name — Color" (strip color already embedded in title)
        color = r["color"] or ""
        if color.lower() in ("no color", "no colour", ""):
            color = ""
        title = r["product_title"] or ""
        # Strip " - Color" suffix from title if it already contains the color
        if color and title.lower().endswith(f" - {color.lower()}"):
            title = title[: -(len(color) + 3)].rstrip()
        display_name = f"{title} — {color}" if color else title

        # Location: store name for retail, destination city for digital
        if ch == "retail":
            location = r["store_name"] or r["destination_city"] or ""
        else:
            location = r["destination_city"] or ""

        items.append({
            "order_date":    r["order_date"].isoformat() if r["order_date"] else None,
            "order_name":    r["order_name"],
            "product_title": display_name,
            "variant":       r["variant_title"] or "",
            "channel":       ch,
            "country_code":  cc,
            "flag":          _flag(cc),
            "location":      location,
            "price":         float(r["gross_sales_usd"]) if r["gross_sales_usd"] is not None else None,
            "qty":           r["order_quantity"],
            "category":      r["subcategory"] or r["product_category"] or "",
        })

    return jsonify({
        "purchases": items,
        "summary": {
            "total_orders":   len(order_ids),
            "total_countries": len(countries),
            "total_channels":  len(channels),
        },
    })



def _generate_intel(c: dict) -> dict:
    """Generate SA Intel (conversation starters, signals, dos/don'ts) from customer data."""
    starters = []
    signals = []
    dos = []
    donts = []

    days_since = _safe_int(c.get("days_since_last_order"))
    tier = _fmt_tier(c.get("loyalty_tier_name"))
    preferred_channel = c.get("preferred_comm_channel") or ""
    if preferred_channel.lower() == "none":
        preferred_channel = ""
    # Use pre-computed RFM fields; fall back to rfm measures, then live order_line_fact measures
    total_rev  = (_safe_float(c.get("total_revenue_l3y"))
                  or _safe_float(c.get("total_revenue_l3y_sum"))
                  or _safe_float(c.get("order_line_fact_line_revenue_sum")))
    orders_52w = (_safe_int(c.get("orders_last_52_weeks"))
                  or _safe_int(c.get("order_line_fact_order_count")))
    rev_52w = _safe_float(c.get("revenue_last_52_weeks"))
    city = c.get("city") or ""
    country = c.get("country_code") or ""
    domestic = c.get("domestic_international_customer") or ""
    omni_seg = c.get("omni_geo_segment") or ""
    digital_seg = c.get("digital_geo_segment") or ""

    # Birthdate proximity
    birthdate_str = c.get("birthdate")
    if birthdate_str:
        try:
            bd = datetime.strptime(str(birthdate_str)[:10], "%Y-%m-%d")
            today = datetime.today()
            this_year_bd = bd.replace(year=today.year)
            if this_year_bd < today:
                this_year_bd = bd.replace(year=today.year + 1)
            days_to_bd = (this_year_bd - today).days
            if days_to_bd <= 30:
                starters.append({
                    "icon": "🎂",
                    "text": f"Birthday is in <strong>{days_to_bd} days</strong> ({this_year_bd.strftime('%b %d')}). Mention birthday perks or offer a personal shopping appointment.",
                })
                dos.append("Mention upcoming birthday and available perks")
        except (ValueError, TypeError):
            pass

    # Lapsed visit signal
    if days_since and days_since > 60:
        starters.append({
            "icon": "⏰",
            "text": f"Client hasn't purchased in <strong>{days_since} days</strong>. This is a great moment for a warm outreach — check if they saw any recent new arrivals.",
        })
        signals.append({"color": "var(--red)", "text": f"<strong>Lapsed</strong> — {days_since} days since last order (consider outreach)"})
    elif days_since and days_since <= 14:
        signals.append({"color": "var(--green)", "text": f"<strong>Recent buyer</strong> — ordered just {days_since} days ago"})

    # Tier-specific signals (works with both raw "tier4" and mapped "Obsidian")
    tier_lower = tier.lower()
    raw_tier = (c.get("loyalty_tier_name") or "").lower()
    is_top = tier_lower in ("obsidian", "diamond", "vic") or raw_tier in ("tier4", "tier5", "tier6")
    is_mid = tier_lower in ("gold", "platinum") or raw_tier in ("tier2", "tier3")
    if is_top:
        signals.append({"color": "var(--gold)", "text": f"<strong>Top tier</strong> — {tier} member, handle with white-glove service"})
        dos.append("Greet by name immediately and offer dedicated attention")
        donts.append("Keep waiting or treat as a walk-in — this is a VIC")
    elif is_mid:
        signals.append({"color": "var(--purple)", "text": f"<strong>{tier} member</strong> — loyalty rewards eligible"})
        dos.append("Remind them of their current points balance and rewards")

    # Channel preference
    if preferred_channel:
        starters.append({
            "icon": "💬",
            "text": f"Preferred communication channel is <strong>{preferred_channel}</strong>. Use this for post-visit follow-up.",
        })
        dos.append(f"Follow up via {preferred_channel} after the visit")

    # International customer
    if domestic.lower() == "international" or (country and country not in ("US", "USA")):
        starters.append({
            "icon": "✈️",
            "text": f"International shopper from <strong>{city or country}</strong>. Ask about their travel and mention cross-border loyalty benefits.",
        })
        signals.append({"color": "var(--blue)", "text": "<strong>International customer</strong> — eligible for cross-border loyalty"})

    # Revenue trend
    if total_rev and rev_52w:
        pct_recent = rev_52w / total_rev * 100 if total_rev else 0
        if pct_recent > 50:
            signals.append({"color": "var(--green)", "text": f"<strong>Trending up</strong> — {pct_recent:.0f}% of lifetime spend in the last 52 weeks"})

    # Orders per year
    if orders_52w and orders_52w >= 5:
        signals.append({"color": "var(--purple)", "text": f"<strong>Frequent buyer</strong> — {orders_52w} orders in the last 52 weeks"})
    elif orders_52w and orders_52w <= 1:
        signals.append({"color": "var(--gold)", "text": "<strong>Occasional shopper</strong> — focus on deepening the relationship"})
        donts.append("Push for immediate upsell — focus on building trust first")

    # Geo segment insight
    if digital_seg:
        starters.append({
            "icon": "🌐",
            "text": f"Digital segment: <strong>{digital_seg}</strong>. Reference online browsing behavior if relevant.",
        })

    # Default dos/donts if sparse
    if not dos:
        dos.append("Greet by name and ask about their current needs")
    if not donts:
        donts.append("Make assumptions about size or style without asking")

    return {
        "starters": starters[:3],
        "signals": signals[:5],
        "dos": dos[:4],
        "donts": donts[:4],
    }


def _safe_int(v) -> int | None:
    try:
        return int(float(v)) if v is not None else None
    except (TypeError, ValueError):
        return None


def _safe_float(v) -> float | None:
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
