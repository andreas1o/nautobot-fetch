from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

"""
NetBox to Nautobot compatibility filter plugin.

Transforms NetBox 4.2+ data structures to match Nautobot format
so that existing Jinja2 templates can work with both platforms.

Key transformations:
- custom_field_data -> cf_fieldname (flattened)
- role -> device_role (for devices)
- assigned_object -> interface (for IP addresses)
- status (string) -> status.name (nested object)
- cable terminations -> connected_interface
"""


def flatten_custom_fields(obj):
    """
    Flatten custom_field_data into cf_* prefixed fields.
    NetBox: {"custom_field_data": {"bgp_asn": "65001", "device_id": 1}}
    Nautobot: {"cf_bgp_asn": "65001", "cf_device_id": 1}
    """
    if not isinstance(obj, dict):
        return obj

    if 'custom_field_data' in obj and isinstance(obj['custom_field_data'], dict):
        for key, value in obj['custom_field_data'].items():
            obj[f'cf_{key}'] = value

    return obj


def transform_status(obj):
    """
    Transform status from string to nested object format.
    NetBox: {"status": "active"}
    Nautobot: {"status": {"name": "Active"}}
    """
    if not isinstance(obj, dict):
        return obj

    if 'status' in obj and isinstance(obj['status'], str):
        obj['status'] = {'name': obj['status'].capitalize()}

    return obj


def transform_device_role(obj):
    """
    Transform role to device_role for compatibility.
    NetBox: {"role": {"name": "spine"}}
    Nautobot: {"device_role": {"name": "spine"}}
    """
    if not isinstance(obj, dict):
        return obj

    if 'role' in obj and 'device_role' not in obj:
        obj['device_role'] = obj['role']

    return obj


def transform_assigned_object(obj):
    """
    Transform assigned_object to interface for IP addresses.
    NetBox: {"assigned_object": {...interface data...}}
    Nautobot: {"interface": {...interface data...}}
    """
    if not isinstance(obj, dict):
        return obj

    if 'assigned_object' in obj and 'interface' not in obj:
        obj['interface'] = obj['assigned_object']

    return obj


def transform_cable_terminations(interface):
    """
    Transform cable terminations to connected_interface.
    NetBox uses cable.a_terminations/b_terminations.
    Nautobot uses connected_interface directly.
    """
    if not isinstance(interface, dict):
        return interface

    if 'cable' in interface and interface['cable']:
        cable = interface['cable']
        connected = None

        # Get a_terminations and b_terminations
        a_terms = cable.get('a_terminations', [])
        b_terms = cable.get('b_terminations', [])

        # Find the remote interface (not our interface)
        current_name = interface.get('name', '')

        for term in a_terms + b_terms:
            if isinstance(term, dict):
                if term.get('name') != current_name:
                    connected = term
                    break

        if connected:
            interface['connected_interface'] = connected

    return interface


def transform_site_asn(site):
    """
    Transform site ASN from list to single value.
    NetBox 4.2+: {"asns": [{"asn": 65001}]}
    Nautobot: {"asn": 65001}
    """
    if not isinstance(site, dict):
        return site

    if 'asns' in site and isinstance(site['asns'], list) and len(site['asns']) > 0:
        site['asn'] = site['asns'][0].get('asn')

    return site


def transform_object(obj):
    """Apply all transformations to an object."""
    if not isinstance(obj, dict):
        return obj

    obj = flatten_custom_fields(obj)
    obj = transform_status(obj)
    obj = transform_device_role(obj)
    obj = transform_assigned_object(obj)

    return obj


def transform_device(device):
    """Transform a device object and its nested interfaces."""
    if not isinstance(device, dict):
        return device

    device = transform_object(device)

    # Transform interfaces
    if 'interfaces' in device and isinstance(device['interfaces'], list):
        for i, interface in enumerate(device['interfaces']):
            device['interfaces'][i] = transform_object(interface)
            device['interfaces'][i] = transform_cable_terminations(interface)

    # Transform uplinks (aliased interfaces)
    if 'uplinks' in device and isinstance(device['uplinks'], list):
        for i, uplink in enumerate(device['uplinks']):
            device['uplinks'][i] = transform_object(uplink)
            device['uplinks'][i] = transform_cable_terminations(uplink)

    # Transform peerlinks
    if 'peerlinks' in device and isinstance(device['peerlinks'], list):
        for i, peerlink in enumerate(device['peerlinks']):
            device['peerlinks'][i] = transform_object(peerlink)

    return device


def transform_virtual_chassis(vc):
    """Transform a virtual_chassis object and its members."""
    if not isinstance(vc, dict):
        return vc

    vc = transform_object(vc)

    if 'members' in vc and isinstance(vc['members'], list):
        for i, member in enumerate(vc['members']):
            vc['members'][i] = transform_device(member)

    return vc


def transform_tenant(tenant):
    """Transform a tenant object with VRFs and VLANs."""
    if not isinstance(tenant, dict):
        return tenant

    tenant = transform_object(tenant)

    # Transform l2vlans
    if 'l2vlans' in tenant and isinstance(tenant['l2vlans'], list):
        for i, vlan in enumerate(tenant['l2vlans']):
            tenant['l2vlans'][i] = transform_object(vlan)

    # Transform VLANs
    if 'vlans' in tenant and isinstance(tenant['vlans'], list):
        for i, vlan in enumerate(tenant['vlans']):
            tenant['vlans'][i] = transform_object(vlan)

    # Transform VRFs
    if 'vrfs' in tenant and isinstance(tenant['vrfs'], list):
        for i, vrf in enumerate(tenant['vrfs']):
            tenant['vrfs'][i] = transform_object(vrf)

            # Transform IP addresses within VRF
            if 'ip_addresses' in vrf and isinstance(vrf['ip_addresses'], list):
                for j, ip in enumerate(vrf['ip_addresses']):
                    tenant['vrfs'][i]['ip_addresses'][j] = transform_object(ip)
                    # Transform interface inside IP address
                    if 'interface' in ip and isinstance(ip['interface'], dict):
                        tenant['vrfs'][i]['ip_addresses'][j]['interface'] = transform_object(ip['interface'])
                        if 'device' in ip['interface']:
                            tenant['vrfs'][i]['ip_addresses'][j]['interface']['device'] = transform_object(ip['interface']['device'])

            # Transform SVIs (prefixes)
            if 'svis' in vrf and isinstance(vrf['svis'], list):
                for j, svi in enumerate(vrf['svis']):
                    tenant['vrfs'][i]['svis'][j] = transform_object(svi)
                    # Transform VLAN inside SVI
                    if 'vlan' in svi and isinstance(svi['vlan'], dict):
                        tenant['vrfs'][i]['svis'][j]['vlan'] = transform_object(svi['vlan'])

    return tenant


def netbox_to_nautobot_devices(devices):
    """
    Transform NetBox device list to Nautobot-compatible format.
    Use this filter on nb_spines, nb_standalone_leafs, etc.
    """
    if not isinstance(devices, list):
        return devices

    return [transform_device(d) for d in devices]


def netbox_to_nautobot_virtual_chassis(virtual_chassis_list):
    """
    Transform NetBox virtual_chassis_list to Nautobot-compatible format.
    Use this filter on nb_mlag_pairs.
    """
    if not isinstance(virtual_chassis_list, list):
        return virtual_chassis_list

    return [transform_virtual_chassis(vc) for vc in virtual_chassis_list]


def netbox_to_nautobot_tenants(tenants):
    """
    Transform NetBox tenant_list to Nautobot-compatible format.
    Use this filter on nb_network_services.
    """
    if not isinstance(tenants, list):
        return tenants

    return [transform_tenant(t) for t in tenants]


def netbox_to_nautobot_sites(sites):
    """
    Transform NetBox site_list to Nautobot-compatible format.
    Use this filter on nb_sites.
    """
    if not isinstance(sites, list):
        return sites

    return [transform_site_asn(s) for s in sites]


def netbox_compat(data, data_type='auto'):
    """
    Main compatibility filter that auto-detects data type.

    Args:
        data: The NetBox data to transform
        data_type: One of 'devices', 'virtual_chassis', 'tenants', 'sites', 'auto'

    Usage in Jinja2:
        {{ nb_spines.device_list | netbox_compat('devices') }}
        {{ nb_mlag_pairs.virtual_chassis_list | netbox_compat('virtual_chassis') }}
    """
    if data_type == 'devices':
        return netbox_to_nautobot_devices(data)
    elif data_type == 'virtual_chassis':
        return netbox_to_nautobot_virtual_chassis(data)
    elif data_type == 'tenants':
        return netbox_to_nautobot_tenants(data)
    elif data_type == 'sites':
        return netbox_to_nautobot_sites(data)
    elif data_type == 'auto':
        # Try to auto-detect based on structure
        if isinstance(data, list) and len(data) > 0:
            sample = data[0]
            if isinstance(sample, dict):
                if 'members' in sample:
                    return netbox_to_nautobot_virtual_chassis(data)
                elif 'vrfs' in sample or 'vlans' in sample:
                    return netbox_to_nautobot_tenants(data)
                elif 'asns' in sample:
                    return netbox_to_nautobot_sites(data)
                else:
                    return netbox_to_nautobot_devices(data)

    return data


class FilterModule(object):
    """Ansible filter plugin for NetBox to Nautobot compatibility."""

    def filters(self):
        return {
            'netbox_compat': netbox_compat,
            'netbox_to_nautobot_devices': netbox_to_nautobot_devices,
            'netbox_to_nautobot_virtual_chassis': netbox_to_nautobot_virtual_chassis,
            'netbox_to_nautobot_tenants': netbox_to_nautobot_tenants,
            'netbox_to_nautobot_sites': netbox_to_nautobot_sites,
        }
