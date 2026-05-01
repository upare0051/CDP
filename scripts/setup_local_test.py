#!/usr/bin/env python3
"""
Setup script for local Braze sync testing.

This script creates:
1. A DuckDB source with sample customer data
2. A mock Braze destination (won't actually call Braze API)
3. A sync job with field mappings
4. Runs the sync to verify everything works

Usage:
    python scripts/setup_local_test.py
"""

import requests
import json
import sys

API_BASE = "http://localhost:8000/api/v1"


def main():
    print("=" * 60)
    print("Alo ActivationOS Local Test Setup")
    print("=" * 60)
    
    # Step 1: Create DuckDB Source
    print("\n1. Creating DuckDB source connection...")
    source_data = {
        "name": "Local Customer Data",
        "source_type": "duckdb",
        "duckdb_path": ":memory:"
    }
    
    response = requests.post(f"{API_BASE}/sources", json=source_data)
    if response.status_code == 201:
        source = response.json()
        print(f"   ✅ Created source: {source['name']} (ID: {source['id']})")
    elif response.status_code == 400 and "already exists" in response.text:
        # Get existing source
        sources = requests.get(f"{API_BASE}/sources").json()
        source = next((s for s in sources if s["name"] == source_data["name"]), None)
        if source:
            print(f"   ℹ️  Source already exists: {source['name']} (ID: {source['id']})")
        else:
            print(f"   ❌ Error: {response.text}")
            sys.exit(1)
    else:
        print(f"   ❌ Error: {response.text}")
        sys.exit(1)
    
    source_id = source["id"]
    
    # Step 2: Test source connection
    print("\n2. Testing source connection...")
    response = requests.post(f"{API_BASE}/sources/{source_id}/test")
    result = response.json()
    if result.get("success"):
        print(f"   ✅ {result['message']}")
    else:
        print(f"   ❌ {result['message']}")
    
    # Step 3: Create Mock Braze Destination
    print("\n3. Creating mock Braze destination...")
    dest_data = {
        "name": "Braze (Mock - Local Testing)",
        "destination_type": "braze",
        "api_key": "mock",  # Special key to enable mock mode
        "api_endpoint": "https://rest.iad-01.braze.com",
        "batch_size": 75
    }
    
    response = requests.post(f"{API_BASE}/destinations", json=dest_data)
    if response.status_code == 201:
        destination = response.json()
        print(f"   ✅ Created destination: {destination['name']} (ID: {destination['id']})")
    elif response.status_code == 400 and "already exists" in response.text:
        destinations = requests.get(f"{API_BASE}/destinations").json()
        destination = next((d for d in destinations if "Mock" in d["name"]), None)
        if destination:
            print(f"   ℹ️  Destination already exists: {destination['name']} (ID: {destination['id']})")
        else:
            print(f"   ❌ Error: {response.text}")
            sys.exit(1)
    else:
        print(f"   ❌ Error: {response.text}")
        sys.exit(1)
    
    dest_id = destination["id"]
    
    # Step 4: Test destination connection
    print("\n4. Testing destination connection...")
    response = requests.post(f"{API_BASE}/destinations/{dest_id}/test")
    result = response.json()
    if result.get("success"):
        print(f"   ✅ {result['message']}")
    else:
        print(f"   ⚠️  {result['message']} (expected for mock mode)")
    
    # Step 5: Create Sync Job
    print("\n5. Creating sync job with field mappings...")
    sync_data = {
        "name": "Customer to Braze Sync (Demo)",
        "description": "Demo sync job for local testing",
        "source_connection_id": source_id,
        "destination_connection_id": dest_id,
        "source_schema": "analytics",
        "source_table": "customers",
        "sync_mode": "full_refresh",
        "sync_key": "external_id",
        "schedule_type": "manual",
        "field_mappings": [
            {
                "source_field": "external_id",
                "destination_field": "external_id",
                "is_sync_key": True,
                "is_required": True
            },
            {
                "source_field": "email",
                "destination_field": "email",
                "is_sync_key": False,
                "is_required": False
            },
            {
                "source_field": "phone",
                "destination_field": "phone",
                "is_sync_key": False,
                "is_required": False
            },
            {
                "source_field": "first_name",
                "destination_field": "first_name",
                "is_sync_key": False,
                "is_required": False
            },
            {
                "source_field": "last_name",
                "destination_field": "last_name",
                "is_sync_key": False,
                "is_required": False
            },
            {
                "source_field": "city",
                "destination_field": "home_city",
                "is_sync_key": False,
                "is_required": False
            },
            {
                "source_field": "country",
                "destination_field": "country",
                "is_sync_key": False,
                "is_required": False
            },
            {
                "source_field": "lifetime_value",
                "destination_field": "ltv",
                "is_sync_key": False,
                "is_required": False
            },
            {
                "source_field": "is_subscribed",
                "destination_field": "email_subscribe",
                "transformation": "string",
                "is_sync_key": False,
                "is_required": False
            }
        ]
    }
    
    response = requests.post(f"{API_BASE}/syncs", json=sync_data)
    if response.status_code == 201:
        sync = response.json()
        print(f"   ✅ Created sync job: {sync['name']} (ID: {sync['id']})")
    elif response.status_code == 400 and "already exists" in response.text:
        syncs = requests.get(f"{API_BASE}/syncs").json()
        sync = next((s for s in syncs if "Demo" in s["name"]), None)
        if sync:
            print(f"   ℹ️  Sync job already exists: {sync['name']} (ID: {sync['id']})")
        else:
            print(f"   ❌ Error: {response.text}")
            sys.exit(1)
    else:
        print(f"   ❌ Error: {response.text}")
        sys.exit(1)
    
    sync_id = sync["id"]
    
    # Step 6: Run the sync
    print("\n6. Running sync job...")
    response = requests.post(f"{API_BASE}/syncs/{sync_id}/trigger")
    result = response.json()
    print(f"   Run ID: {result.get('run_id', 'N/A')}")
    print(f"   Status: {result.get('status', 'N/A')}")
    print(f"   Message: {result.get('message', 'N/A')}")
    
    # Step 7: Get run details
    if result.get("run_id"):
        print("\n7. Getting run details...")
        response = requests.get(f"{API_BASE}/runs/{result['run_id']}")
        if response.status_code == 200:
            run = response.json()
            print(f"   Rows Read: {run['rows_read']}")
            print(f"   Rows Synced: {run['rows_synced']}")
            print(f"   Rows Failed: {run['rows_failed']}")
            print(f"   Duration: {run.get('duration_seconds', 'N/A')}s")
            if run.get("error_message"):
                print(f"   Error: {run['error_message']}")
    
    print("\n" + "=" * 60)
    print("Setup Complete!")
    print("=" * 60)
    print("\nYou can now:")
    print("  - View the dashboard at http://localhost:5173")
    print("  - See the sync job at http://localhost:5173/syncs")
    print("  - View run history at http://localhost:5173/runs")
    print("  - Trigger more syncs via API or UI")
    print("\n")


if __name__ == "__main__":
    main()
