"""
DCIM object mappers for Nautobot to NetBox migration.
"""

from typing import Dict, List, Any, Optional
import logging

from .base import BaseMapper
from lib.id_mapper import StatusMapper, InterfaceTypeMapper

logger = logging.getLogger(__name__)


class TagMapper(BaseMapper):
    """Mapper for tags."""

    object_type = 'tag'

    def transform(self, nautobot_obj: Dict) -> Dict:
        """Transform a Nautobot tag to NetBox format."""
        return {
            'name': nautobot_obj.get('name'),
            'slug': self._get_slug(nautobot_obj),
            'color': nautobot_obj.get('color', '9e9e9e').lstrip('#'),
            'description': nautobot_obj.get('description', '') or '',
        }


class RegionMapper(BaseMapper):
    """Mapper for regions."""

    object_type = 'region'

    def transform(self, nautobot_obj: Dict) -> Dict:
        """Transform a Nautobot region to NetBox format."""
        data = {
            'name': nautobot_obj.get('name'),
            'slug': self._get_slug(nautobot_obj),
            'description': nautobot_obj.get('description', '') or '',
        }

        # Handle parent region
        parent_id = self._resolve_nested_id(nautobot_obj, 'parent', 'region')
        if parent_id:
            data['parent'] = parent_id

        return data


class SiteMapper(BaseMapper):
    """Mapper for sites."""

    object_type = 'site'
    content_type = 'dcim.site'

    def transform(self, nautobot_obj: Dict) -> Dict:
        """Transform a Nautobot site to NetBox format."""
        data = {
            'name': nautobot_obj.get('name'),
            'slug': self._get_slug(nautobot_obj),
            'status': StatusMapper.get_status('site', nautobot_obj.get('status')),
            'description': nautobot_obj.get('description', '') or '',
        }

        # Handle region
        region_id = self._resolve_nested_id(nautobot_obj, 'region', 'region')
        if region_id:
            data['region'] = region_id

        # Handle tenant
        tenant_id = self._resolve_nested_id(nautobot_obj, 'tenant', 'tenant')
        if tenant_id:
            data['tenant'] = tenant_id

        # Optional fields
        if nautobot_obj.get('facility'):
            data['facility'] = nautobot_obj['facility']
        if nautobot_obj.get('time_zone'):
            data['time_zone'] = nautobot_obj['time_zone']
        if nautobot_obj.get('physical_address'):
            data['physical_address'] = nautobot_obj['physical_address']
        if nautobot_obj.get('shipping_address'):
            data['shipping_address'] = nautobot_obj['shipping_address']
        if nautobot_obj.get('latitude'):
            data['latitude'] = nautobot_obj['latitude']
        if nautobot_obj.get('longitude'):
            data['longitude'] = nautobot_obj['longitude']
        if nautobot_obj.get('comments'):
            data['comments'] = nautobot_obj['comments']

        # Custom fields
        custom_fields = self._transform_custom_fields(nautobot_obj)
        # Some environments define virtual-chassis evpn_role choices differently.
        # Drop this field to keep VC migration idempotent across target schemas.
        custom_fields.pop('evpn_role', None)
        if custom_fields:
            data['custom_fields'] = custom_fields

        # Tags
        tags = self._transform_tags(nautobot_obj)
        if tags:
            data['tags'] = tags

        return data


class ManufacturerMapper(BaseMapper):
    """Mapper for manufacturers."""

    object_type = 'manufacturer'

    def transform(self, nautobot_obj: Dict) -> Dict:
        """Transform a Nautobot manufacturer to NetBox format."""
        return {
            'name': nautobot_obj.get('name'),
            'slug': self._get_slug(nautobot_obj),
            'description': nautobot_obj.get('description', '') or '',
        }


class DeviceTypeMapper(BaseMapper):
    """Mapper for device types."""

    object_type = 'device_type'

    def transform(self, nautobot_obj: Dict) -> Dict:
        """Transform a Nautobot device type to NetBox format."""
        data = {
            'model': nautobot_obj.get('model'),
            'slug': self._get_slug(nautobot_obj),
        }

        # Manufacturer (required)
        manufacturer_id = self._resolve_nested_id(nautobot_obj, 'manufacturer', 'manufacturer')
        if manufacturer_id:
            data['manufacturer'] = manufacturer_id

        # Optional fields
        if nautobot_obj.get('part_number'):
            data['part_number'] = nautobot_obj['part_number']
        if nautobot_obj.get('u_height') is not None:
            data['u_height'] = nautobot_obj['u_height']
        if nautobot_obj.get('is_full_depth') is not None:
            data['is_full_depth'] = nautobot_obj['is_full_depth']
        if nautobot_obj.get('comments'):
            data['comments'] = nautobot_obj['comments']

        return data


class DeviceRoleMapper(BaseMapper):
    """Mapper for device roles."""

    object_type = 'device_role'

    def transform(self, nautobot_obj: Dict) -> Dict:
        """Transform a Nautobot device role to NetBox format."""
        return {
            'name': nautobot_obj.get('name'),
            'slug': self._get_slug(nautobot_obj),
            'color': nautobot_obj.get('color', '9e9e9e').lstrip('#'),
            'vm_role': nautobot_obj.get('vm_role', False),
            'description': nautobot_obj.get('description', '') or '',
        }


class PlatformMapper(BaseMapper):
    """Mapper for platforms."""

    object_type = 'platform'

    def transform(self, nautobot_obj: Dict) -> Dict:
        """Transform a Nautobot platform to NetBox format."""
        data = {
            'name': nautobot_obj.get('name'),
            'slug': self._get_slug(nautobot_obj),
            'description': nautobot_obj.get('description', '') or '',
        }

        # Manufacturer (optional in NetBox)
        manufacturer_id = self._resolve_nested_id(nautobot_obj, 'manufacturer', 'manufacturer')
        if manufacturer_id:
            data['manufacturer'] = manufacturer_id

        # NAPALM driver
        if nautobot_obj.get('napalm_driver'):
            data['napalm_driver'] = nautobot_obj['napalm_driver']

        return data


class RackMapper(BaseMapper):
    """Mapper for racks."""

    object_type = 'rack'

    def transform(self, nautobot_obj: Dict) -> Dict:
        """Transform a Nautobot rack to NetBox format."""
        data = {
            'name': nautobot_obj.get('name'),
            'status': StatusMapper.get_status('device', nautobot_obj.get('status', 'active')),
        }

        # Site (required)
        site_id = self._resolve_nested_id(nautobot_obj, 'site', 'site')
        if site_id:
            data['site'] = site_id

        # Location (NetBox 4.x rack groups become locations)
        location_id = self._resolve_nested_id(nautobot_obj, 'group', 'location')
        if location_id:
            data['location'] = location_id

        # Tenant
        tenant_id = self._resolve_nested_id(nautobot_obj, 'tenant', 'tenant')
        if tenant_id:
            data['tenant'] = tenant_id

        # Optional fields
        if nautobot_obj.get('u_height'):
            data['u_height'] = nautobot_obj['u_height']
        if nautobot_obj.get('width'):
            width = nautobot_obj['width']
            # Nautobot returns width as {'value': 19, 'label': '19 inches'}, NetBox wants just 19
            if isinstance(width, dict):
                data['width'] = width.get('value', 19)
            else:
                data['width'] = width
        if nautobot_obj.get('serial'):
            data['serial'] = nautobot_obj['serial']
        if nautobot_obj.get('comments'):
            data['comments'] = nautobot_obj['comments']

        return data


class DeviceMapper(BaseMapper):
    """Mapper for devices."""

    object_type = 'device'
    content_type = 'dcim.device'

    def transform(self, nautobot_obj: Dict) -> Dict:
        """Transform a Nautobot device to NetBox format."""
        data = {
            'name': nautobot_obj.get('name'),
            'status': StatusMapper.get_status('device', nautobot_obj.get('status')),
        }

        # Site (required)
        site_id = self._resolve_nested_id(nautobot_obj, 'site', 'site')
        if site_id:
            data['site'] = site_id

        # Device type (required)
        device_type_id = self._resolve_nested_id(nautobot_obj, 'device_type', 'device_type')
        if device_type_id:
            data['device_type'] = device_type_id

        # Role (required) - Note: Nautobot uses device_role, NetBox 4.x uses role
        role_id = self._resolve_nested_id(nautobot_obj, 'device_role', 'device_role')
        if not role_id:
            role_id = self._resolve_nested_id(nautobot_obj, 'role', 'device_role')
        if role_id:
            data['role'] = role_id

        # Platform
        platform_id = self._resolve_nested_id(nautobot_obj, 'platform', 'platform')
        if platform_id:
            data['platform'] = platform_id

        # Tenant
        tenant_id = self._resolve_nested_id(nautobot_obj, 'tenant', 'tenant')
        if tenant_id:
            data['tenant'] = tenant_id

        # Rack
        rack_id = self._resolve_nested_id(nautobot_obj, 'rack', 'rack')
        if rack_id:
            data['rack'] = rack_id
            if nautobot_obj.get('position'):
                data['position'] = nautobot_obj['position']
            if nautobot_obj.get('face'):
                face = nautobot_obj['face']
                if isinstance(face, dict):
                    data['face'] = face.get('value', 'front')
                else:
                    data['face'] = face

        # Location
        location_id = self._resolve_nested_id(nautobot_obj, 'location', 'location')
        if location_id:
            data['location'] = location_id

        # Optional fields
        if nautobot_obj.get('serial'):
            data['serial'] = nautobot_obj['serial']
        if nautobot_obj.get('asset_tag'):
            data['asset_tag'] = nautobot_obj['asset_tag']
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


class InterfaceMapper(BaseMapper):
    """Mapper for interfaces."""

    object_type = 'interface'
    content_type = 'dcim.interface'

    def transform(self, nautobot_obj: Dict) -> Dict:
        """Transform a Nautobot interface to NetBox format."""
        data = {
            'name': nautobot_obj.get('name'),
            'type': InterfaceTypeMapper.get_type(nautobot_obj.get('type')),
            'enabled': nautobot_obj.get('enabled', True),
        }

        # Device (required)
        device_id = self._resolve_nested_id(nautobot_obj, 'device', 'device')
        if device_id:
            data['device'] = device_id

        # LAG parent
        lag_id = self._resolve_nested_id(nautobot_obj, 'lag', 'interface')
        if lag_id:
            data['lag'] = lag_id

        # Mode (access/tagged/tagged-all)
        mode = nautobot_obj.get('mode')
        if mode:
            if isinstance(mode, dict):
                mode_value = mode.get('value', '')
            else:
                mode_value = str(mode)
            if mode_value:
                data['mode'] = mode_value

        # Untagged VLAN
        untagged_vlan_id = self._resolve_nested_id(nautobot_obj, 'untagged_vlan', 'vlan')
        if untagged_vlan_id:
            data['untagged_vlan'] = untagged_vlan_id

        # Tagged VLANs
        tagged_vlans = nautobot_obj.get('tagged_vlans', [])
        if tagged_vlans:
            tagged_ids = []
            for vlan in tagged_vlans:
                vlan_id = self._resolve_id('vlan', self._get_id(vlan))
                if vlan_id:
                    tagged_ids.append(vlan_id)
            if tagged_ids:
                data['tagged_vlans'] = tagged_ids

        # Optional fields
        if nautobot_obj.get('mac_address'):
            data['mac_address'] = nautobot_obj['mac_address']
        if nautobot_obj.get('mtu'):
            data['mtu'] = nautobot_obj['mtu']
        if nautobot_obj.get('description'):
            data['description'] = nautobot_obj['description']
        if nautobot_obj.get('mgmt_only') is not None:
            data['mgmt_only'] = nautobot_obj['mgmt_only']

        # Custom fields
        custom_fields = self._transform_custom_fields(nautobot_obj)
        if custom_fields:
            data['custom_fields'] = custom_fields

        # Tags
        tags = self._transform_tags(nautobot_obj)
        if tags:
            data['tags'] = tags

        return data


class CableMapper(BaseMapper):
    """Mapper for cables."""

    object_type = 'cable'

    def transform(self, nautobot_obj: Dict) -> Dict:
        """Transform a Nautobot cable to NetBox format.

        NetBox 4.x uses a_terminations/b_terminations format.
        """
        data = {
            'status': StatusMapper.get_status('cable', nautobot_obj.get('status', 'connected')),
        }

        # Termination A
        term_a_type = nautobot_obj.get('termination_a_type')
        term_a_id = nautobot_obj.get('termination_a_id')
        if term_a_type and term_a_id:
            netbox_term_a_id = self._resolve_termination(term_a_type, term_a_id)
            if netbox_term_a_id:
                data['a_terminations'] = [{
                    'object_type': self._map_termination_type(term_a_type),
                    'object_id': netbox_term_a_id
                }]

        # Termination B
        term_b_type = nautobot_obj.get('termination_b_type')
        term_b_id = nautobot_obj.get('termination_b_id')
        if term_b_type and term_b_id:
            netbox_term_b_id = self._resolve_termination(term_b_type, term_b_id)
            if netbox_term_b_id:
                data['b_terminations'] = [{
                    'object_type': self._map_termination_type(term_b_type),
                    'object_id': netbox_term_b_id
                }]

        # Optional fields
        if nautobot_obj.get('type'):
            cable_type = nautobot_obj['type']
            if isinstance(cable_type, dict):
                data['type'] = cable_type.get('value', '')
            else:
                data['type'] = cable_type
        if nautobot_obj.get('label'):
            data['label'] = nautobot_obj['label']
        if nautobot_obj.get('color'):
            data['color'] = nautobot_obj['color']
        if nautobot_obj.get('length'):
            data['length'] = nautobot_obj['length']
            if nautobot_obj.get('length_unit'):
                length_unit = nautobot_obj['length_unit']
                if isinstance(length_unit, dict):
                    data['length_unit'] = length_unit.get('value', 'm')
                else:
                    data['length_unit'] = length_unit

        return data

    def _resolve_termination(self, term_type: str, nautobot_id: str) -> Optional[int]:
        """Resolve termination ID based on type."""
        type_mapping = {
            'dcim.interface': 'interface',
            'dcim.consoleport': 'console_port',
            'dcim.consoleserverport': 'console_server_port',
            'dcim.powerport': 'power_port',
            'dcim.poweroutlet': 'power_outlet',
            'dcim.frontport': 'front_port',
            'dcim.rearport': 'rear_port',
        }
        obj_type = type_mapping.get(term_type, 'interface')
        return self._resolve_id(obj_type, nautobot_id)

    def _map_termination_type(self, nautobot_type: str) -> str:
        """Map Nautobot termination type to NetBox content type."""
        type_mapping = {
            'dcim.interface': 'dcim.interface',
            'dcim.consoleport': 'dcim.consoleport',
            'dcim.consoleserverport': 'dcim.consoleserverport',
            'dcim.powerport': 'dcim.powerport',
            'dcim.poweroutlet': 'dcim.poweroutlet',
            'dcim.frontport': 'dcim.frontport',
            'dcim.rearport': 'dcim.rearport',
        }
        return type_mapping.get(nautobot_type, 'dcim.interface')


class VirtualChassisMapper(BaseMapper):
    """Mapper for virtual chassis."""

    object_type = 'virtual_chassis'
    content_type = 'dcim.virtualchassis'

    def transform(self, nautobot_obj: Dict) -> Dict:
        """Transform a Nautobot virtual chassis to NetBox format."""
        data = {
            'name': nautobot_obj.get('name'),
        }

        # Master device
        master_id = self._resolve_nested_id(nautobot_obj, 'master', 'device')
        if master_id:
            data['master'] = master_id

        # Domain (optional)
        if nautobot_obj.get('domain'):
            data['domain'] = nautobot_obj['domain']

        # Custom fields
        custom_fields = self._transform_custom_fields(nautobot_obj)
        if custom_fields:
            data['custom_fields'] = custom_fields

        # Tags
        tags = self._transform_tags(nautobot_obj)
        if tags:
            data['tags'] = tags

        return data

    def get_member_devices(self, nautobot_obj: Dict) -> List[Dict]:
        """Get member device updates for virtual chassis.

        Returns list of device updates with vc_position and vc_priority.
        """
        members = []
        member_data = nautobot_obj.get('members', [])

        for member in member_data:
            device_id = self._resolve_id('device', self._get_id(member))
            if device_id:
                members.append({
                    'device_id': device_id,
                    'vc_position': member.get('vc_position'),
                    'vc_priority': member.get('vc_priority'),
                })

        return members
