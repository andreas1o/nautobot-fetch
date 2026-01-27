"""
Base mapper class for Nautobot to NetBox object transformation.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
import logging

from ..lib.id_mapper import IDMapper

logger = logging.getLogger(__name__)


class BaseMapper(ABC):
    """Base class for object mappers."""

    # Object type identifier (used for ID mapping)
    object_type: str = 'base'

    def __init__(self, id_mapper: IDMapper, custom_field_mapping: Optional[Dict[str, str]] = None):
        self.id_mapper = id_mapper
        self.custom_field_mapping = custom_field_mapping or {}

    @abstractmethod
    def transform(self, nautobot_obj: Dict) -> Dict:
        """Transform a Nautobot object to NetBox format."""
        pass

    def transform_all(self, nautobot_objects: List[Dict]) -> List[Dict]:
        """Transform a list of Nautobot objects."""
        results = []
        for obj in nautobot_objects:
            try:
                transformed = self.transform(obj)
                if transformed:
                    results.append(transformed)
            except Exception as e:
                logger.error(f"Failed to transform {self.object_type} {obj.get('id', 'unknown')}: {e}")
        return results

    def _get_id(self, obj: Optional[Dict]) -> Optional[str]:
        """Extract ID from a Nautobot object reference."""
        if not obj:
            return None
        if isinstance(obj, dict):
            return obj.get('id')
        return str(obj)

    def _get_nested_id(self, obj: Optional[Dict], key: str) -> Optional[str]:
        """Extract nested object ID."""
        if not obj:
            return None
        nested = obj.get(key)
        return self._get_id(nested)

    def _resolve_id(self, obj_type: str, nautobot_id: Optional[str]) -> Optional[int]:
        """Resolve Nautobot UUID to NetBox ID."""
        if not nautobot_id:
            return None
        return self.id_mapper.get_netbox_id(obj_type, nautobot_id)

    def _resolve_nested_id(self, nautobot_obj: Dict, key: str, target_type: str) -> Optional[int]:
        """Resolve a nested object reference to NetBox ID."""
        nautobot_id = self._get_nested_id(nautobot_obj, key)
        return self._resolve_id(target_type, nautobot_id)

    def _transform_custom_fields(self, nautobot_obj: Dict) -> Dict:
        """Transform custom fields from Nautobot to NetBox format.

        Nautobot: custom_fields: {field_name: value, ...}
        NetBox: custom_fields: {field_name: value, ...}
        """
        cf_data = nautobot_obj.get('custom_fields', {})
        if not cf_data:
            return {}

        netbox_cf = {}
        for nb_field, value in cf_data.items():
            # Use mapping if provided, otherwise use same name
            netbox_field = self.custom_field_mapping.get(nb_field, nb_field)
            if value is not None:
                netbox_cf[netbox_field] = value

        return netbox_cf

    def _transform_tags(self, nautobot_obj: Dict) -> List[Dict]:
        """Transform tags from Nautobot to NetBox format.

        Returns list of tag slugs for NetBox.
        """
        tags = nautobot_obj.get('tags', [])
        if not tags:
            return []

        # Return tag slugs/names that can be resolved by NetBox
        return [{'slug': tag.get('slug', tag.get('name', '').lower().replace(' ', '-'))}
                for tag in tags if tag]

    def _get_slug(self, obj: Dict) -> str:
        """Generate or extract slug from object."""
        slug = obj.get('slug')
        if slug:
            return slug
        # Generate from name
        name = obj.get('name', '')
        return name.lower().replace(' ', '-').replace('_', '-')

    def _safe_get(self, obj: Dict, *keys, default=None):
        """Safely get nested dictionary values."""
        result = obj
        for key in keys:
            if isinstance(result, dict):
                result = result.get(key)
            else:
                return default
            if result is None:
                return default
        return result

    def register_mapping(self, nautobot_id: str, netbox_id: int):
        """Register ID mapping after successful creation."""
        self.id_mapper.add(self.object_type, nautobot_id, netbox_id)
