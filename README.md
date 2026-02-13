# Nautobot / NetBox as AVD Source of Truth

This project provides modeling conventions and Ansible roles to use either **Nautobot** or **NetBox** as the source of truth, then render data into a YAML model consumed by Arista's `arista.avd` collection to build an L3LS EVPN-VXLAN fabric.

## Repository Contents

### Ansible Roles

| Role | Description |
|------|-------------|
| **nautobot-sync** | Posts GraphQL queries to Nautobot and registers results for the avdbuilder role. |
| **netbox-sync** | Fetches data from NetBox (GraphQL + REST), normalizes it for avdbuilder. |
| **avdbuilder** | Renders YAML group_vars for an AVD fabric from data provided by nautobot-sync or netbox-sync. |

Refer to each role’s README for details.

### Custom Filters

The `emil.nbavd` filters (e.g. `structure_tenants`, `netbox_compat`) are included and required for the avdbuilder role.

### Migration Tool (Nautobot → NetBox)

The `migration/` directory contains a Python script that migrates data from Nautobot to NetBox. It runs **before** you use NetBox as the source of truth.

- **Custom fields**: The script **creates custom fields in NetBox automatically** from your Nautobot custom fields (including object types and choice sets for selection fields). You do **not** need to create them manually in NetBox.
- **Other objects**: Tags, sites, devices, interfaces, VLANs, VRFs, prefixes, cables, virtual chassis, config contexts, etc. are migrated in dependency order.

Run from the project root:

```bash
cd migration
cp config.yaml.example config.yaml
# Edit config.yaml with Nautobot and NetBox URLs and tokens
python migrate.py --config config.yaml --dry-run   # optional
python migrate.py --config config.yaml
```

After a successful migration, use the NetBox inventory and playbook below to generate AVD from NetBox.

## Modeling Conventions

Conventions for modeling data in Nautobot are described in **Nautobot Modelling Conventions.md**. The same logical fields (e.g. `evpn_role`, `bgp_asn`, `device_id`, `ospf_enabled`, `ip_helpers`, `next_hop`, etc.) are used when running from NetBox; the migration script ensures they exist in NetBox with the right types and object assignments.

## Example Playbooks

### Using NetBox

```yaml
---
- hosts: netbox
  connection: local
  gather_facts: false
  tasks:
    - name: Run netbox-sync
      import_role:
        name: netbox-sync

- hosts: netbox
  tasks:
    - name: Run avdbuilder
      import_role:
        name: avdbuilder
      vars:
        fabric_name: TEST-FABRIC
        site_names: ["dja", "sat"]   # must match site names in NetBox
```

### Using Nautobot

```yaml
---
- hosts: nautobot
  connection: local
  gather_facts: false
  tasks:
    - name: Run nautobot-sync
      import_role:
        name: nautobot-sync

- hosts: nautobot
  tasks:
    - name: Run avdbuilder
      import_role:
        name: avdbuilder
      vars:
        fabric_name: TEST-FABRIC
        site_names: ["DC1", "DC2"]
```

## Example Inventory

### NetBox

```yaml
---
all:
  children:
    NETBOX:
      hosts:
        netbox:
          ansible_host: localhost
          netbox_url: "http://localhost:8000"
          netbox_api_token: "<your-netbox-api-token>"
          netbox_validate_certs: false
```

Use host vars for the `netbox` host (e.g. `host_vars/netbox.yml`) with `avd_fabric_defaults` and per-site DC/spine/leaf defaults; site keys should match NetBox site names.

### Nautobot

```yaml
---
all:
  children:
    NAUTOBOT:
      hosts:
        nautobot:
          ansible_host: 10.10.10.10
          api_token: "<your-api-token>"
```

## Requirements and Dependencies

### Ansible

Tested with ansible-core 2.12+.

### AVD

Install the Arista AVD collection:

```shell
ansible-galaxy collection install arista.avd
ansible-galaxy collection install ansible.utils
```

The roles output the AVD v3/v4 data model.

### Source platform

- **Nautobot**: Tested with Nautobot v1.1.2 and later. The custom fields described in the modeling conventions document must exist in Nautobot (or be created there first). A Nautobot restart can be needed before new custom fields appear in the GraphQL API.
- **NetBox**: Tested with NetBox 4.2.x. When using the migration tool, custom fields are created in NetBox automatically; no manual creation is required.

### Python (for migration)

For the Nautobot→NetBox migration script:

```shell
pip install -r requirements.txt
```

Includes `pynautobot`, `pynetbox`, `requests`, `pyyaml`, etc.

### Ansible collections (Nautobot path)

For config contexts when using Nautobot:

```shell
ansible-galaxy collection install networktocode.nautobot
```
