# NetBox Migration Guide

This document describes how to use this library with NetBox 4.2.9 instead of Nautobot 1.6.

## Overview

The library has been extended to support both Nautobot and NetBox as data sources. A new `netbox-sync` role has been created that fetches data from NetBox's GraphQL API and transforms it into a format compatible with the existing `avdbuilder` role.

## Key Differences Between Nautobot 1.6 and NetBox 4.2.9

### GraphQL Query Syntax

| Aspect | Nautobot 1.6 | NetBox 4.2.9 |
|--------|--------------|--------------|
| Root queries | `devices(...)`, `tenants(...)` | `device_list(...)`, `tenant_list(...)` |
| Filtering | `devices(role:"spine")` | `device_list(filters: {role: "spine"})` |
| Tag filtering | `tag: "avd"` | `tag: ["avd"]` |
| Custom fields | `cf_fieldname` | `custom_field_data` object |
| Status field | `status { name }` | `status` (string) |

### Data Model Differences

| Model/Field | Nautobot 1.6 | NetBox 4.2.9 |
|-------------|--------------|--------------|
| Primary Keys | UUIDs | Integers |
| Device Role | `device_role { name }` | `role { name }` |
| Interface connection | `connected_interface` | `cable.terminations` |
| Site ASN | `site.asn` | `site.asns[].asn` |

## Setup for NetBox

### 1. Configure Inventory

Edit `inventory_netbox.yml`:

```yaml
all:
  children:
    NETBOX:
      hosts:
        netbox:
          ansible_host: netbox.example.com
          netbox_url: "https://netbox.example.com"
          netbox_api_token: "your-api-token-here"
          netbox_validate_certs: true
```

### 2. Run the Playbook

```bash
ansible-playbook -i inventory_netbox.yml PLAY_avdbuilder_netbox.yml
```

## Required NetBox Custom Fields

Create the following custom fields in NetBox (Admin → Custom Fields):

### Device Custom Fields

| Name | Type | Object Types | Description |
|------|------|--------------|-------------|
| `bgp_asn` | Text | Device | BGP AS number |
| `device_id` | Integer | Device | Device ID (1-254) |
| `evpn_role` | Selection | Device | EVPN role: `client`, `server`, `none` |
| `route_map_in` | Text | Device | Inbound route-map name |
| `route_map_out` | Text | Device | Outbound route-map name |
| `bgp_password` | Text | Device | BGP peer password |
| `default_originate` | Selection | Device | Default originate: `on`, `always`, `off` |
| `local_as` | Text | Device | Local AS number |
| `bfd` | Boolean | Device | Enable BFD |

### VRF Custom Fields

| Name | Type | Object Types | Description |
|------|------|--------------|-------------|
| `ospf_enabled` | Boolean | VRF | Enable OSPF in VRF |
| `mlag_ibgp_peering` | Boolean | VRF | Enable MLAG iBGP peering |
| `mlag_ibgp_peering_vlan` | Integer | VRF | MLAG iBGP peering VLAN |

### VLAN Custom Fields

| Name | Type | Object Types | Description |
|------|------|--------------|-------------|
| `ospf_enabled` | Boolean | VLAN | Enable OSPF on SVI |
| `ip_helpers` | Text | VLAN | Comma-separated IP helpers |
| `mtu` | Integer | VLAN | SVI MTU |
| `vxlan_enable` | Boolean | VLAN | Enable VXLAN for VLAN |

### Interface Custom Fields

| Name | Type | Object Types | Description |
|------|------|--------------|-------------|
| `raw_eos_cli` | Text | Interface | Raw EOS CLI configuration |
| `speed` | Text | Interface | Interface speed |
| `ospf_enabled` | Boolean | Interface | Enable OSPF on interface |

### Prefix Custom Fields

| Name | Type | Object Types | Description |
|------|------|--------------|-------------|
| `next_hop` | Text | Prefix | Static route next-hop |

### IP Address Custom Fields

| Name | Type | Object Types | Description |
|------|------|--------------|-------------|
| `is_default_route` | Boolean | IP Address | Use as default route gateway |

### Tenant Custom Fields

| Name | Type | Object Types | Description |
|------|------|--------------|-------------|
| `base_vni` | Integer | Tenant | MAC VRF VNI base |

## Required Tags

Create the following tags in NetBox:

- `avd` - Marks objects for AVD processing (required on devices, VLANs, VRFs, tenants, prefixes)
- `uplink` - Marks uplink interfaces
- `peerlink` - Marks MLAG peer-link interfaces
- `routing_policy` - Marks objects with routing policies

## Required Device Roles

- `spine` - Spine switches
- `l3leaf` - Layer 3 leaf switches
- `l2leaf` - Layer 2 leaf switches
- `bgp_peer` - External BGP peer devices

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  NetBox 4.2.9   │────▶│  netbox-sync     │────▶│  avdbuilder     │
│  GraphQL API    │     │  role            │     │  role           │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                               │
                               ▼
                        ┌──────────────────┐
                        │  netbox_compat   │
                        │  filter plugin   │
                        └──────────────────┘
```

The `netbox_compat` filter plugin transforms NetBox data structures to match the Nautobot format expected by the `avdbuilder` templates:

- Flattens `custom_field_data` into `cf_*` prefixed fields
- Transforms `role` to `device_role`
- Converts cable terminations to `connected_interface`
- Normalizes status from string to object format
- Extracts site ASN from `asns` array

## Files Added/Modified

### New Files

- `roles/netbox-sync/` - New role for NetBox data fetching
  - `tasks/main.yml` - Ansible tasks
  - `templates/*.graphql` - GraphQL query templates
  - `defaults/main.yml` - Default variables
- `ansible-emil/.../filter/netbox_compat.py` - NetBox compatibility filter
- `inventory_netbox.yml` - NetBox inventory template
- `PLAY_avdbuilder_netbox.yml` - NetBox playbook

### Unchanged Files

- `roles/nautobot-sync/` - Original Nautobot role (preserved)
- `roles/avdbuilder/` - AVD builder templates (no changes needed)
- `PLAY_avdbuilder.yml` - Original Nautobot playbook (preserved)

## Troubleshooting

### GraphQL Query Errors

If you see GraphQL errors, check that:
1. Your NetBox version is 4.2.x or later
2. Tags exist and are applied correctly
3. Custom fields are created with correct types

### Missing Custom Fields

The filter plugin expects custom fields. If a field is missing, it will be set to `None`. Ensure all required custom fields are created.

### Connection Issues

```yaml
# Disable SSL verification for self-signed certificates
netbox_validate_certs: false
```

## Migration Checklist

- [ ] Create all required custom fields in NetBox
- [ ] Create all required tags
- [ ] Create required device roles
- [ ] Migrate device data from Nautobot to NetBox
- [ ] Apply `avd` tag to relevant objects
- [ ] Configure `inventory_netbox.yml` with correct URL and token
- [ ] Test with `ansible-playbook -i inventory_netbox.yml PLAY_avdbuilder_netbox.yml --check`
