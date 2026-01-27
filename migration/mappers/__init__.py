# Object mappers for Nautobot to NetBox migration
from .base import BaseMapper
from .dcim import (
    TagMapper,
    RegionMapper,
    SiteMapper,
    ManufacturerMapper,
    DeviceTypeMapper,
    DeviceRoleMapper,
    PlatformMapper,
    RackMapper,
    DeviceMapper,
    InterfaceMapper,
    CableMapper,
    VirtualChassisMapper,
)
from .ipam import (
    VLANGroupMapper,
    VLANMapper,
    VRFMapper,
    PrefixMapper,
    IPAddressMapper,
)
from .tenancy import TenantMapper
from .extras import CustomFieldMapper, ConfigContextMapper

__all__ = [
    'BaseMapper',
    'TagMapper',
    'RegionMapper',
    'SiteMapper',
    'ManufacturerMapper',
    'DeviceTypeMapper',
    'DeviceRoleMapper',
    'PlatformMapper',
    'RackMapper',
    'DeviceMapper',
    'InterfaceMapper',
    'CableMapper',
    'VirtualChassisMapper',
    'VLANGroupMapper',
    'VLANMapper',
    'VRFMapper',
    'PrefixMapper',
    'IPAddressMapper',
    'TenantMapper',
    'CustomFieldMapper',
    'ConfigContextMapper',
]
