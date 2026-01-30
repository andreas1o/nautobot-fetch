#!/usr/bin/env python3
"""
Nautobot to NetBox Migration Tool

Migrates data from Nautobot 1.6+ to NetBox 4.2.9+

Usage:
    python migrate.py --config config.yaml
    python migrate.py --config config.yaml --dry-run
    python migrate.py --config config.yaml --objects tags,sites,devices
"""

import argparse
import logging
import sys
import yaml
import urllib3
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

# Suppress SSL warnings when verify_ssl is disabled in config
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from lib import NautobotClient, NetBoxClient, IDMapper
from lib.id_mapper import StatusMapper
from mappers import (
    TagMapper, RegionMapper, SiteMapper, ManufacturerMapper,
    DeviceTypeMapper, DeviceRoleMapper, PlatformMapper, RackMapper,
    DeviceMapper, InterfaceMapper, CableMapper, VirtualChassisMapper,
    VLANGroupMapper, VLANMapper, VRFMapper, PrefixMapper, IPAddressMapper,
    TenantMapper, CustomFieldMapper, ConfigContextMapper,
)
from mappers.tenancy import TenantGroupMapper
from mappers.ipam import RouteTargetMapper

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('migration')


class MigrationRunner:
    """Orchestrates the migration from Nautobot to NetBox."""

    # Migration order respects foreign key dependencies
    MIGRATION_ORDER = [
        'tags',
        'custom_fields',
        'tenant_groups',
        'tenants',
        'regions',
        'sites',
        'manufacturers',
        'device_types',
        'device_roles',
        'platforms',
        'rack_groups',
        'racks',
        'vlan_groups',
        'route_targets',
        'vrf',
        'vlans',
        'prefixes',
        'devices',
        'interfaces',
        'ip_addresses',
        'cables',
        'virtual_chassis',
        'config_contexts',
    ]

    def __init__(self, config: Dict):
        self.config = config
        self.dry_run = config.get('migration', {}).get('dry_run', False)
        self.continue_on_error = config.get('migration', {}).get('continue_on_error', True)
        self.custom_field_mapping = config.get('migration', {}).get('custom_field_mapping', {})

        # Initialize clients
        nautobot_cfg = config['nautobot']
        netbox_cfg = config['netbox']

        self.nautobot = NautobotClient(
            url=nautobot_cfg['url'],
            token=nautobot_cfg['token'],
            verify_ssl=nautobot_cfg.get('verify_ssl', True)
        )

        self.netbox = NetBoxClient(
            url=netbox_cfg['url'],
            token=netbox_cfg['token'],
            verify_ssl=netbox_cfg.get('verify_ssl', True),
            dry_run=self.dry_run
        )

        # Initialize ID mapper
        self.id_mapper = IDMapper(cache_file='id_mapping.json')

        # Statistics
        self.stats = {
            'created': {},
            'skipped': {},
            'failed': {},
        }

    def test_connections(self) -> bool:
        """Test connections to both Nautobot and NetBox."""
        logger.info("Testing connections...")

        if not self.nautobot.test_connection():
            logger.error("Failed to connect to Nautobot")
            return False

        if not self.netbox.test_connection():
            logger.error("Failed to connect to NetBox")
            return False

        logger.info("Connections verified successfully")
        return True

    def run(self, objects: Optional[List[str]] = None):
        """Run the migration."""
        start_time = datetime.now()
        logger.info(f"Starting migration at {start_time}")

        if self.dry_run:
            logger.warning("DRY RUN MODE - No changes will be made to NetBox")

        # Determine which objects to migrate
        if objects:
            migration_objects = [o for o in self.MIGRATION_ORDER if o in objects]
        else:
            configured_objects = self.config.get('migration', {}).get('objects', self.MIGRATION_ORDER)
            migration_objects = [o for o in self.MIGRATION_ORDER if o in configured_objects]

        logger.info(f"Migration order: {migration_objects}")

        # Run migrations in order
        for obj_type in migration_objects:
            try:
                self._migrate_object_type(obj_type)
            except Exception as e:
                logger.error(f"Failed to migrate {obj_type}: {e}")
                if not self.continue_on_error:
                    raise

        # Save ID mapping
        self.id_mapper.save_cache()

        # Print summary
        end_time = datetime.now()
        duration = end_time - start_time
        self._print_summary(duration)

    def _migrate_object_type(self, obj_type: str):
        """Migrate a specific object type."""
        logger.info(f"Migrating {obj_type}...")

        migrate_method = getattr(self, f'_migrate_{obj_type}', None)
        if not migrate_method:
            logger.warning(f"No migration method for {obj_type}")
            return

        migrate_method()

    def _migrate_tags(self):
        """Migrate tags."""
        mapper = TagMapper(self.id_mapper, self.custom_field_mapping)
        nautobot_tags = self.nautobot.get_tags()

        # Get existing tags in NetBox to avoid duplicates
        existing_tags = {t['slug']: t for t in self.netbox.get_tags()}

        created, skipped, failed = 0, 0, 0
        for nb_tag in nautobot_tags:
            try:
                slug = mapper._get_slug(nb_tag)
                if slug in existing_tags:
                    # Map to existing
                    self.id_mapper.add('tag', nb_tag['id'], existing_tags[slug]['id'])
                    skipped += 1
                    continue

                data = mapper.transform(nb_tag)
                result = self.netbox.create_tag(data)
                if result:
                    mapper.register_mapping(nb_tag['id'], result['id'])
                    created += 1
            except Exception as e:
                logger.error(f"Failed to migrate tag {nb_tag.get('name')}: {e}")
                failed += 1
                if not self.continue_on_error:
                    raise

        self._update_stats('tags', created, skipped, failed)

    def _migrate_custom_fields(self):
        """Migrate custom fields.

        NetBox 4.x requires choice sets to be created BEFORE select-type custom fields.
        """
        mapper = CustomFieldMapper(self.id_mapper, self.custom_field_mapping)
        nautobot_cfs = self.nautobot.get_custom_fields()

        # Get existing custom fields in NetBox
        existing_cfs = {cf['name']: cf for cf in self.netbox.get_custom_fields()}

        # Get existing choice sets in NetBox
        existing_choice_sets = {}
        try:
            for cs in self.netbox._get('extras/custom-field-choice-sets'):
                existing_choice_sets[cs['name']] = cs
        except Exception:
            pass  # Endpoint may not exist in older versions

        created, skipped, failed = 0, 0, 0

        # First pass: Create choice sets for select/multiselect fields
        for nb_cf in nautobot_cfs:
            try:
                if not mapper.is_select_type(nb_cf):
                    continue

                choices_data = mapper.get_choices(nb_cf)
                if not choices_data:
                    continue

                choice_set_name = choices_data['name']
                if choice_set_name in existing_choice_sets:
                    # Use existing choice set
                    mapper.set_choice_set_id(nb_cf.get('name'), existing_choice_sets[choice_set_name]['id'])
                    logger.debug(f"Using existing choice set: {choice_set_name}")
                else:
                    # Create new choice set
                    result = self.netbox.create_custom_field_choice(choices_data)
                    if result:
                        mapper.set_choice_set_id(nb_cf.get('name'), result['id'])
                        logger.debug(f"Created choice set: {choice_set_name} -> {result['id']}")
            except Exception as e:
                logger.warning(f"Failed to create choice set for {nb_cf.get('name')}: {e}")

        # Second pass: Create custom fields (now with choice_set references)
        for nb_cf in nautobot_cfs:
            try:
                name = nb_cf.get('name')
                if name in existing_cfs:
                    self.id_mapper.add('custom_field', nb_cf['id'], existing_cfs[name]['id'])
                    skipped += 1
                    continue

                data = mapper.transform(nb_cf)
                result = self.netbox.create_custom_field(data)
                if result:
                    mapper.register_mapping(nb_cf['id'], result['id'])
                    created += 1
            except Exception as e:
                logger.error(f"Failed to migrate custom field {nb_cf.get('name')}: {e}")
                failed += 1
                if not self.continue_on_error:
                    raise

        self._update_stats('custom_fields', created, skipped, failed)

    def _migrate_tenant_groups(self):
        """Migrate tenant groups."""
        mapper = TenantGroupMapper(self.id_mapper, self.custom_field_mapping)
        nautobot_groups = self.nautobot.get_tenant_groups()

        created, skipped, failed = 0, 0, 0
        # Sort by hierarchy level (parents first)
        sorted_groups = sorted(nautobot_groups, key=lambda x: x.get('_depth', 0) if x.get('_depth') else 0)

        for nb_group in sorted_groups:
            try:
                data = mapper.transform(nb_group)
                result = self.netbox.create_tenant_group(data)
                if result:
                    mapper.register_mapping(nb_group['id'], result['id'])
                    created += 1
            except Exception as e:
                logger.error(f"Failed to migrate tenant group {nb_group.get('name')}: {e}")
                failed += 1

        self._update_stats('tenant_groups', created, skipped, failed)

    def _migrate_tenants(self):
        """Migrate tenants."""
        mapper = TenantMapper(self.id_mapper, self.custom_field_mapping)
        nautobot_tenants = self.nautobot.get_tenants()

        existing_tenants = {t['slug']: t for t in self.netbox.get_tenants()}

        created, skipped, failed = 0, 0, 0
        for nb_tenant in nautobot_tenants:
            try:
                slug = mapper._get_slug(nb_tenant)
                if slug in existing_tenants:
                    self.id_mapper.add('tenant', nb_tenant['id'], existing_tenants[slug]['id'])
                    skipped += 1
                    continue

                data = mapper.transform(nb_tenant)
                result = self.netbox.create_tenant(data)
                if result:
                    mapper.register_mapping(nb_tenant['id'], result['id'])
                    created += 1
            except Exception as e:
                logger.error(f"Failed to migrate tenant {nb_tenant.get('name')}: {e}")
                failed += 1

        self._update_stats('tenants', created, skipped, failed)

    def _migrate_regions(self):
        """Migrate regions."""
        mapper = RegionMapper(self.id_mapper, self.custom_field_mapping)
        nautobot_regions = self.nautobot.get_regions()

        existing_regions = {r['slug']: r for r in self.netbox.get_regions()}

        created, skipped, failed = 0, 0, 0
        # Sort by hierarchy level (parents first)
        sorted_regions = sorted(nautobot_regions, key=lambda x: x.get('_depth', 0) if x.get('_depth') else 0)

        for nb_region in sorted_regions:
            try:
                slug = mapper._get_slug(nb_region)
                if slug in existing_regions:
                    self.id_mapper.add('region', nb_region['id'], existing_regions[slug]['id'])
                    skipped += 1
                    continue

                data = mapper.transform(nb_region)
                result = self.netbox.create_region(data)
                if result:
                    mapper.register_mapping(nb_region['id'], result['id'])
                    created += 1
            except Exception as e:
                logger.error(f"Failed to migrate region {nb_region.get('name')}: {e}")
                failed += 1

        self._update_stats('regions', created, skipped, failed)

    def _migrate_sites(self):
        """Migrate sites."""
        mapper = SiteMapper(self.id_mapper, self.custom_field_mapping)
        nautobot_sites = self.nautobot.get_sites()

        existing_sites = {s['slug']: s for s in self.netbox.get_sites()}

        created, skipped, failed = 0, 0, 0
        for nb_site in nautobot_sites:
            try:
                slug = mapper._get_slug(nb_site)
                if slug in existing_sites:
                    self.id_mapper.add('site', nb_site['id'], existing_sites[slug]['id'])
                    skipped += 1
                    continue

                data = mapper.transform(nb_site)
                result = self.netbox.create_site(data)
                if result:
                    mapper.register_mapping(nb_site['id'], result['id'])
                    created += 1
            except Exception as e:
                logger.error(f"Failed to migrate site {nb_site.get('name')}: {e}")
                failed += 1

        self._update_stats('sites', created, skipped, failed)

    def _migrate_manufacturers(self):
        """Migrate manufacturers."""
        mapper = ManufacturerMapper(self.id_mapper, self.custom_field_mapping)
        nautobot_mfrs = self.nautobot.get_manufacturers()

        existing_mfrs = {m['slug']: m for m in self.netbox.get_manufacturers()}

        created, skipped, failed = 0, 0, 0
        for nb_mfr in nautobot_mfrs:
            try:
                slug = mapper._get_slug(nb_mfr)
                if slug in existing_mfrs:
                    self.id_mapper.add('manufacturer', nb_mfr['id'], existing_mfrs[slug]['id'])
                    skipped += 1
                    continue

                data = mapper.transform(nb_mfr)
                result = self.netbox.create_manufacturer(data)
                if result:
                    mapper.register_mapping(nb_mfr['id'], result['id'])
                    created += 1
            except Exception as e:
                logger.error(f"Failed to migrate manufacturer {nb_mfr.get('name')}: {e}")
                failed += 1

        self._update_stats('manufacturers', created, skipped, failed)

    def _migrate_device_types(self):
        """Migrate device types."""
        mapper = DeviceTypeMapper(self.id_mapper, self.custom_field_mapping)
        nautobot_types = self.nautobot.get_device_types()

        existing_types = {dt['slug']: dt for dt in self.netbox.get_device_types()}

        created, skipped, failed = 0, 0, 0
        for nb_type in nautobot_types:
            try:
                slug = mapper._get_slug(nb_type)
                if slug in existing_types:
                    self.id_mapper.add('device_type', nb_type['id'], existing_types[slug]['id'])
                    skipped += 1
                    continue

                data = mapper.transform(nb_type)
                result = self.netbox.create_device_type(data)
                if result:
                    mapper.register_mapping(nb_type['id'], result['id'])
                    created += 1
            except Exception as e:
                logger.error(f"Failed to migrate device type {nb_type.get('model')}: {e}")
                failed += 1

        self._update_stats('device_types', created, skipped, failed)

    def _migrate_device_roles(self):
        """Migrate device roles."""
        mapper = DeviceRoleMapper(self.id_mapper, self.custom_field_mapping)
        nautobot_roles = self.nautobot.get_device_roles()

        existing_roles = {r['slug']: r for r in self.netbox.get_device_roles()}

        created, skipped, failed = 0, 0, 0
        for nb_role in nautobot_roles:
            try:
                slug = mapper._get_slug(nb_role)
                if slug in existing_roles:
                    self.id_mapper.add('device_role', nb_role['id'], existing_roles[slug]['id'])
                    skipped += 1
                    continue

                data = mapper.transform(nb_role)
                result = self.netbox.create_device_role(data)
                if result:
                    mapper.register_mapping(nb_role['id'], result['id'])
                    created += 1
            except Exception as e:
                logger.error(f"Failed to migrate device role {nb_role.get('name')}: {e}")
                failed += 1

        self._update_stats('device_roles', created, skipped, failed)

    def _migrate_platforms(self):
        """Migrate platforms."""
        mapper = PlatformMapper(self.id_mapper, self.custom_field_mapping)
        nautobot_platforms = self.nautobot.get_platforms()

        existing_platforms = {p['slug']: p for p in self.netbox.get_platforms()}

        created, skipped, failed = 0, 0, 0
        for nb_platform in nautobot_platforms:
            try:
                slug = mapper._get_slug(nb_platform)
                if slug in existing_platforms:
                    self.id_mapper.add('platform', nb_platform['id'], existing_platforms[slug]['id'])
                    skipped += 1
                    continue

                data = mapper.transform(nb_platform)
                result = self.netbox.create_platform(data)
                if result:
                    mapper.register_mapping(nb_platform['id'], result['id'])
                    created += 1
            except Exception as e:
                logger.error(f"Failed to migrate platform {nb_platform.get('name')}: {e}")
                failed += 1

        self._update_stats('platforms', created, skipped, failed)

    def _migrate_rack_groups(self):
        """Migrate rack groups (as locations in NetBox 4.x)."""
        # In NetBox 4.x, rack groups are replaced by locations
        nautobot_groups = self.nautobot.get_rack_groups()

        created, skipped, failed = 0, 0, 0
        for nb_group in nautobot_groups:
            try:
                data = {
                    'name': nb_group.get('name'),
                    'slug': nb_group.get('slug', nb_group.get('name', '').lower().replace(' ', '-')),
                }
                # Site is required
                site_id = self.id_mapper.get_netbox_id('site', nb_group.get('site', {}).get('id'))
                if site_id:
                    data['site'] = site_id

                result = self.netbox.create_location(data)
                if result:
                    self.id_mapper.add('location', nb_group['id'], result['id'])
                    created += 1
            except Exception as e:
                logger.error(f"Failed to migrate rack group {nb_group.get('name')}: {e}")
                failed += 1

        self._update_stats('rack_groups', created, skipped, failed)

    def _migrate_racks(self):
        """Migrate racks."""
        mapper = RackMapper(self.id_mapper, self.custom_field_mapping)
        nautobot_racks = self.nautobot.get_racks()

        created, skipped, failed = 0, 0, 0
        for nb_rack in nautobot_racks:
            try:
                data = mapper.transform(nb_rack)
                result = self.netbox.create_rack(data)
                if result:
                    mapper.register_mapping(nb_rack['id'], result['id'])
                    created += 1
            except Exception as e:
                logger.error(f"Failed to migrate rack {nb_rack.get('name')}: {e}")
                failed += 1

        self._update_stats('racks', created, skipped, failed)

    def _migrate_vlan_groups(self):
        """Migrate VLAN groups."""
        mapper = VLANGroupMapper(self.id_mapper, self.custom_field_mapping)
        nautobot_groups = self.nautobot.get_vlan_groups()

        existing_groups = {g['slug']: g for g in self.netbox.get_vlan_groups()}

        created, skipped, failed = 0, 0, 0
        for nb_group in nautobot_groups:
            try:
                slug = mapper._get_slug(nb_group)
                if slug in existing_groups:
                    self.id_mapper.add('vlan_group', nb_group['id'], existing_groups[slug]['id'])
                    skipped += 1
                    continue

                data = mapper.transform(nb_group)
                result = self.netbox.create_vlan_group(data)
                if result:
                    mapper.register_mapping(nb_group['id'], result['id'])
                    created += 1
            except Exception as e:
                logger.error(f"Failed to migrate VLAN group {nb_group.get('name')}: {e}")
                failed += 1

        self._update_stats('vlan_groups', created, skipped, failed)

    def _migrate_route_targets(self):
        """Migrate route targets."""
        mapper = RouteTargetMapper(self.id_mapper, self.custom_field_mapping)
        nautobot_rts = self.nautobot.get_route_targets()

        created, skipped, failed = 0, 0, 0
        for nb_rt in nautobot_rts:
            try:
                data = mapper.transform(nb_rt)
                result = self.netbox.create_route_target(data)
                if result:
                    mapper.register_mapping(nb_rt['id'], result['id'])
                    created += 1
            except Exception as e:
                logger.error(f"Failed to migrate route target {nb_rt.get('name')}: {e}")
                failed += 1

        self._update_stats('route_targets', created, skipped, failed)

    def _migrate_vrf(self):
        """Migrate VRFs."""
        mapper = VRFMapper(self.id_mapper, self.custom_field_mapping)
        nautobot_vrfs = self.nautobot.get_vrf()

        existing_vrfs = {v['name']: v for v in self.netbox.get_vrfs()}

        created, skipped, failed = 0, 0, 0
        for nb_vrf in nautobot_vrfs:
            try:
                name = nb_vrf.get('name')
                if name in existing_vrfs:
                    self.id_mapper.add('vrf', nb_vrf['id'], existing_vrfs[name]['id'])
                    skipped += 1
                    continue

                data = mapper.transform(nb_vrf)
                result = self.netbox.create_vrf(data)
                if result:
                    mapper.register_mapping(nb_vrf['id'], result['id'])
                    created += 1
            except Exception as e:
                logger.error(f"Failed to migrate VRF {nb_vrf.get('name')}: {e}")
                failed += 1

        self._update_stats('vrf', created, skipped, failed)

    def _migrate_vlans(self):
        """Migrate VLANs."""
        mapper = VLANMapper(self.id_mapper, self.custom_field_mapping)
        nautobot_vlans = self.nautobot.get_vlans()

        created, skipped, failed = 0, 0, 0
        for nb_vlan in nautobot_vlans:
            try:
                data = mapper.transform(nb_vlan)
                result = self.netbox.create_vlan(data)
                if result:
                    mapper.register_mapping(nb_vlan['id'], result['id'])
                    created += 1
            except Exception as e:
                logger.error(f"Failed to migrate VLAN {nb_vlan.get('name')}: {e}")
                failed += 1

        self._update_stats('vlans', created, skipped, failed)

    def _migrate_prefixes(self):
        """Migrate prefixes."""
        mapper = PrefixMapper(self.id_mapper, self.custom_field_mapping)
        nautobot_prefixes = self.nautobot.get_prefixes()

        created, skipped, failed = 0, 0, 0
        for nb_prefix in nautobot_prefixes:
            try:
                data = mapper.transform(nb_prefix)
                if not data:
                    skipped += 1
                    continue

                result = self.netbox.create_prefix(data)
                if result:
                    mapper.register_mapping(nb_prefix['id'], result['id'])
                    created += 1
            except Exception as e:
                logger.error(f"Failed to migrate prefix {nb_prefix.get('prefix')}: {e}")
                failed += 1

        self._update_stats('prefixes', created, skipped, failed)

    def _migrate_devices(self):
        """Migrate devices."""
        mapper = DeviceMapper(self.id_mapper, self.custom_field_mapping)
        nautobot_devices = self.nautobot.get_devices()

        existing_devices = {d['name']: d for d in self.netbox.get_devices()}

        created, skipped, failed = 0, 0, 0
        for nb_device in nautobot_devices:
            try:
                name = nb_device.get('name')
                if name in existing_devices:
                    self.id_mapper.add('device', nb_device['id'], existing_devices[name]['id'])
                    skipped += 1
                    continue

                data = mapper.transform(nb_device)
                result = self.netbox.create_device(data)
                if result:
                    mapper.register_mapping(nb_device['id'], result['id'])
                    created += 1
            except Exception as e:
                logger.error(f"Failed to migrate device {nb_device.get('name')}: {e}")
                failed += 1

        self._update_stats('devices', created, skipped, failed)

    def _migrate_interfaces(self):
        """Migrate interfaces."""
        mapper = InterfaceMapper(self.id_mapper, self.custom_field_mapping)
        nautobot_interfaces = self.nautobot.get_interfaces()

        # Build lookup of existing interfaces in NetBox (device_id, name) -> interface
        existing_interfaces = {}
        for iface in self.netbox.get_interfaces():
            device = iface.get('device')
            if device:
                device_id = device.get('id') if isinstance(device, dict) else device
                key = (device_id, iface.get('name'))
                existing_interfaces[key] = iface

        created, skipped, failed = 0, 0, 0

        def process_interface(nb_iface):
            """Process a single interface, returning (created, skipped, failed) counts."""
            nonlocal created, skipped, failed
            try:
                # Get the NetBox device ID for this interface
                nb_device = nb_iface.get('device', {})
                nautobot_device_id = nb_device.get('id') if isinstance(nb_device, dict) else nb_device
                netbox_device_id = self.id_mapper.get_netbox_id('device', nautobot_device_id)

                if netbox_device_id:
                    # Check if interface already exists
                    key = (netbox_device_id, nb_iface.get('name'))
                    if key in existing_interfaces:
                        existing_iface = existing_interfaces[key]
                        self.id_mapper.add('interface', nb_iface['id'], existing_iface['id'])
                        skipped += 1
                        return

                data = mapper.transform(nb_iface)
                result = self.netbox.create_interface(data)
                if result:
                    mapper.register_mapping(nb_iface['id'], result['id'])
                    created += 1
            except Exception as e:
                logger.error(f"Failed to migrate interface {nb_iface.get('name')}: {e}")
                failed += 1

        # First pass: Create LAG interfaces
        lag_interfaces = [i for i in nautobot_interfaces if i.get('type', {}).get('value') == 'lag']
        for nb_iface in lag_interfaces:
            process_interface(nb_iface)

        # Second pass: Create other interfaces
        other_interfaces = [i for i in nautobot_interfaces if i.get('type', {}).get('value') != 'lag']
        for nb_iface in other_interfaces:
            process_interface(nb_iface)

        self._update_stats('interfaces', created, skipped, failed)

    def _migrate_ip_addresses(self):
        """Migrate IP addresses."""
        mapper = IPAddressMapper(self.id_mapper, self.custom_field_mapping)
        nautobot_ips = self.nautobot.get_ip_addresses()

        created, skipped, failed = 0, 0, 0
        for nb_ip in nautobot_ips:
            try:
                data = mapper.transform(nb_ip)
                if not data:
                    skipped += 1
                    continue

                result = self.netbox.create_ip_address(data)
                if result:
                    mapper.register_mapping(nb_ip['id'], result['id'])
                    created += 1
            except Exception as e:
                logger.error(f"Failed to migrate IP address {nb_ip.get('address')}: {e}")
                failed += 1

        self._update_stats('ip_addresses', created, skipped, failed)

    def _migrate_cables(self):
        """Migrate cables."""
        mapper = CableMapper(self.id_mapper, self.custom_field_mapping)
        nautobot_cables = self.nautobot.get_cables()

        created, skipped, failed = 0, 0, 0
        for nb_cable in nautobot_cables:
            try:
                data = mapper.transform(nb_cable)
                # Skip if terminations couldn't be resolved
                if 'a_terminations' not in data or 'b_terminations' not in data:
                    skipped += 1
                    continue

                result = self.netbox.create_cable(data)
                if result:
                    mapper.register_mapping(nb_cable['id'], result['id'])
                    created += 1
            except Exception as e:
                logger.error(f"Failed to migrate cable {nb_cable.get('id')}: {e}")
                failed += 1

        self._update_stats('cables', created, skipped, failed)

    def _migrate_virtual_chassis(self):
        """Migrate virtual chassis."""
        mapper = VirtualChassisMapper(self.id_mapper, self.custom_field_mapping)
        nautobot_vcs = self.nautobot.get_virtual_chassis()

        created, skipped, failed = 0, 0, 0
        for nb_vc in nautobot_vcs:
            try:
                data = mapper.transform(nb_vc)
                result = self.netbox.create_virtual_chassis(data)
                if result:
                    mapper.register_mapping(nb_vc['id'], result['id'])
                    created += 1

                    # Update member devices
                    members = mapper.get_member_devices(nb_vc)
                    for member in members:
                        try:
                            self.netbox.update_device(member['device_id'], {
                                'virtual_chassis': result['id'],
                                'vc_position': member.get('vc_position'),
                                'vc_priority': member.get('vc_priority'),
                            })
                        except Exception as e:
                            logger.warning(f"Failed to update VC member: {e}")
            except Exception as e:
                logger.error(f"Failed to migrate virtual chassis {nb_vc.get('name')}: {e}")
                failed += 1

        self._update_stats('virtual_chassis', created, skipped, failed)

    def _migrate_config_contexts(self):
        """Migrate config contexts."""
        mapper = ConfigContextMapper(self.id_mapper, self.custom_field_mapping)
        nautobot_contexts = self.nautobot.get_config_contexts()

        existing_contexts = {c['name']: c for c in self.netbox.get_config_contexts()}

        created, skipped, failed = 0, 0, 0
        for nb_ctx in nautobot_contexts:
            try:
                name = nb_ctx.get('name')
                if name in existing_contexts:
                    self.id_mapper.add('config_context', nb_ctx['id'], existing_contexts[name]['id'])
                    skipped += 1
                    continue

                data = mapper.transform(nb_ctx)
                result = self.netbox.create_config_context(data)
                if result:
                    mapper.register_mapping(nb_ctx['id'], result['id'])
                    created += 1
            except Exception as e:
                logger.error(f"Failed to migrate config context {nb_ctx.get('name')}: {e}")
                failed += 1

        self._update_stats('config_contexts', created, skipped, failed)

    def _update_stats(self, obj_type: str, created: int, skipped: int, failed: int):
        """Update migration statistics."""
        self.stats['created'][obj_type] = created
        self.stats['skipped'][obj_type] = skipped
        self.stats['failed'][obj_type] = failed
        logger.info(f"  {obj_type}: {created} created, {skipped} skipped, {failed} failed")

    def _print_summary(self, duration):
        """Print migration summary."""
        print("\n" + "=" * 60)
        print("MIGRATION SUMMARY")
        print("=" * 60)

        total_created = sum(self.stats['created'].values())
        total_skipped = sum(self.stats['skipped'].values())
        total_failed = sum(self.stats['failed'].values())

        print(f"\nDuration: {duration}")
        print(f"Total objects created: {total_created}")
        print(f"Total objects skipped: {total_skipped}")
        print(f"Total objects failed: {total_failed}")

        print("\nBy object type:")
        print("-" * 40)
        for obj_type in self.MIGRATION_ORDER:
            created = self.stats['created'].get(obj_type, 0)
            skipped = self.stats['skipped'].get(obj_type, 0)
            failed = self.stats['failed'].get(obj_type, 0)
            if created or skipped or failed:
                print(f"  {obj_type:20} | {created:5} created | {skipped:5} skipped | {failed:5} failed")

        print("\nID mapping summary:")
        for obj_type, count in self.id_mapper.summary().items():
            print(f"  {obj_type}: {count} mappings")

        print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description='Migrate data from Nautobot to NetBox'
    )
    parser.add_argument(
        '--config', '-c',
        required=True,
        help='Path to configuration file'
    )
    parser.add_argument(
        '--dry-run', '-n',
        action='store_true',
        help='Dry run mode - no changes will be made'
    )
    parser.add_argument(
        '--objects', '-o',
        help='Comma-separated list of object types to migrate'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )

    args = parser.parse_args()

    # Set log level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Load configuration
    config_path = Path(args.config)
    if not config_path.exists():
        logger.error(f"Configuration file not found: {config_path}")
        sys.exit(1)

    with open(config_path) as f:
        config = yaml.safe_load(f)

    # Override dry run from command line
    if args.dry_run:
        config.setdefault('migration', {})['dry_run'] = True

    # Parse objects to migrate
    objects = None
    if args.objects:
        objects = [o.strip() for o in args.objects.split(',')]

    # Run migration
    runner = MigrationRunner(config)

    if not runner.test_connections():
        sys.exit(1)

    runner.run(objects)


if __name__ == '__main__':
    main()
