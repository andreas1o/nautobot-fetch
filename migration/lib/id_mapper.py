"""
ID Mapper for tracking Nautobot UUID to NetBox ID relationships.

Nautobot uses UUIDs for primary keys while NetBox uses integers.
This mapper maintains the relationship to resolve foreign keys during migration.
"""

import json
import os
from typing import Dict, Optional, Any
import logging

logger = logging.getLogger(__name__)


class IDMapper:
    """Maps Nautobot UUIDs to NetBox integer IDs."""

    def __init__(self, cache_file: str = 'id_mapping.json'):
        self.cache_file = cache_file
        self._mapping: Dict[str, Dict[str, int]] = {}
        self._reverse_mapping: Dict[str, Dict[int, str]] = {}
        self._load_cache()

    def _load_cache(self):
        """Load mapping from cache file if it exists."""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r') as f:
                    self._mapping = json.load(f)
                    # Build reverse mapping
                    for obj_type, mappings in self._mapping.items():
                        self._reverse_mapping[obj_type] = {v: k for k, v in mappings.items()}
                logger.info(f"Loaded ID mapping from {self.cache_file}")
            except Exception as e:
                logger.warning(f"Failed to load cache: {e}")
                self._mapping = {}

    def save_cache(self):
        """Save mapping to cache file."""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self._mapping, f, indent=2)
            logger.debug(f"Saved ID mapping to {self.cache_file}")
        except Exception as e:
            logger.error(f"Failed to save cache: {e}")

    def add(self, obj_type: str, nautobot_id: str, netbox_id: int):
        """Add a mapping between Nautobot UUID and NetBox ID."""
        if obj_type not in self._mapping:
            self._mapping[obj_type] = {}
            self._reverse_mapping[obj_type] = {}

        self._mapping[obj_type][str(nautobot_id)] = netbox_id
        self._reverse_mapping[obj_type][netbox_id] = str(nautobot_id)
        logger.debug(f"Mapped {obj_type}: {nautobot_id} -> {netbox_id}")

    def get_netbox_id(self, obj_type: str, nautobot_id: str) -> Optional[int]:
        """Get NetBox ID for a Nautobot UUID."""
        if not nautobot_id:
            return None
        return self._mapping.get(obj_type, {}).get(str(nautobot_id))

    def get_nautobot_id(self, obj_type: str, netbox_id: int) -> Optional[str]:
        """Get Nautobot UUID for a NetBox ID."""
        return self._reverse_mapping.get(obj_type, {}).get(netbox_id)

    def has(self, obj_type: str, nautobot_id: str) -> bool:
        """Check if a mapping exists."""
        return str(nautobot_id) in self._mapping.get(obj_type, {})

    def get_all(self, obj_type: str) -> Dict[str, int]:
        """Get all mappings for an object type."""
        return self._mapping.get(obj_type, {})

    def count(self, obj_type: str) -> int:
        """Get count of mappings for an object type."""
        return len(self._mapping.get(obj_type, {}))

    def total_count(self) -> int:
        """Get total count of all mappings."""
        return sum(len(m) for m in self._mapping.values())

    def clear(self, obj_type: Optional[str] = None):
        """Clear mappings for an object type or all mappings."""
        if obj_type:
            self._mapping.pop(obj_type, None)
            self._reverse_mapping.pop(obj_type, None)
        else:
            self._mapping = {}
            self._reverse_mapping = {}

    def summary(self) -> Dict[str, int]:
        """Get a summary of mappings by object type."""
        return {obj_type: len(mappings) for obj_type, mappings in self._mapping.items()}

    def __repr__(self):
        return f"IDMapper({self.total_count()} mappings across {len(self._mapping)} types)"


class StatusMapper:
    """Maps Nautobot status names to NetBox status values."""

    # Nautobot uses a Status model, NetBox uses predefined choices
    DEVICE_STATUS_MAP = {
        'Active': 'active',
        'active': 'active',
        'Planned': 'planned',
        'planned': 'planned',
        'Staged': 'staged',
        'staged': 'staged',
        'Failed': 'failed',
        'failed': 'failed',
        'Offline': 'offline',
        'offline': 'offline',
        'Decommissioning': 'decommissioning',
        'decommissioning': 'decommissioning',
        'Inventory': 'inventory',
        'inventory': 'inventory',
    }

    SITE_STATUS_MAP = {
        'Active': 'active',
        'active': 'active',
        'Planned': 'planned',
        'planned': 'planned',
        'Staging': 'staging',
        'staging': 'staging',
        'Decommissioning': 'decommissioning',
        'decommissioning': 'decommissioning',
        'Retired': 'retired',
        'retired': 'retired',
    }

    PREFIX_STATUS_MAP = {
        'Active': 'active',
        'active': 'active',
        'Container': 'container',
        'container': 'container',
        'Reserved': 'reserved',
        'reserved': 'reserved',
        'Deprecated': 'deprecated',
        'deprecated': 'deprecated',
    }

    VLAN_STATUS_MAP = {
        'Active': 'active',
        'active': 'active',
        'Reserved': 'reserved',
        'reserved': 'reserved',
        'Deprecated': 'deprecated',
        'deprecated': 'deprecated',
    }

    IP_STATUS_MAP = {
        'Active': 'active',
        'active': 'active',
        'Reserved': 'reserved',
        'reserved': 'reserved',
        'Deprecated': 'deprecated',
        'deprecated': 'deprecated',
        'DHCP': 'dhcp',
        'dhcp': 'dhcp',
        'SLAAC': 'slaac',
        'slaac': 'slaac',
    }

    CABLE_STATUS_MAP = {
        'Connected': 'connected',
        'connected': 'connected',
        'Planned': 'planned',
        'planned': 'planned',
        'Decommissioning': 'decommissioning',
        'decommissioning': 'decommissioning',
    }

    @classmethod
    def get_status(cls, obj_type: str, nautobot_status: Any) -> str:
        """Convert Nautobot status to NetBox status."""
        # Handle Nautobot status object format
        if isinstance(nautobot_status, dict):
            status_name = nautobot_status.get('name', nautobot_status.get('value', 'active'))
        else:
            status_name = str(nautobot_status) if nautobot_status else 'active'

        # Get the appropriate mapping
        status_maps = {
            'device': cls.DEVICE_STATUS_MAP,
            'site': cls.SITE_STATUS_MAP,
            'prefix': cls.PREFIX_STATUS_MAP,
            'vlan': cls.VLAN_STATUS_MAP,
            'ip_address': cls.IP_STATUS_MAP,
            'cable': cls.CABLE_STATUS_MAP,
        }

        status_map = status_maps.get(obj_type, cls.DEVICE_STATUS_MAP)
        return status_map.get(status_name, 'active')


class InterfaceTypeMapper:
    """Maps Nautobot interface types to NetBox interface types."""

    TYPE_MAP = {
        # Virtual
        'virtual': 'virtual',
        'bridge': 'bridge',
        'lag': 'lag',
        # Ethernet
        '100base-tx': '100base-tx',
        '1000base-t': '1000base-t',
        '1000base-x-gbic': '1000base-x-gbic',
        '1000base-x-sfp': '1000base-x-sfp',
        '2.5gbase-t': '2.5gbase-t',
        '5gbase-t': '5gbase-t',
        '10gbase-t': '10gbase-t',
        '10gbase-cx4': '10gbase-cx4',
        '10gbase-x-sfpp': '10gbase-x-sfpp',
        '10gbase-x-xfp': '10gbase-x-xfp',
        '10gbase-x-xenpak': '10gbase-x-xenpak',
        '10gbase-x-x2': '10gbase-x-x2',
        '25gbase-x-sfp28': '25gbase-x-sfp28',
        '40gbase-x-qsfpp': '40gbase-x-qsfpp',
        '50gbase-x-sfp28': '50gbase-x-sfp28',
        '100gbase-x-cfp': '100gbase-x-cfp',
        '100gbase-x-cfp2': '100gbase-x-cfp2',
        '100gbase-x-cfp4': '100gbase-x-cfp4',
        '100gbase-x-cpak': '100gbase-x-cpak',
        '100gbase-x-qsfp28': '100gbase-x-qsfp28',
        '200gbase-x-cfp2': '200gbase-x-cfp2',
        '200gbase-x-qsfp56': '200gbase-x-qsfp56',
        '400gbase-x-qsfpdd': '400gbase-x-qsfpdd',
        '400gbase-x-osfp': '400gbase-x-osfp',
        # Other
        'other': 'other',
    }

    @classmethod
    def get_type(cls, nautobot_type: Any) -> str:
        """Convert Nautobot interface type to NetBox interface type."""
        if isinstance(nautobot_type, dict):
            type_value = nautobot_type.get('value', 'other')
        else:
            type_value = str(nautobot_type) if nautobot_type else 'other'

        return cls.TYPE_MAP.get(type_value, 'other')
