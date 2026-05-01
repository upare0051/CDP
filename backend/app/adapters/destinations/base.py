"""Base destination adapter interface."""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

from ...core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class DestinationConfig:
    """Configuration for destination connection."""
    api_key: str
    api_endpoint: Optional[str] = None
    batch_size: int = 75
    rate_limit_per_second: int = 100
    extra_config: Optional[Dict[str, Any]] = None


@dataclass
class SyncResult:
    """Result of a sync batch operation."""
    success: bool
    records_sent: int = 0
    records_failed: int = 0
    records_skipped: int = 0
    errors: List[Dict[str, Any]] = field(default_factory=list)
    response_data: Optional[Dict[str, Any]] = None


@dataclass
class FieldMapping:
    """Mapping from source to destination field."""
    source_field: str
    destination_field: str
    transformation: Optional[str] = None
    is_sync_key: bool = False


class DestinationAdapter(ABC):
    """Abstract base class for destination adapters (Braze, Attentive)."""
    
    def __init__(self, config: DestinationConfig):
        self.config = config
    
    @abstractmethod
    def test_connection(self) -> tuple[bool, str]:
        """Test the API connection. Returns (success, message)."""
        pass
    
    @abstractmethod
    def build_payload(
        self, 
        records: List[Dict[str, Any]], 
        field_mappings: List[FieldMapping],
        sync_key: str,
    ) -> Dict[str, Any]:
        """Build destination-specific API payload from records."""
        pass
    
    @abstractmethod
    def send_batch(
        self, 
        payload: Dict[str, Any],
    ) -> SyncResult:
        """Send a batch of records to the destination."""
        pass
    
    def sync_records(
        self,
        records: List[Dict[str, Any]],
        field_mappings: List[FieldMapping],
        sync_key: str,
    ) -> SyncResult:
        """Sync records to the destination."""
        if not records:
            return SyncResult(success=True, records_sent=0)
        
        # Build payload
        payload = self.build_payload(records, field_mappings, sync_key)
        
        # Send batch
        result = self.send_batch(payload)
        
        return result
    
    def apply_field_mapping(
        self, 
        record: Dict[str, Any], 
        field_mappings: List[FieldMapping]
    ) -> Dict[str, Any]:
        """Apply field mappings to transform a source record."""
        mapped = {}
        
        for mapping in field_mappings:
            value = record.get(mapping.source_field)
            
            # Apply transformation if specified
            if mapping.transformation and value is not None:
                value = self._apply_transformation(value, mapping.transformation)
            
            mapped[mapping.destination_field] = value
        
        return mapped
    
    def _apply_transformation(self, value: Any, transformation: str) -> Any:
        """Apply a transformation to a value."""
        transform_lower = transformation.lower()
        
        if transform_lower == "upper" and isinstance(value, str):
            return value.upper()
        elif transform_lower == "lower" and isinstance(value, str):
            return value.lower()
        elif transform_lower == "trim" and isinstance(value, str):
            return value.strip()
        elif transform_lower == "string":
            return str(value) if value is not None else None
        elif transform_lower == "integer":
            return int(value) if value is not None else None
        elif transform_lower == "float":
            return float(value) if value is not None else None
        elif transform_lower == "boolean":
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                return value.lower() in ("true", "1", "yes")
            return bool(value) if value is not None else None
        
        return value
    
    def get_sync_key_value(
        self, 
        record: Dict[str, Any], 
        field_mappings: List[FieldMapping],
        sync_key: str,
    ) -> Optional[str]:
        """Get the sync key value from a record."""
        for mapping in field_mappings:
            if mapping.is_sync_key or mapping.destination_field == sync_key:
                value = record.get(mapping.source_field)
                return str(value) if value is not None else None
        return None


class DestinationAdapterFactory:
    """Factory for creating destination adapters."""
    
    _adapters: Dict[str, type] = {}
    
    @classmethod
    def register(cls, destination_type: str, adapter_class: type):
        """Register an adapter class for a destination type."""
        cls._adapters[destination_type] = adapter_class
    
    @classmethod
    def create(cls, destination_type: str, config: DestinationConfig) -> DestinationAdapter:
        """Create an adapter instance."""
        if destination_type not in cls._adapters:
            raise ValueError(f"Unknown destination type: {destination_type}")
        return cls._adapters[destination_type](config)
    
    @classmethod
    def get_available_types(cls) -> List[str]:
        """Get list of registered destination types."""
        return list(cls._adapters.keys())
