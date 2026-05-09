#!/usr/bin/env python3
"""Emit backend/app/data/c360_upstream_customer_unified_attr.json from dbt manifest.json.

Reads transitive parents of model.<project>.customer_unified_attr, keeps only
model.* and snapshot.* nodes (excludes sources/seeds). Drops relations whose
**alias** starts with ``br_rs_`` (REST Shopify bronze — excluded from this view).

Usage::
    python scripts/generate_c360_model_health_upstream.py \\
        --manifest /path/to/alo-data-stack/is-redshift/warehouse/target/manifest.json

Default manifest path tries ALO_DBT_MANIFEST env, then common local path.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


DEFAULT_MANIFEST = Path(
    "/Users/utkarsh.parekh/alo-data-stack/is-redshift/warehouse/target/manifest.json"
)
OUT = Path(__file__).resolve().parents[1] / "backend" / "app" / "data" / "c360_upstream_customer_unified_attr.json"
ROOT_SUFFIX = "customer_unified_attr"


def _ancestors(parent_map: dict, root: str) -> set[str]:
    seen: set[str] = set()
    stack = list(parent_map.get(root, []))
    while stack:
        nid = stack.pop()
        if nid in seen:
            continue
        seen.add(nid)
        stack.extend(parent_map.get(nid, []))
    return seen


def _pick_root_id(parent_map: dict, nodes: dict) -> str:
    candidates = [k for k in nodes if k.startswith("model.") and k.endswith(ROOT_SUFFIX)]
    if len(candidates) == 1:
        return candidates[0]
    if candidates:
        return sorted(candidates)[0]
    raise SystemExit("Could not find model.*.customer_unified_attr in manifest nodes")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--manifest",
        type=Path,
        default=Path(os.environ.get("ALO_DBT_MANIFEST", str(DEFAULT_MANIFEST))),
    )
    ap.add_argument("-o", "--out", type=Path, default=OUT)
    args = ap.parse_args()
    if not args.manifest.exists():
        raise SystemExit(f"Manifest not found: {args.manifest}")

    with open(args.manifest, encoding="utf-8") as f:
        m = json.load(f)

    nodes = m.get("nodes") or {}
    parent_map = m.get("parent_map") or {}
    root = _pick_root_id(parent_map, nodes)
    anc = _ancestors(parent_map, root)

    items = []
    for nid in sorted(anc):
        if not (nid.startswith("model.") or nid.startswith("snapshot.")):
            continue
        node = nodes.get(nid)
        if not node:
            continue
        alias = (node.get("alias") or node.get("name") or "").strip()
        if alias.lower().startswith("br_rs_"):
            continue
        items.append(
            {
                "unique_id": nid,
                "resource_type": nid.split(".", 1)[0],
                "name": node.get("name"),
                "schema": (node.get("schema") or "").lower(),
                "alias": node.get("alias"),
                "relation_name": node.get("relation_name"),
            }
        )

    payload = {
        "root_model_id": root,
        "manifest_path": str(args.manifest.resolve()),
        "upstream_model_count": len(items),
        "items": items,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")
    print(f"Wrote {args.out} ({len(items)} models/snapshots)")


if __name__ == "__main__":
    main()
