#!/usr/bin/env python3
"""
Import Kaggle Customer 360 Dataset into Alo ActivationOS

This script loads the rich customer dataset and populates:
- Customer profiles with demographics
- Customer attributes from various sources
- Customer events from clickstream, orders, and support tickets
- Aggregated metrics (LTV, order count, ticket count)
"""

import csv
import sys
import os
from datetime import datetime
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from sqlalchemy.orm import Session
from app.db import SessionLocal, engine, Base
from app.models.customer import CustomerProfile, CustomerAttribute, CustomerEvent


DATA_DIR = Path(__file__).parent.parent / "data"


def parse_date(date_str: str) -> datetime:
    """Parse various date formats."""
    if not date_str or date_str == "":
        return None
    
    formats = [
        "%Y-%m-%d",
        "%Y/%d/%m",
        "%Y/%m/%d",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%Y-%m-%d %H:%M:%S",
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    return None


def clean_name(name: str) -> str:
    """Clean and title-case names."""
    if not name:
        return ""
    # Remove extra spaces, title case
    return " ".join(name.strip().split()).title()


def load_customers(db: Session, limit: int = None):
    """Load customer profiles from CRM data."""
    print("\n📥 Loading customers...")
    
    csv_path = DATA_DIR / "crm_50000_customers_dirty_v3.csv"
    
    # First, clear existing data
    db.query(CustomerEvent).delete()
    db.query(CustomerAttribute).delete()
    db.query(CustomerProfile).delete()
    db.commit()
    print("  Cleared existing customer data")
    
    customers = {}
    seen_ids = set()
    count = 0
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            if limit and count >= limit:
                break
            
            customer_id = row['customer_id']
            
            # Skip duplicates
            if customer_id in seen_ids:
                continue
            seen_ids.add(customer_id)
            
            # Clean name fields
            first_name = clean_name(row.get('first_name', ''))
            last_name = clean_name(row.get('last_name', ''))
            
            # Parse dates
            dob = parse_date(row.get('dob', ''))
            signup_date = parse_date(row.get('signup_date', ''))
            
            # Create customer profile
            profile = CustomerProfile(
                external_id=customer_id,
                email=row.get('email', '').lower().strip(),
                phone=row.get('phone_number', '').strip(),
                first_name=first_name,
                last_name=last_name,
                source_count=1,
                first_seen_at=signup_date or datetime.now(),
                last_seen_at=datetime.now(),
                last_synced_at=datetime.now(),
            )
            
            db.add(profile)
            db.flush()
            
            # Store for later aggregation
            customers[customer_id] = profile.id
            
            # Add attributes
            attrs = [
                ("gender", row.get('gender', ''), "string"),
                ("dob", row.get('dob', ''), "date"),
                ("signup_date", row.get('signup_date', ''), "date"),
                ("address", row.get('address', ''), "string"),
                ("city", row.get('city', ''), "string"),
                ("state", row.get('state', ''), "string"),
                ("country", row.get('country', ''), "string"),
                ("acquisition_source", row.get('source', ''), "string"),
            ]
            
            for attr_name, attr_value, attr_type in attrs:
                if attr_value and attr_value.strip():
                    attr = CustomerAttribute(
                        customer_id=profile.id,
                        attribute_name=attr_name,
                        attribute_value=str(attr_value).strip(),
                        attribute_type=attr_type,
                        source_field=attr_name,
                    )
                    db.add(attr)
            
            count += 1
            if count % 5000 == 0:
                db.commit()
                print(f"  Loaded {count} customers...")
    
    db.commit()
    print(f"  ✅ Loaded {count} customers")
    return customers


def load_orders(db: Session, customers: dict, limit: int = None):
    """Load and aggregate order data."""
    print("\n📥 Loading orders...")
    
    csv_path = DATA_DIR / "orders_300k_dirty.csv"
    
    # Aggregate orders per customer
    customer_orders = {}
    count = 0
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            if limit and count >= limit:
                break
            
            customer_id = row['customer_id']
            if customer_id not in customers:
                continue
            
            profile_id = customers[customer_id]
            
            # Parse order amount (handle NaN and invalid values)
            try:
                amount = float(row.get('order_amount', 0))
                if amount != amount:  # Check for NaN
                    amount = 0.0
            except:
                amount = 0.0
            
            # Aggregate
            if profile_id not in customer_orders:
                customer_orders[profile_id] = {
                    'total_amount': 0,
                    'order_count': 0,
                    'first_order': None,
                    'last_order': None,
                }
            
            customer_orders[profile_id]['total_amount'] += amount
            customer_orders[profile_id]['order_count'] += 1
            
            order_date = parse_date(row.get('order_date', ''))
            if order_date:
                if not customer_orders[profile_id]['first_order'] or order_date < customer_orders[profile_id]['first_order']:
                    customer_orders[profile_id]['first_order'] = order_date
                if not customer_orders[profile_id]['last_order'] or order_date > customer_orders[profile_id]['last_order']:
                    customer_orders[profile_id]['last_order'] = order_date
            
            # Create event for recent orders only (last 10 per customer)
            if customer_orders[profile_id]['order_count'] <= 10:
                event = CustomerEvent(
                    customer_id=profile_id,
                    event_type="order",
                    event_category="transaction",
                    title=f"Order {row.get('status', 'completed')}",
                    description=f"Order for ${amount:.2f}",
                    event_data={
                        "order_id": row.get('order_id'),
                        "product_id": row.get('product_id'),
                        "amount": amount,
                        "payment_method": row.get('payment_method'),
                        "status": row.get('status'),
                        "quantity": row.get('quantity'),
                    },
                    occurred_at=order_date or datetime.now(),
                )
                db.add(event)
            
            count += 1
            if count % 50000 == 0:
                db.commit()
                print(f"  Processed {count} orders...")
    
    # Update customer profiles with aggregated order data as attributes
    print("  Adding LTV and order count attributes...")
    for profile_id, data in customer_orders.items():
        # Add LTV attribute
        attr = CustomerAttribute(
            customer_id=profile_id,
            attribute_name="lifetime_value",
            attribute_value=str(round(data['total_amount'], 2)),
            attribute_type="number",
            source_field="order_amount",
        )
        db.add(attr)
        
        attr2 = CustomerAttribute(
            customer_id=profile_id,
            attribute_name="total_orders",
            attribute_value=str(data['order_count']),
            attribute_type="number",
            source_field="order_count",
        )
        db.add(attr2)
    
    db.commit()
    print(f"  ✅ Processed {count} orders for {len(customer_orders)} customers")


def load_support_tickets(db: Session, customers: dict, limit: int = None):
    """Load support ticket data."""
    print("\n📥 Loading support tickets...")
    
    csv_path = DATA_DIR / "support_tickets_30000_dirty.csv"
    
    customer_tickets = {}
    count = 0
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            if limit and count >= limit:
                break
            
            customer_id = row['customer_id']
            if customer_id not in customers:
                continue
            
            profile_id = customers[customer_id]
            
            # Aggregate
            if profile_id not in customer_tickets:
                customer_tickets[profile_id] = {
                    'ticket_count': 0,
                    'sentiments': [],
                }
            
            customer_tickets[profile_id]['ticket_count'] += 1
            sentiment = row.get('sentiment', '')
            if sentiment:
                customer_tickets[profile_id]['sentiments'].append(sentiment)
            
            # Create event
            ticket_date = parse_date(row.get('ticket_created', ''))
            event = CustomerEvent(
                customer_id=profile_id,
                event_type="support_ticket",
                event_category="support",
                title=f"Support: {row.get('issue_type', 'Unknown')}",
                description=f"Sentiment: {sentiment}" if sentiment else None,
                event_data={
                    "ticket_id": row.get('ticket_id'),
                    "issue_type": row.get('issue_type'),
                    "sentiment": sentiment,
                    "resolution_time_hours": row.get('resolution_time_hours'),
                    "support_agent": row.get('support_agent'),
                },
                occurred_at=ticket_date or datetime.now(),
            )
            db.add(event)
            
            count += 1
            if count % 5000 == 0:
                db.commit()
                print(f"  Processed {count} tickets...")
    
    # Add ticket attributes
    from collections import Counter
    for profile_id, data in customer_tickets.items():
        attr = CustomerAttribute(
            customer_id=profile_id,
            attribute_name="support_ticket_count",
            attribute_value=str(data['ticket_count']),
            attribute_type="number",
            source_field="ticket_count",
        )
        db.add(attr)
        
        # Calculate dominant sentiment
        if data['sentiments']:
            most_common = Counter(data['sentiments']).most_common(1)[0][0]
            attr2 = CustomerAttribute(
                customer_id=profile_id,
                attribute_name="support_sentiment",
                attribute_value=most_common,
                attribute_type="string",
                source_field="sentiment",
            )
            db.add(attr2)
    
    db.commit()
    print(f"  ✅ Processed {count} tickets for {len(customer_tickets)} customers")


def load_clickstream(db: Session, customers: dict, limit: int = None):
    """Load clickstream events (sample only for performance)."""
    print("\n📥 Loading clickstream events (sampled)...")
    
    csv_path = DATA_DIR / "clickstream_500k_events.csv"
    
    # Only load limited events per customer for performance
    customer_events = {}
    max_events_per_customer = 5
    count = 0
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            if limit and count >= limit:
                break
            
            customer_id = row['customer_id']
            if customer_id not in customers:
                continue
            
            profile_id = customers[customer_id]
            
            # Limit events per customer
            if profile_id not in customer_events:
                customer_events[profile_id] = 0
            
            if customer_events[profile_id] >= max_events_per_customer:
                continue
            
            customer_events[profile_id] += 1
            
            event_time = parse_date(row.get('timestamp', ''))
            event = CustomerEvent(
                customer_id=profile_id,
                event_type="clickstream",
                event_category="web",
                title=row.get('event_type', 'page_view'),
                description=row.get('page_url', ''),
                event_data={
                    "event_id": row.get('event_id'),
                    "session_id": row.get('session_id'),
                    "page_url": row.get('page_url'),
                    "device_id": row.get('device_id'),
                },
                occurred_at=event_time or datetime.now(),
            )
            db.add(event)
            
            count += 1
            if count % 10000 == 0:
                db.commit()
                print(f"  Processed {count} events...")
    
    db.commit()
    print(f"  ✅ Loaded {count} clickstream events for {len(customer_events)} customers")


def main():
    """Main import function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Import Kaggle Customer 360 dataset")
    parser.add_argument("--customers", type=int, default=1000, 
                        help="Number of customers to import (default: 1000, use -1 for all)")
    parser.add_argument("--orders", type=int, default=50000,
                        help="Number of orders to process (default: 50000)")
    parser.add_argument("--tickets", type=int, default=10000,
                        help="Number of tickets to process (default: 10000)")
    parser.add_argument("--clickstream", type=int, default=20000,
                        help="Number of clickstream events (default: 20000)")
    
    args = parser.parse_args()
    
    customer_limit = None if args.customers == -1 else args.customers
    
    print("=" * 60)
    print("🚀 Alo ActivationOS - Kaggle Customer 360 Import")
    print("=" * 60)
    print(f"\nConfiguration:")
    print(f"  Customers: {customer_limit or 'ALL'}")
    print(f"  Orders: {args.orders}")
    print(f"  Tickets: {args.tickets}")
    print(f"  Clickstream: {args.clickstream}")
    
    # Create tables if needed
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    
    try:
        # Load data
        customers = load_customers(db, limit=customer_limit)
        load_orders(db, customers, limit=args.orders)
        load_support_tickets(db, customers, limit=args.tickets)
        load_clickstream(db, customers, limit=args.clickstream)
        
        # Final stats
        total_customers = db.query(CustomerProfile).count()
        total_attrs = db.query(CustomerAttribute).count()
        total_events = db.query(CustomerEvent).count()
        
        print("\n" + "=" * 60)
        print("✅ Import Complete!")
        print("=" * 60)
        print(f"\n📊 Final Statistics:")
        print(f"  Customer Profiles: {total_customers:,}")
        print(f"  Attributes: {total_attrs:,}")
        print(f"  Events: {total_events:,}")
        print(f"\n🌐 View at: http://localhost:5173/customers")
        
    finally:
        db.close()


if __name__ == "__main__":
    main()
