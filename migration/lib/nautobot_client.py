"""
Nautobot API Client for data extraction.

Handles pagination and provides methods to fetch all object types
needed for migration to NetBox.
"""

import requests
from typing import Dict, List, Any, Optional, Generator
import logging

logger = logging.getLogger(__name__)


class NautobotClient:
    """Client for extracting data from Nautobot API."""

    def __init__(self, url: str, token: str, verify_ssl: bool = True):
        self.base_url = url.rstrip('/')
        self.token = token
        self.verify_ssl = verify_ssl
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Token {token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        })
        self.session.verify = verify_ssl

    def _get_paginated(self, endpoint: str, params: Optional[Dict] = None) -> Generator[Dict, None, None]:
        """Fetch all pages of a paginated endpoint."""
        url = f"{self.base_url}/api/{endpoint}/"
        params = params or {}
        params['limit'] = 100

        while url:
            logger.debug(f"Fetching: {url}")
            response = self.session.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            for item in data.get('results', []):
                yield item

            url = data.get('next')
            params = {}  # Clear params for subsequent requests (next URL includes them)

    def _get_all(self, endpoint: str, params: Optional[Dict] = None) -> List[Dict]:
        """Fetch all items from a paginated endpoint."""
        return list(self._get_paginated(endpoint, params))

    # Organization
    def get_tags(self) -> List[Dict]:
        """Fetch all tags."""
        return self._get_all('extras/tags')

    def get_custom_fields(self) -> List[Dict]:
        """Fetch all custom fields."""
        return self._get_all('extras/custom-fields')

    def get_custom_field_choices(self) -> List[Dict]:
        """Fetch all custom field choices."""
        return self._get_all('extras/custom-field-choices')

    # Tenancy
    def get_tenants(self) -> List[Dict]:
        """Fetch all tenants."""
        return self._get_all('tenancy/tenants')

    def get_tenant_groups(self) -> List[Dict]:
        """Fetch all tenant groups."""
        return self._get_all('tenancy/tenant-groups')

    # DCIM - Locations
    def get_regions(self) -> List[Dict]:
        """Fetch all regions."""
        return self._get_all('dcim/regions')

    def get_sites(self) -> List[Dict]:
        """Fetch all sites."""
        return self._get_all('dcim/sites')

    def get_locations(self) -> List[Dict]:
        """Fetch all locations."""
        return self._get_all('dcim/locations')

    # DCIM - Equipment
    def get_manufacturers(self) -> List[Dict]:
        """Fetch all manufacturers."""
        return self._get_all('dcim/manufacturers')

    def get_device_types(self) -> List[Dict]:
        """Fetch all device types."""
        return self._get_all('dcim/device-types')

    def get_device_roles(self) -> List[Dict]:
        """Fetch all device roles."""
        # Nautobot uses 'device-roles', NetBox 4.x uses 'roles'
        return self._get_all('dcim/device-roles')

    def get_platforms(self) -> List[Dict]:
        """Fetch all platforms."""
        return self._get_all('dcim/platforms')

    # DCIM - Racks
    def get_rack_groups(self) -> List[Dict]:
        """Fetch all rack groups."""
        return self._get_all('dcim/rack-groups')

    def get_racks(self) -> List[Dict]:
        """Fetch all racks."""
        return self._get_all('dcim/racks')

    # DCIM - Devices
    def get_devices(self) -> List[Dict]:
        """Fetch all devices."""
        return self._get_all('dcim/devices')

    def get_interfaces(self) -> List[Dict]:
        """Fetch all interfaces."""
        return self._get_all('dcim/interfaces')

    def get_console_ports(self) -> List[Dict]:
        """Fetch all console ports."""
        return self._get_all('dcim/console-ports')

    def get_power_ports(self) -> List[Dict]:
        """Fetch all power ports."""
        return self._get_all('dcim/power-ports')

    # DCIM - Connections
    def get_cables(self) -> List[Dict]:
        """Fetch all cables."""
        return self._get_all('dcim/cables')

    # DCIM - Virtual Chassis
    def get_virtual_chassis(self) -> List[Dict]:
        """Fetch all virtual chassis."""
        return self._get_all('dcim/virtual-chassis')

    # IPAM
    def get_vlan_groups(self) -> List[Dict]:
        """Fetch all VLAN groups."""
        return self._get_all('ipam/vlan-groups')

    def get_vlans(self) -> List[Dict]:
        """Fetch all VLANs."""
        return self._get_all('ipam/vlans')

    def get_vrf(self) -> List[Dict]:
        """Fetch all VRFs."""
        return self._get_all('ipam/vrfs')

    def get_route_targets(self) -> List[Dict]:
        """Fetch all route targets."""
        return self._get_all('ipam/route-targets')

    def get_prefixes(self) -> List[Dict]:
        """Fetch all prefixes."""
        return self._get_all('ipam/prefixes')

    def get_ip_addresses(self) -> List[Dict]:
        """Fetch all IP addresses."""
        return self._get_all('ipam/ip-addresses')

    def get_ip_ranges(self) -> List[Dict]:
        """Fetch all IP ranges."""
        return self._get_all('ipam/ip-ranges')

    # Extras
    def get_config_contexts(self) -> List[Dict]:
        """Fetch all config contexts."""
        return self._get_all('extras/config-contexts')

    def get_statuses(self) -> List[Dict]:
        """Fetch all statuses (Nautobot-specific)."""
        return self._get_all('extras/statuses')

    # GraphQL for complex queries
    def graphql_query(self, query: str, variables: Optional[Dict] = None) -> Dict:
        """Execute a GraphQL query."""
        url = f"{self.base_url}/api/graphql/"
        payload = {'query': query}
        if variables:
            payload['variables'] = variables

        response = self.session.post(url, json=payload)
        response.raise_for_status()
        return response.json()

    def test_connection(self) -> bool:
        """Test the connection to Nautobot."""
        try:
            url = f"{self.base_url}/api/"
            response = self.session.get(url)
            response.raise_for_status()
            logger.info(f"Successfully connected to Nautobot at {self.base_url}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Nautobot: {e}")
            return False
