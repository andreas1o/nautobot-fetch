"""
NetBox API Client for data insertion.

Handles object creation in NetBox 4.2.9+ with proper error handling
and support for custom fields.
"""

import requests
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)


class NetBoxClient:
    """Client for inserting data into NetBox API."""

    def __init__(self, url: str, token: str, verify_ssl: bool = True, dry_run: bool = False):
        self.base_url = url.rstrip('/')
        self.token = token
        self.verify_ssl = verify_ssl
        self.dry_run = dry_run
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Token {token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        })
        self.session.verify = verify_ssl

    def _post(self, endpoint: str, data: Dict) -> Optional[Dict]:
        """Create a single object."""
        if self.dry_run:
            logger.info(f"[DRY RUN] Would create {endpoint}: {data.get('name', data.get('address', data.get('slug', 'unknown')))}")
            return {'id': 0, **data}  # Return mock data

        url = f"{self.base_url}/api/{endpoint}/"
        logger.debug(f"POST {url}: {data}")

        response = self.session.post(url, json=data)
        if not response.ok:
            logger.error(f"Failed to create {endpoint}: {response.status_code}")
            logger.error(f"Request data: {data}")
            logger.error(f"Response: {response.text}")
            response.raise_for_status()

        result = response.json()
        logger.debug(f"Created: {result.get('id')}")
        return result

    def _post_bulk(self, endpoint: str, data: List[Dict]) -> List[Dict]:
        """Create multiple objects in bulk."""
        if self.dry_run:
            logger.info(f"[DRY RUN] Would create {len(data)} objects in {endpoint}")
            return [{'id': i, **d} for i, d in enumerate(data)]

        url = f"{self.base_url}/api/{endpoint}/"
        logger.debug(f"POST BULK {url}: {len(data)} objects")

        try:
            response = self.session.post(url, json=data)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            logger.error(f"Bulk create failed for {endpoint}: {e}")
            logger.error(f"Response: {e.response.text if e.response else 'No response'}")
            raise

    def _get(self, endpoint: str, params: Optional[Dict] = None) -> List[Dict]:
        """Get objects with optional filtering."""
        url = f"{self.base_url}/api/{endpoint}/"
        all_results = []
        params = params or {}
        params['limit'] = 100

        while url:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            all_results.extend(data.get('results', []))
            url = data.get('next')
            params = {}

        return all_results

    def _get_by_name(self, endpoint: str, name: str) -> Optional[Dict]:
        """Get an object by name."""
        results = self._get(endpoint, {'name': name})
        return results[0] if results else None

    def _get_by_slug(self, endpoint: str, slug: str) -> Optional[Dict]:
        """Get an object by slug."""
        results = self._get(endpoint, {'slug': slug})
        return results[0] if results else None

    # Organization
    def create_tag(self, data: Dict) -> Optional[Dict]:
        """Create a tag."""
        return self._post('extras/tags', data)

    def get_tags(self) -> List[Dict]:
        """Get all tags."""
        return self._get('extras/tags')

    def create_custom_field(self, data: Dict) -> Optional[Dict]:
        """Create a custom field."""
        return self._post('extras/custom-fields', data)

    def get_custom_fields(self) -> List[Dict]:
        """Get all custom fields."""
        return self._get('extras/custom-fields')

    def create_custom_field_choice(self, data: Dict) -> Optional[Dict]:
        """Create a custom field choice set."""
        return self._post('extras/custom-field-choice-sets', data)

    # Tenancy
    def create_tenant_group(self, data: Dict) -> Optional[Dict]:
        """Create a tenant group."""
        return self._post('tenancy/tenant-groups', data)

    def create_tenant(self, data: Dict) -> Optional[Dict]:
        """Create a tenant."""
        return self._post('tenancy/tenants', data)

    def get_tenants(self) -> List[Dict]:
        """Get all tenants."""
        return self._get('tenancy/tenants')

    # DCIM - Locations
    def create_region(self, data: Dict) -> Optional[Dict]:
        """Create a region."""
        return self._post('dcim/regions', data)

    def get_regions(self) -> List[Dict]:
        """Get all regions."""
        return self._get('dcim/regions')

    def create_site(self, data: Dict) -> Optional[Dict]:
        """Create a site."""
        return self._post('dcim/sites', data)

    def get_sites(self) -> List[Dict]:
        """Get all sites."""
        return self._get('dcim/sites')

    def create_location(self, data: Dict) -> Optional[Dict]:
        """Create a location."""
        return self._post('dcim/locations', data)

    # DCIM - Equipment
    def create_manufacturer(self, data: Dict) -> Optional[Dict]:
        """Create a manufacturer."""
        return self._post('dcim/manufacturers', data)

    def get_manufacturers(self) -> List[Dict]:
        """Get all manufacturers."""
        return self._get('dcim/manufacturers')

    def create_device_type(self, data: Dict) -> Optional[Dict]:
        """Create a device type."""
        return self._post('dcim/device-types', data)

    def get_device_types(self) -> List[Dict]:
        """Get all device types."""
        return self._get('dcim/device-types')

    def create_device_role(self, data: Dict) -> Optional[Dict]:
        """Create a device role (NetBox 4.x uses 'roles' endpoint)."""
        return self._post('dcim/device-roles', data)

    def get_device_roles(self) -> List[Dict]:
        """Get all device roles."""
        return self._get('dcim/device-roles')

    def create_platform(self, data: Dict) -> Optional[Dict]:
        """Create a platform."""
        return self._post('dcim/platforms', data)

    def get_platforms(self) -> List[Dict]:
        """Get all platforms."""
        return self._get('dcim/platforms')

    # DCIM - Racks
    def create_rack_group(self, data: Dict) -> Optional[Dict]:
        """Create a rack group (location in NetBox 4.x)."""
        return self._post('dcim/locations', data)

    def create_rack(self, data: Dict) -> Optional[Dict]:
        """Create a rack."""
        return self._post('dcim/racks', data)

    # DCIM - Devices
    def create_device(self, data: Dict) -> Optional[Dict]:
        """Create a device."""
        return self._post('dcim/devices', data)

    def get_devices(self) -> List[Dict]:
        """Get all devices."""
        return self._get('dcim/devices')

    def create_interface(self, data: Dict) -> Optional[Dict]:
        """Create an interface."""
        return self._post('dcim/interfaces', data)

    def get_interfaces(self, device_id: Optional[int] = None) -> List[Dict]:
        """Get interfaces, optionally filtered by device."""
        params = {'device_id': device_id} if device_id else None
        return self._get('dcim/interfaces', params)

    def create_interface_bulk(self, data: List[Dict]) -> List[Dict]:
        """Create multiple interfaces."""
        return self._post_bulk('dcim/interfaces', data)

    # DCIM - Connections
    def create_cable(self, data: Dict) -> Optional[Dict]:
        """Create a cable."""
        return self._post('dcim/cables', data)

    # DCIM - Virtual Chassis
    def create_virtual_chassis(self, data: Dict) -> Optional[Dict]:
        """Create a virtual chassis."""
        return self._post('dcim/virtual-chassis', data)

    def update_device(self, device_id: int, data: Dict) -> Optional[Dict]:
        """Update a device (for virtual chassis assignment)."""
        if self.dry_run:
            logger.info(f"[DRY RUN] Would update device {device_id}")
            return data

        url = f"{self.base_url}/api/dcim/devices/{device_id}/"
        response = self.session.patch(url, json=data)
        response.raise_for_status()
        return response.json()

    # IPAM
    def create_vlan_group(self, data: Dict) -> Optional[Dict]:
        """Create a VLAN group."""
        return self._post('ipam/vlan-groups', data)

    def get_vlan_groups(self) -> List[Dict]:
        """Get all VLAN groups."""
        return self._get('ipam/vlan-groups')

    def create_vlan(self, data: Dict) -> Optional[Dict]:
        """Create a VLAN."""
        return self._post('ipam/vlans', data)

    def get_vlans(self) -> List[Dict]:
        """Get all VLANs."""
        return self._get('ipam/vlans')

    def create_vrf(self, data: Dict) -> Optional[Dict]:
        """Create a VRF."""
        return self._post('ipam/vrfs', data)

    def get_vrfs(self) -> List[Dict]:
        """Get all VRFs."""
        return self._get('ipam/vrfs')

    def create_route_target(self, data: Dict) -> Optional[Dict]:
        """Create a route target."""
        return self._post('ipam/route-targets', data)

    def create_prefix(self, data: Dict) -> Optional[Dict]:
        """Create a prefix."""
        return self._post('ipam/prefixes', data)

    def get_prefixes(self) -> List[Dict]:
        """Get all prefixes."""
        return self._get('ipam/prefixes')

    def create_ip_address(self, data: Dict) -> Optional[Dict]:
        """Create an IP address."""
        return self._post('ipam/ip-addresses', data)

    def get_ip_addresses(self) -> List[Dict]:
        """Get all IP addresses."""
        return self._get('ipam/ip-addresses')

    # Extras
    def create_config_context(self, data: Dict) -> Optional[Dict]:
        """Create a config context."""
        return self._post('extras/config-contexts', data)

    def get_config_contexts(self) -> List[Dict]:
        """Get all config contexts."""
        return self._get('extras/config-contexts')

    def test_connection(self) -> bool:
        """Test the connection to NetBox."""
        try:
            url = f"{self.base_url}/api/"
            response = self.session.get(url)
            response.raise_for_status()
            logger.info(f"Successfully connected to NetBox at {self.base_url}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to NetBox: {e}")
            return False

    def get_api_version(self) -> Optional[str]:
        """Get the NetBox API version."""
        try:
            url = f"{self.base_url}/api/"
            response = self.session.get(url)
            response.raise_for_status()
            # NetBox returns version in headers or response
            return response.headers.get('API-Version', 'unknown')
        except Exception:
            return None
