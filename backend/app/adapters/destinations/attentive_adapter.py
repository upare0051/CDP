"""Attentive destination adapter."""

from typing import List, Dict, Any, Optional
import httpx

from .base import DestinationAdapter, DestinationConfig, DestinationAdapterFactory, SyncResult, FieldMapping
from ...core.logging import get_logger

logger = get_logger(__name__)


class AttentiveAdapter(DestinationAdapter):
    """
    Attentive destination adapter.
    
    Attentive API:
    - /v1/subscribers - Create/update subscribers
    - /v1/me - Test API connection
    
    Key identifiers:
    - phone (required for SMS)
    - email (required for email)
    """
    
    DEFAULT_API_URL = "https://api.attentivemobile.com"
    
    # Standard Attentive subscriber fields
    ATTENTIVE_FIELDS = {
        "phone", "email", "externalId", "firstName", "lastName",
        "customAttributes", "source", "signUpSourceId",
    }
    
    def __init__(self, config: DestinationConfig):
        super().__init__(config)
        self.base_url = config.api_endpoint or self.DEFAULT_API_URL
        self.batch_size = min(config.batch_size, 100)  # Attentive max batch
    
    def test_connection(self) -> tuple[bool, str]:
        """Test Attentive API connection."""
        try:
            with httpx.Client(timeout=30) as client:
                response = client.get(
                    f"{self.base_url}/v1/me",
                    headers={
                        "Authorization": f"Bearer {self.config.api_key}",
                    },
                )
                
                if response.status_code == 200:
                    data = response.json()
                    company = data.get("company", {}).get("name", "Unknown")
                    return True, f"Connected to Attentive ({company})"
                elif response.status_code == 401:
                    return False, "Invalid API key"
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
        Build Attentive subscriber payload.
        
        Payload format for bulk:
        {
            "subscribers": [
                {
                    "phone": "+1234567890",
                    "email": "user@example.com",
                    "externalId": "...",
                    "customAttributes": {...}
                }
            ]
        }
        """
        subscribers = []
        
        for record in records:
            subscriber = {}
            custom_attrs = {}
            
            # Apply field mappings
            for mapping in field_mappings:
                source_value = record.get(mapping.source_field)
                
                # Apply transformation
                if mapping.transformation and source_value is not None:
                    source_value = self._apply_transformation(source_value, mapping.transformation)
                
                dest_field = mapping.destination_field
                
                # Standard vs custom attribute
                if dest_field in self.ATTENTIVE_FIELDS and dest_field != "customAttributes":
                    # Format phone number for Attentive
                    if dest_field == "phone" and source_value:
                        source_value = self._format_phone(source_value)
                    subscriber[dest_field] = source_value
                else:
                    custom_attrs[dest_field] = source_value
            
            # Add custom attributes
            if custom_attrs:
                subscriber["customAttributes"] = custom_attrs
            
            # Only add if we have phone or email
            if subscriber.get("phone") or subscriber.get("email"):
                subscribers.append(subscriber)
        
        return {"subscribers": subscribers}
    
    def _format_phone(self, phone: str) -> str:
        """Format phone number for Attentive (E.164 format)."""
        if not phone:
            return phone
        
        # Remove non-numeric characters
        digits = "".join(c for c in phone if c.isdigit())
        
        # Add country code if missing (assume US)
        if len(digits) == 10:
            digits = "1" + digits
        
        return f"+{digits}"
    
    def send_batch(self, payload: Dict[str, Any]) -> SyncResult:
        """Send batch to Attentive subscribers endpoint."""
        subscribers = payload.get("subscribers", [])
        
        if not subscribers:
            return SyncResult(success=True, records_sent=0)
        
        try:
            with httpx.Client(timeout=60) as client:
                # Attentive uses individual subscriber creates
                # For production, use bulk endpoint if available
                success_count = 0
                failed_count = 0
                errors = []
                
                for subscriber in subscribers:
                    response = client.post(
                        f"{self.base_url}/v1/subscribers",
                        headers={
                            "Authorization": f"Bearer {self.config.api_key}",
                            "Content-Type": "application/json",
                        },
                        json=subscriber,
                    )
                    
                    if response.status_code in (200, 201):
                        success_count += 1
                    elif response.status_code == 409:
                        # Conflict - subscriber exists, update instead
                        success_count += 1
                    else:
                        failed_count += 1
                        try:
                            error_data = response.json()
                            errors.append({
                                "subscriber": subscriber.get("email") or subscriber.get("phone"),
                                "error": error_data.get("message", "Unknown error"),
                                "status": response.status_code,
                            })
                        except Exception:
                            errors.append({
                                "subscriber": subscriber.get("email") or subscriber.get("phone"),
                                "error": f"HTTP {response.status_code}",
                            })
                
                return SyncResult(
                    success=failed_count == 0,
                    records_sent=success_count,
                    records_failed=failed_count,
                    errors=errors,
                )
        except Exception as e:
            logger.error("Attentive API error", error=str(e))
            return SyncResult(
                success=False,
                records_sent=0,
                records_failed=len(subscribers),
                errors=[{"error": str(e)}],
            )
    
    def get_attentive_field_schema(self) -> Dict[str, Dict[str, Any]]:
        """Get Attentive field schema for UI mapping."""
        return {
            "phone": {"type": "string", "required": True, "description": "Phone number (E.164 format)"},
            "email": {"type": "string", "required": False, "description": "Email address"},
            "externalId": {"type": "string", "required": False, "description": "External identifier"},
            "firstName": {"type": "string", "required": False, "description": "First name"},
            "lastName": {"type": "string", "required": False, "description": "Last name"},
            "source": {"type": "string", "required": False, "description": "Subscription source"},
        }


# Register adapter
DestinationAdapterFactory.register("attentive", AttentiveAdapter)
