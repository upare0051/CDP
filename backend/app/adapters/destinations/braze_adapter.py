"""Braze destination adapter."""

from typing import List, Dict, Any, Optional
from datetime import date, datetime
from decimal import Decimal
import httpx
import time

from .base import DestinationAdapter, DestinationConfig, DestinationAdapterFactory, SyncResult, FieldMapping
from ...core.logging import get_logger

logger = get_logger(__name__)


class BrazeAdapter(DestinationAdapter):
    """
    Braze destination adapter.
    
    Braze API endpoints:
    - /users/track - Update user attributes and events
    - /users/identify - Identify users with external_id
    
    Rate limits:
    - 250,000 requests/hour for /users/track
    - 75 attributes per request
    
    Mock mode:
    - Set api_key to "mock" or "test" for local testing
    - Will simulate successful API calls without hitting Braze
    """
    
    # Standard Braze user attributes
    BRAZE_STANDARD_ATTRIBUTES = {
        "external_id", "email", "phone", "first_name", "last_name",
        "gender", "dob", "country", "home_city", "language",
        "email_subscribe", "push_subscribe", "time_zone",
    }
    
    # Braze API endpoints by region
    BRAZE_ENDPOINTS = {
        "US-01": "https://rest.iad-01.braze.com",
        "US-02": "https://rest.iad-02.braze.com",
        "US-03": "https://rest.iad-03.braze.com",
        "US-04": "https://rest.iad-04.braze.com",
        "US-05": "https://rest.iad-05.braze.com",
        "US-06": "https://rest.iad-06.braze.com",
        "US-07": "https://rest.iad-07.braze.com",
        "US-08": "https://rest.iad-08.braze.com",
        "EU-01": "https://rest.fra-01.braze.eu",
        "EU-02": "https://rest.fra-02.braze.eu",
    }
    
    def __init__(self, config: DestinationConfig):
        super().__init__(config)
        self.base_url = config.api_endpoint or self.BRAZE_ENDPOINTS.get("US-01")
        self.batch_size = min(config.batch_size, 75)  # Braze max is 75
        # Enable mock mode for local testing:
        # support exact markers and common demo key prefixes (e.g. "demo-api-key-12345").
        api_key_lower = (config.api_key or "").strip().lower()
        self.mock_mode = (
            api_key_lower in ("mock", "test", "demo", "local")
            or api_key_lower.startswith(("mock-", "test-", "demo-", "local-"))
        )
    
    def test_connection(self) -> tuple[bool, str]:
        """Test Braze API connection."""
        # Mock mode for local testing
        if self.mock_mode:
            logger.info("Braze mock mode enabled - simulating successful connection")
            return True, "Connected to Braze (MOCK MODE - for local testing)"
        
        try:
            # Use /users/export/ids with empty body to test auth
            # This endpoint validates API key without making changes
            with httpx.Client(timeout=30) as client:
                response = client.post(
                    f"{self.base_url}/users/export/ids",
                    headers={
                        "Authorization": f"Bearer {self.config.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={"external_ids": []},
                )
                
                if response.status_code == 401:
                    return False, "Invalid API key"
                elif response.status_code in (200, 201, 400):
                    # 400 is expected for empty request, but means auth worked
                    return True, "Connected to Braze successfully"
                else:
                    return False, f"Unexpected response: {response.status_code}"
        except Exception as e:
            return False, f"Connection failed: {str(e)}"
    
    def build_payload(
        self, 
        records: List[Dict[str, Any]], 
        field_mappings: List[FieldMapping],
        sync_key: str,
    ) -> Dict[str, Any]:
        """
        Build Braze /users/track payload.
        
        Payload format:
        {
            "attributes": [
                {
                    "external_id": "...",
                    "email": "...",
                    "custom_attribute": "...",
                    ...
                }
            ]
        }
        """
        attributes = []
        
        for record in records:
            user_attr = {}
            custom_attrs = {}
            
            # Apply field mappings
            for mapping in field_mappings:
                source_value = record.get(mapping.source_field)
                
                # Apply transformation
                if mapping.transformation and source_value is not None:
                    source_value = self._apply_transformation(source_value, mapping.transformation)
                
                dest_field = mapping.destination_field
                
                # Ensure value is JSON-safe before adding to payload.
                source_value = self._to_json_safe(source_value)

                # Check if standard or custom attribute
                if dest_field in self.BRAZE_STANDARD_ATTRIBUTES:
                    user_attr[dest_field] = source_value
                else:
                    custom_attrs[dest_field] = source_value
            
            # Ensure sync key is set
            if sync_key not in user_attr:
                sync_key_value = self.get_sync_key_value(record, field_mappings, sync_key)
                if sync_key_value:
                    user_attr[sync_key] = sync_key_value
            
            # Merge custom attributes
            user_attr.update(custom_attrs)
            
            # Only add if we have external_id
            if user_attr.get("external_id") or user_attr.get("email"):
                attributes.append(user_attr)
        
        return {"attributes": attributes}

    def _to_json_safe(self, value: Any) -> Any:
        """Convert values to JSON-serializable primitives for API payloads."""
        if value is None:
            return None
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, dict):
            return {str(k): self._to_json_safe(v) for k, v in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [self._to_json_safe(v) for v in value]
        return value
    
    def send_batch(self, payload: Dict[str, Any]) -> SyncResult:
        """Send batch to Braze /users/track endpoint."""
        attributes = payload.get("attributes", [])
        
        if not attributes:
            return SyncResult(success=True, records_sent=0)
        
        # Mock mode for local testing
        if self.mock_mode:
            logger.info(
                "Braze mock mode - simulating successful sync",
                records=len(attributes),
                sample_record=attributes[0] if attributes else None,
            )
            return SyncResult(
                success=True,
                records_sent=len(attributes),
                records_failed=0,
                response_data={"message": "MOCK MODE - records logged but not sent to Braze"},
            )
        
        try:
            with httpx.Client(timeout=60) as client:
                response = client.post(
                    f"{self.base_url}/users/track",
                    headers={
                        "Authorization": f"Bearer {self.config.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                
                response_data = response.json()
                
                if response.status_code in (200, 201):
                    # Success
                    errors_count = response_data.get("errors", [])
                    if isinstance(errors_count, list):
                        errors_count = len(errors_count)
                    
                    return SyncResult(
                        success=True,
                        records_sent=len(attributes) - errors_count,
                        records_failed=errors_count,
                        response_data=response_data,
                    )
                elif response.status_code == 429:
                    # Rate limited
                    return SyncResult(
                        success=False,
                        records_sent=0,
                        records_failed=len(attributes),
                        errors=[{"error": "Rate limited", "status": 429}],
                        response_data=response_data,
                    )
                else:
                    return SyncResult(
                        success=False,
                        records_sent=0,
                        records_failed=len(attributes),
                        errors=[{
                            "error": response_data.get("message", "Unknown error"),
                            "status": response.status_code,
                        }],
                        response_data=response_data,
                    )
        except Exception as e:
            logger.error("Braze API error", error=str(e))
            return SyncResult(
                success=False,
                records_sent=0,
                records_failed=len(attributes),
                errors=[{"error": str(e)}],
            )
    
    def get_braze_field_schema(self) -> Dict[str, Dict[str, Any]]:
        """Get Braze field schema for UI mapping."""
        return {
            "external_id": {"type": "string", "required": True, "description": "Unique user identifier"},
            "email": {"type": "string", "required": False, "description": "User email address"},
            "phone": {"type": "string", "required": False, "description": "User phone number"},
            "first_name": {"type": "string", "required": False, "description": "User first name"},
            "last_name": {"type": "string", "required": False, "description": "User last name"},
            "gender": {"type": "string", "required": False, "description": "M, F, O, N, P"},
            "dob": {"type": "date", "required": False, "description": "Date of birth (YYYY-MM-DD)"},
            "country": {"type": "string", "required": False, "description": "ISO 3166-1 alpha-2"},
            "home_city": {"type": "string", "required": False, "description": "User city"},
            "language": {"type": "string", "required": False, "description": "ISO 639-1"},
            "email_subscribe": {"type": "string", "required": False, "description": "opted_in, subscribed, unsubscribed"},
            "push_subscribe": {"type": "string", "required": False, "description": "opted_in, subscribed, unsubscribed"},
            "time_zone": {"type": "string", "required": False, "description": "IANA time zone"},
        }


# Register adapter
DestinationAdapterFactory.register("braze", BrazeAdapter)
