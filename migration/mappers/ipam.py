"""
IPAM object mappers for Nautobot to NetBox migration.
"""

from typing import Dict, List, Any, Optional
import logging

from .base import BaseMapper
from lib.id_mapper import StatusMapper

logger = logging.getLogger(__name__)


class VLANGroupMapper(BaseMapper):
    """Mapper for VLAN groups."""

    object_type = 'vlan_group'

    def transform(self, nautobot_obj: Dict) -> Dict:
        """Transform a Nautobot VLAN group to NetBox format."""
        data = {
            'name': nautobot_obj.get('name'),
            'slug': self._get_slug(nautobot_obj),
            'description': nautobot_obj.get('description', '') or '',
        }

        # Site scope (NetBox 4.x uses scope_type/scope_id for generic scoping)
        site_id = self._resolve_nested_id(nautobot_obj, 'site', 'site')
        if site_id:
            data['scope_type'] = 'dcim.site'
            data['scope_id'] = site_id

        # Min/max VLAN IDs
        if nautobot_obj.get('min_vid'):
            data['min_vid'] = nautobot_obj['min_vid']
        if nautobot_obj.get('max_vid'):
            data['max_vid'] = nautobot_obj['max_vid']

        return data


class VLANMapper(BaseMapper):
    """Mapper for VLANs."""

    object_type = 'vlan'
    content_type = 'ipam.vlan'

    def transform(self, nautobot_obj: Dict) -> Dict:
        """Transform a Nautobot VLAN to NetBox format."""
        data = {
            'vid': nautobot_obj.get('vid'),
            'name': nautobot_obj.get('name'),
            'status': StatusMapper.get_status('vlan', nautobot_obj.get('status')),
        }

        # Site
        site_id = self._resolve_nested_id(nautobot_obj, 'site', 'site')
        if site_id:
            data['site'] = site_id

        # VLAN Group
        group_id = self._resolve_nested_id(nautobot_obj, 'group', 'vlan_group')
        if group_id:
            data['group'] = group_id

        # Tenant
        tenant_id = self._resolve_nested_id(nautobot_obj, 'tenant', 'tenant')
        if tenant_id:
            data['tenant'] = tenant_id

        # Role
        role_id = self._resolve_nested_id(nautobot_obj, 'role', 'vlan_role')
        if role_id:
            data['role'] = role_id

        # Optional fields
        if nautobot_obj.get('description'):
            data['description'] = nautobot_obj['description']

        # Custom fields
        custom_fields = self._transform_custom_fields(nautobot_obj)
        if custom_fields:
            data['custom_fields'] = custom_fields

        # Tags
        tags = self._transform_tags(nautobot_obj)
        if tags:
            data['tags'] = tags

        return data


class VRFMapper(BaseMapper):
    """Mapper for VRFs."""

    object_type = 'vrf'

    def transform(self, nautobot_obj: Dict) -> Dict:
        """Transform a Nautobot VRF to NetBox format."""
        data = {
            'name': nautobot_obj.get('name'),
            'enforce_unique': nautobot_obj.get('enforce_unique', True),
        }

        # RD (Route Distinguisher)
        if nautobot_obj.get('rd'):
            data['rd'] = nautobot_obj['rd']

        # Tenant
        tenant_id = self._resolve_nested_id(nautobot_obj, 'tenant', 'tenant')
        if tenant_id:
            data['tenant'] = tenant_id

        # Description
        if nautobot_obj.get('description'):
            data['description'] = nautobot_obj['description']

        # Import/Export targets
        import_targets = nautobot_obj.get('import_targets', [])
        if import_targets:
            import_ids = []
            for rt in import_targets:
                rt_id = self._resolve_id('route_target', self._get_id(rt))
                if rt_id:
                    import_ids.append(rt_id)
            if import_ids:
                data['import_targets'] = import_ids

        export_targets = nautobot_obj.get('export_targets', [])
        if export_targets:
            export_ids = []
            for rt in export_targets:
                rt_id = self._resolve_id('route_target', self._get_id(rt))
                if rt_id:
                    export_ids.append(rt_id)
            if export_ids:
                data['export_targets'] = export_ids

        # Custom fields
        custom_fields = self._transform_custom_fields(nautobot_obj)
        if custom_fields:
            data['custom_fields'] = custom_fields

        # Tags
        tags = self._transform_tags(nautobot_obj)
        if tags:
            data['tags'] = tags

        return data


class RouteTargetMapper(BaseMapper):
    """Mapper for route targets."""

    object_type = 'route_target'

    def transform(self, nautobot_obj: Dict) -> Dict:
        """Transform a Nautobot route target to NetBox format."""
        data = {
            'name': nautobot_obj.get('name'),
        }

        # Tenant
        tenant_id = self._resolve_nested_id(nautobot_obj, 'tenant', 'tenant')
        if tenant_id:
            data['tenant'] = tenant_id

        # Description
        if nautobot_obj.get('description'):
            data['description'] = nautobot_obj['description']

        return data


class PrefixMapper(BaseMapper):
    """Mapper for prefixes."""

    object_type = 'prefix'
    content_type = 'ipam.prefix'

    def transform(self, nautobot_obj: Dict) -> Dict:
        """Transform a Nautobot prefix to NetBox format.

        Note: Nautobot stores prefix as a computed field from network/prefix_length.
        NetBox 4.x uses a scope generic FK instead of direct site FK.
        """
        # Get prefix value
        prefix = nautobot_obj.get('prefix')
        if not prefix:
            # Try to construct from network and prefix_length
            network = nautobot_obj.get('network')
            prefix_length = nautobot_obj.get('prefix_length')
            if network and prefix_length:
                prefix = f"{network}/{prefix_length}"

        if not prefix:
            logger.warning(f"Prefix missing for object {nautobot_obj.get('id')}")
            return None

        data = {
            'prefix': prefix,
            'status': StatusMapper.get_status('prefix', nautobot_obj.get('status')),
        }

        # Site (NetBox 4.x uses scope for site)
        site_id = self._resolve_nested_id(nautobot_obj, 'site', 'site')
        if site_id:
            data['site'] = site_id

        # VRF
        vrf_id = self._resolve_nested_id(nautobot_obj, 'vrf', 'vrf')
        if vrf_id:
            data['vrf'] = vrf_id

        # VLAN
        vlan_id = self._resolve_nested_id(nautobot_obj, 'vlan', 'vlan')
        if vlan_id:
            data['vlan'] = vlan_id

        # Tenant
        tenant_id = self._resolve_nested_id(nautobot_obj, 'tenant', 'tenant')
        if tenant_id:
            data['tenant'] = tenant_id

        # Role
        role_id = self._resolve_nested_id(nautobot_obj, 'role', 'prefix_role')
        if role_id:
            data['role'] = role_id

        # is_pool
        if nautobot_obj.get('is_pool') is not None:
            data['is_pool'] = nautobot_obj['is_pool']

        # Description
        if nautobot_obj.get('description'):
            data['description'] = nautobot_obj['description']

        # Custom fields
        custom_fields = self._transform_custom_fields(nautobot_obj)
        if custom_fields:
            data['custom_fields'] = custom_fields

        # Tags
        tags = self._transform_tags(nautobot_obj)
        if tags:
            data['tags'] = tags

        return data


class IPAddressMapper(BaseMapper):
    """Mapper for IP addresses."""

    object_type = 'ip_address'
    content_type = 'ipam.ipaddress'

    def transform(self, nautobot_obj: Dict) -> Dict:
        """Transform a Nautobot IP address to NetBox format.

        Note: Nautobot stores address as a computed field from host/mask_length.
        NetBox uses assigned_object for interface assignment.
        """
        # Get address value
        address = nautobot_obj.get('address')
        if not address:
            # Try to construct from host and mask_length
            host = nautobot_obj.get('host')
            mask_length = nautobot_obj.get('mask_length')
            if host and mask_length:
                address = f"{host}/{mask_length}"

        if not address:
            logger.warning(f"Address missing for IP object {nautobot_obj.get('id')}")
            return None

        data = {
            'address': address,
            'status': StatusMapper.get_status('ip_address', nautobot_obj.get('status')),
        }

        # VRF
        vrf_id = self._resolve_nested_id(nautobot_obj, 'vrf', 'vrf')
        if vrf_id:
            data['vrf'] = vrf_id

        # Tenant
        tenant_id = self._resolve_nested_id(nautobot_obj, 'tenant', 'tenant')
        if tenant_id:
            data['tenant'] = tenant_id

        # Assigned object (interface)
        assigned_obj = nautobot_obj.get('assigned_object')
        if assigned_obj:
            assigned_type = nautobot_obj.get('assigned_object_type')
            if assigned_type == 'dcim.interface':
                interface_id = self._resolve_id('interface', self._get_id(assigned_obj))
                if interface_id:
                    data['assigned_object_type'] = 'dcim.interface'
                    data['assigned_object_id'] = interface_id
            elif assigned_type == 'virtualization.vminterface':
                vm_interface_id = self._resolve_id('vminterface', self._get_id(assigned_obj))
                if vm_interface_id:
                    data['assigned_object_type'] = 'virtualization.vminterface'
                    data['assigned_object_id'] = vm_interface_id

        # Role
        role = nautobot_obj.get('role')
        if role:
            if isinstance(role, dict):
                data['role'] = role.get('value', '')
            else:
                data['role'] = role

        # DNS name
        if nautobot_obj.get('dns_name'):
            data['dns_name'] = nautobot_obj['dns_name']

        # Description
        if nautobot_obj.get('description'):
            data['description'] = nautobot_obj['description']

        # Custom fields
        custom_fields = self._transform_custom_fields(nautobot_obj)
        if custom_fields:
            data['custom_fields'] = custom_fields

        # Tags
        tags = self._transform_tags(nautobot_obj)
        if tags:
            data['tags'] = tags

        return data
