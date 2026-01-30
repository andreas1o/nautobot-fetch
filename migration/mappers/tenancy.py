"""
Tenancy object mappers for Nautobot to NetBox migration.
"""

from typing import Dict, List, Any, Optional
import logging

from .base import BaseMapper

logger = logging.getLogger(__name__)


class TenantGroupMapper(BaseMapper):
    """Mapper for tenant groups."""

    object_type = 'tenant_group'

    def transform(self, nautobot_obj: Dict) -> Dict:
        """Transform a Nautobot tenant group to NetBox format."""
        data = {
            'name': nautobot_obj.get('name'),
            'slug': self._get_slug(nautobot_obj),
            'description': nautobot_obj.get('description', '') or '',
        }

        # Parent group
        parent_id = self._resolve_nested_id(nautobot_obj, 'parent', 'tenant_group')
        if parent_id:
            data['parent'] = parent_id

        return data


class TenantMapper(BaseMapper):
    """Mapper for tenants."""

    object_type = 'tenant'
    content_type = 'tenancy.tenant'

    def transform(self, nautobot_obj: Dict) -> Dict:
        """Transform a Nautobot tenant to NetBox format."""
        data = {
            'name': nautobot_obj.get('name'),
            'slug': self._get_slug(nautobot_obj),
            'description': nautobot_obj.get('description', '') or '',
        }

        # Tenant group
        group_id = self._resolve_nested_id(nautobot_obj, 'group', 'tenant_group')
        if group_id:
            data['group'] = group_id

        # Comments
        if nautobot_obj.get('comments'):
            data['comments'] = nautobot_obj['comments']

        # Custom fields
        custom_fields = self._transform_custom_fields(nautobot_obj)
        if custom_fields:
            data['custom_fields'] = custom_fields

        # Tags
        tags = self._transform_tags(nautobot_obj)
        if tags:
            data['tags'] = tags

        return data
