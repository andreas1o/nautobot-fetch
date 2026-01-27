"""
Extras object mappers for Nautobot to NetBox migration.
"""

from typing import Dict, List, Any, Optional
import logging

from .base import BaseMapper

logger = logging.getLogger(__name__)


class CustomFieldMapper(BaseMapper):
    """Mapper for custom fields.

    Custom field types in both systems:
    - text: Single-line text
    - longtext: Multi-line text (NetBox: text with larger widget)
    - integer: Integer number
    - decimal: Decimal number (NetBox 4.x)
    - boolean: True/False
    - date: Date value
    - datetime: Date and time (NetBox 4.x)
    - url: URL
    - json: JSON data (NetBox 4.x)
    - select: Single selection from choices
    - multiselect: Multiple selections (NetBox: multi-select)
    - object: Foreign key reference (NetBox 4.x)
    - multiobject: Multiple foreign keys (NetBox 4.x)
    """

    object_type = 'custom_field'

    # Map Nautobot custom field types to NetBox
    TYPE_MAP = {
        'text': 'text',
        'longtext': 'longtext',
        'integer': 'integer',
        'boolean': 'boolean',
        'date': 'date',
        'url': 'url',
        'select': 'select',
        'multi-select': 'multiselect',
        'json': 'json',
    }

    # Map Nautobot content types to NetBox
    CONTENT_TYPE_MAP = {
        'dcim.device': 'dcim.device',
        'dcim.interface': 'dcim.interface',
        'dcim.site': 'dcim.site',
        'dcim.rack': 'dcim.rack',
        'dcim.devicetype': 'dcim.devicetype',
        'ipam.vlan': 'ipam.vlan',
        'ipam.vrf': 'ipam.vrf',
        'ipam.prefix': 'ipam.prefix',
        'ipam.ipaddress': 'ipam.ipaddress',
        'tenancy.tenant': 'tenancy.tenant',
        'virtualization.virtualmachine': 'virtualization.virtualmachine',
        'virtualization.vminterface': 'virtualization.vminterface',
        'circuits.circuit': 'circuits.circuit',
    }

    def transform(self, nautobot_obj: Dict) -> Dict:
        """Transform a Nautobot custom field to NetBox format."""
        # Get type
        cf_type = nautobot_obj.get('type', 'text')
        if isinstance(cf_type, dict):
            cf_type = cf_type.get('value', 'text')
        netbox_type = self.TYPE_MAP.get(cf_type, 'text')

        data = {
            'name': nautobot_obj.get('name'),
            'type': netbox_type,
            'label': nautobot_obj.get('label', nautobot_obj.get('name')),
            'description': nautobot_obj.get('description', '') or '',
            'required': nautobot_obj.get('required', False),
        }

        # Content types (object types this field applies to)
        content_types = nautobot_obj.get('content_types', [])
        if content_types:
            netbox_content_types = []
            for ct in content_types:
                if isinstance(ct, str):
                    mapped = self.CONTENT_TYPE_MAP.get(ct)
                    if mapped:
                        netbox_content_types.append(mapped)
                elif isinstance(ct, dict):
                    # Handle nested format
                    app_label = ct.get('app_label', '')
                    model = ct.get('model', '')
                    ct_string = f"{app_label}.{model}"
                    mapped = self.CONTENT_TYPE_MAP.get(ct_string)
                    if mapped:
                        netbox_content_types.append(mapped)
            if netbox_content_types:
                data['object_types'] = netbox_content_types

        # Filter logic (display conditions)
        if nautobot_obj.get('filter_logic'):
            filter_logic = nautobot_obj['filter_logic']
            if isinstance(filter_logic, dict):
                data['filter_logic'] = filter_logic.get('value', 'loose')
            else:
                data['filter_logic'] = filter_logic

        # Weight (display order)
        if nautobot_obj.get('weight') is not None:
            data['weight'] = nautobot_obj['weight']

        # Group name (NetBox 4.x supports grouping)
        if nautobot_obj.get('grouping'):
            data['group_name'] = nautobot_obj['grouping']

        # Validation settings
        if nautobot_obj.get('validation_minimum') is not None:
            data['validation_minimum'] = nautobot_obj['validation_minimum']
        if nautobot_obj.get('validation_maximum') is not None:
            data['validation_maximum'] = nautobot_obj['validation_maximum']
        if nautobot_obj.get('validation_regex'):
            data['validation_regex'] = nautobot_obj['validation_regex']

        # Default value
        if nautobot_obj.get('default') is not None:
            data['default'] = nautobot_obj['default']

        return data

    def get_choices(self, nautobot_obj: Dict) -> Optional[Dict]:
        """Extract choice set for select/multiselect fields.

        NetBox 4.x requires separate CustomFieldChoiceSet objects.
        """
        cf_type = nautobot_obj.get('type', 'text')
        if isinstance(cf_type, dict):
            cf_type = cf_type.get('value', 'text')

        if cf_type not in ('select', 'multi-select'):
            return None

        choices = nautobot_obj.get('choices', [])
        if not choices:
            return None

        return {
            'name': f"{nautobot_obj.get('name')}_choices",
            'extra_choices': [[c, c] for c in choices],
        }


class ConfigContextMapper(BaseMapper):
    """Mapper for config contexts."""

    object_type = 'config_context'

    def transform(self, nautobot_obj: Dict) -> Dict:
        """Transform a Nautobot config context to NetBox format."""
        data = {
            'name': nautobot_obj.get('name'),
            'weight': nautobot_obj.get('weight', 1000),
            'is_active': nautobot_obj.get('is_active', True),
            'data': nautobot_obj.get('data', {}),
        }

        # Description
        if nautobot_obj.get('description'):
            data['description'] = nautobot_obj['description']

        # Scoping - regions
        regions = nautobot_obj.get('regions', [])
        if regions:
            region_ids = []
            for region in regions:
                region_id = self._resolve_id('region', self._get_id(region))
                if region_id:
                    region_ids.append(region_id)
            if region_ids:
                data['regions'] = region_ids

        # Scoping - sites
        sites = nautobot_obj.get('sites', [])
        if sites:
            site_ids = []
            for site in sites:
                site_id = self._resolve_id('site', self._get_id(site))
                if site_id:
                    site_ids.append(site_id)
            if site_ids:
                data['sites'] = site_ids

        # Scoping - device roles
        roles = nautobot_obj.get('roles', []) or nautobot_obj.get('device_roles', [])
        if roles:
            role_ids = []
            for role in roles:
                role_id = self._resolve_id('device_role', self._get_id(role))
                if role_id:
                    role_ids.append(role_id)
            if role_ids:
                data['roles'] = role_ids

        # Scoping - platforms
        platforms = nautobot_obj.get('platforms', [])
        if platforms:
            platform_ids = []
            for platform in platforms:
                platform_id = self._resolve_id('platform', self._get_id(platform))
                if platform_id:
                    platform_ids.append(platform_id)
            if platform_ids:
                data['platforms'] = platform_ids

        # Scoping - tenants
        tenants = nautobot_obj.get('tenants', [])
        if tenants:
            tenant_ids = []
            for tenant in tenants:
                tenant_id = self._resolve_id('tenant', self._get_id(tenant))
                if tenant_id:
                    tenant_ids.append(tenant_id)
            if tenant_ids:
                data['tenants'] = tenant_ids

        # Scoping - tags
        tags = nautobot_obj.get('tags', [])
        if tags:
            tag_ids = []
            for tag in tags:
                tag_id = self._resolve_id('tag', self._get_id(tag))
                if tag_id:
                    tag_ids.append(tag_id)
            if tag_ids:
                data['tags'] = tag_ids

        return data
