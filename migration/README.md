# Nautobot to NetBox Migration Tool

This tool migrates data from Nautobot 1.6+ to NetBox 4.2.9+, maintaining compatibility with the `netbox-sync` role for AVD configuration generation.

## Features

- **Full data migration**: Migrates all object types needed for AVD configuration generation
- **ID mapping**: Tracks Nautobot UUIDs to NetBox integer IDs for relationship resolution
- **Custom field support**: Migrates custom fields and their values
- **Dry run mode**: Test migration without making changes
- **Resume capability**: Caches ID mappings to resume interrupted migrations
- **Error handling**: Continue on errors with detailed logging

## Quick Start

```bash
# From the project root directory
cd /path/to/netbox-avd-sync

# Activate the virtual environment
source venv/bin/activate

# Configure migration
cd migration
cp config.yaml.example config.yaml
# Edit config.yaml with your credentials

# Run dry-run first
python migrate.py --config config.yaml --dry-run

# Run full migration
python migrate.py --config config.yaml
```

## Installation

### Option 1: Use project venv (Recommended)

The migration tool uses the same virtual environment as the main project:

```bash
# From project root
cd /path/to/netbox-avd-sync

# Create and activate venv (if not already done)
python3 -m venv venv
source venv/bin/activate

# Install all dependencies
pip install -r requirements.txt

# Migration dependencies are included in main requirements.txt
```

### Option 2: Standalone installation

If you want to run the migration tool separately:

```bash
cd migration

# Create dedicated venv
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Configuration

1. Copy the example configuration:
```bash
cp config.yaml.example config.yaml
```

2. Edit `config.yaml` with your Nautobot and NetBox credentials:
```yaml
nautobot:
  url: "http://nautobot.example.com"
  token: "your-nautobot-api-token"
  verify_ssl: true

netbox:
  url: "https://netbox.example.com"
  token: "your-netbox-api-token"
  verify_ssl: true

migration:
  dry_run: false
  continue_on_error: true
```

## Usage

**Always activate the venv first:**

```bash
# From project root
source venv/bin/activate
cd migration
```

### Full Migration

```bash
python migrate.py --config config.yaml
```

### Dry Run (no changes made)

```bash
python migrate.py --config config.yaml --dry-run
```

### Migrate Specific Objects

```bash
python migrate.py --config config.yaml --objects tags,sites,devices
```

### Verbose Logging

```bash
python migrate.py --config config.yaml --verbose
```

### Using the helper script

```bash
# Make executable (first time only)
chmod +x run_migrate.sh

# Run migration
./run_migrate.sh --dry-run
./run_migrate.sh
./run_migrate.sh --objects tags,sites
```

## Migration Order

Objects are migrated in dependency order:

1. **tags** - No dependencies
2. **custom_fields** - No dependencies
3. **tenant_groups** - Hierarchical (parents first)
4. **tenants** - Depends on tenant_groups
5. **regions** - Hierarchical (parents first)
6. **sites** - Depends on regions, tenants
7. **manufacturers** - No dependencies
8. **device_types** - Depends on manufacturers
9. **device_roles** - No dependencies
10. **platforms** - Depends on manufacturers
11. **rack_groups** - Becomes locations in NetBox 4.x
12. **racks** - Depends on sites, locations
13. **vlan_groups** - Depends on sites
14. **route_targets** - Depends on tenants
15. **vrf** - Depends on tenants, route_targets
16. **vlans** - Depends on sites, vlan_groups, tenants
17. **prefixes** - Depends on sites, vrfs, vlans
18. **devices** - Depends on sites, device_types, roles, platforms
19. **interfaces** - Depends on devices, vlans (LAGs first)
20. **ip_addresses** - Depends on vrfs, interfaces
21. **cables** - Depends on interfaces
22. **virtual_chassis** - Depends on devices
23. **config_contexts** - Depends on regions, sites, roles, platforms

## Data Transformations

### Nautobot to NetBox Field Mappings

| Nautobot | NetBox 4.2+ | Notes |
|----------|-------------|-------|
| UUID IDs | Integer IDs | ID mapper tracks relationships |
| `device_role` | `role` | Field renamed in NetBox 4.x |
| `cf_fieldname` | `custom_fields.fieldname` | Custom fields in JSON object |
| `status.name` | `status` | Status is now a string enum |
| `rack_group` | `location` | Rack groups replaced by locations |
| Connected interface | `cable.terminations` | Cable termination model changed |

### Status Mappings

Nautobot uses a Status model while NetBox uses predefined choices:

| Nautobot Status | NetBox Status |
|-----------------|---------------|
| Active | active |
| Planned | planned |
| Staged | staged |
| Failed | failed |
| Offline | offline |
| Decommissioning | decommissioning |

## ID Mapping Cache

The tool creates an `id_mapping.json` file that stores the relationship between Nautobot UUIDs and NetBox IDs. This file:

- Enables resuming interrupted migrations
- Allows incremental updates
- Helps with troubleshooting

Example:
```json
{
  "device": {
    "abc123-uuid": 1,
    "def456-uuid": 2
  },
  "site": {
    "ghi789-uuid": 1
  }
}
```

## Handling Existing Data

The migration tool checks for existing objects in NetBox by slug or name:

- **Tags**: Matched by slug
- **Sites**: Matched by slug
- **Devices**: Matched by name
- **VRFs**: Matched by name

If an object already exists, it's skipped and the ID mapping is recorded.

## Custom Fields

Custom fields are migrated automatically. The configuration supports field name mapping if field names differ between systems:

```yaml
migration:
  custom_field_mapping:
    nautobot_field_name: netbox_field_name
```

For select/multiselect fields, choice sets are created in NetBox.

## Troubleshooting

### Connection Errors

```
Failed to connect to Nautobot/NetBox
```

- Verify URL and API token
- Check network connectivity
- Verify SSL certificate settings

### Permission Errors

```
403 Forbidden
```

- Ensure API token has write permissions
- Check object-level permissions in NetBox

### Missing Dependencies

```
Failed to migrate device: manufacturer not found
```

- Ensure migration runs in correct order
- Check if dependent objects were migrated successfully
- Review `id_mapping.json` for missing mappings

### Duplicate Objects

```
UNIQUE constraint failed
```

- Object may already exist in NetBox
- Check if object was migrated in previous run
- Clear NetBox data or use `--objects` to skip

## Post-Migration Steps

1. **Verify data in NetBox**:
   - Check object counts match
   - Verify relationships are correct
   - Test custom field values

2. **Update AVD playbook**:
   ```bash
   source venv/bin/activate
   ansible-playbook -i inventory_netbox.yml PLAY_avdbuilder_netbox.yml
   ```

3. **Test AVD output**:
   - Compare generated YAML with previous Nautobot-based output
   - Verify all devices and services are present

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Nautobot 1.6+  │────▶│  migrate.py      │────▶│  NetBox 4.2.9+  │
│  REST API       │     │                  │     │  REST API       │
└─────────────────┘     │  ┌────────────┐  │     └─────────────────┘
                        │  │ ID Mapper  │  │
                        │  └────────────┘  │
                        │  ┌────────────┐  │
                        │  │ Mappers    │  │
                        │  └────────────┘  │
                        └──────────────────┘
```

## Files

```
migration/
├── migrate.py              # Main migration script
├── run_migrate.sh          # Helper script (activates venv)
├── config.yaml.example     # Example configuration
├── requirements.txt        # Python dependencies
├── README.md               # This file
├── lib/
│   ├── __init__.py
│   ├── nautobot_client.py  # Nautobot API client
│   ├── netbox_client.py    # NetBox API client
│   └── id_mapper.py        # ID mapping utilities
└── mappers/
    ├── __init__.py
    ├── base.py             # Base mapper class
    ├── dcim.py             # DCIM object mappers
    ├── ipam.py             # IPAM object mappers
    ├── tenancy.py          # Tenancy mappers
    └── extras.py           # Custom fields, config contexts
```
