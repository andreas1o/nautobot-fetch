# NetBox/Nautobot AVD Sync

Ansible-based framework for generating Arista AVD (Arista Validated Design) configuration from NetBox or Nautobot network source of truth platforms.

## Features

- **Dual Platform Support**: Works with both NetBox 4.2.9+ and Nautobot 1.6+
- **AVD Integration**: Generates YAML files compatible with Arista AVD collection (v3 and v4)
- **Migration Tool**: Python-based tool to migrate data from Nautobot to NetBox
- **L3LS EVPN-VXLAN**: Designed for Layer 3 Leaf-Spine EVPN-VXLAN fabric designs

## Quick Start

### Prerequisites

- Python 3.8+
- Ansible 2.12+
- Access to NetBox or Nautobot instance

### Installation

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/netbox-avd-sync.git
cd netbox-avd-sync

# Install Python dependencies
pip install -r requirements.txt

# Install Ansible collections
ansible-galaxy collection install arista.avd
ansible-galaxy collection install networktocode.nautobot  # For Nautobot
ansible-galaxy collection install netbox.netbox           # For NetBox
```

### Quick Test

```bash
# For NetBox
ansible-playbook -i inventory_netbox.yml PLAY_avdbuilder_netbox.yml --check

# For Nautobot
ansible-playbook -i inventory.yml PLAY_avdbuilder.yml --check
```

## Project Structure

```
netbox-avd-sync/
├── roles/
│   ├── netbox-sync/          # Fetch data from NetBox via GraphQL
│   ├── nautobot-sync/        # Fetch data from Nautobot via GraphQL
│   └── avdbuilder/           # Generate AVD YAML files
│       └── templates/
│           ├── v3/           # AVD 3.x templates
│           └── v4/           # AVD 4.x templates
├── migration/                 # Nautobot → NetBox migration tool
├── ansible-emil/              # Custom Ansible filter plugins
├── PLAY_avdbuilder_netbox.yml # Playbook for NetBox
├── PLAY_avdbuilder.yml        # Playbook for Nautobot
├── inventory_netbox.yml       # NetBox inventory template
├── inventory.yml              # Nautobot inventory template
└── host_vars/                 # Host-specific variables
```

## Installation Guide

### 1. System Requirements

| Component | Version |
|-----------|---------|
| Python | 3.8+ |
| Ansible Core | 2.12+ |
| NetBox | 4.2.9+ (for NetBox sync) |
| Nautobot | 1.6+ (for Nautobot sync) |

### 2. Install Python Dependencies

Create a virtual environment (recommended):

```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# or
.\venv\Scripts\activate   # Windows
```

Install required packages:

```bash
pip install ansible-core>=2.12
pip install pynautobot>=1.0.4    # For Nautobot
pip install pynetbox>=7.0.0      # For NetBox
pip install requests>=2.28.0
pip install pyyaml>=6.0
pip install jmespath
```

Or use the requirements file:

```bash
pip install -r requirements.txt
```

### 3. Install Ansible Collections

```bash
# Required for AVD output consumption
ansible-galaxy collection install arista.avd

# For Nautobot support
ansible-galaxy collection install networktocode.nautobot

# For NetBox support (optional, for additional features)
ansible-galaxy collection install netbox.netbox
```

### 4. Configure Ansible

The `ansible.cfg` is pre-configured, but verify these settings:

```ini
[defaults]
collections_paths = ./ansible-emil:~/.ansible/collections
roles_path = ./roles
jinja2_extensions = jinja2.ext.loopcontrols,jinja2.ext.do
```

### 5. Configure Inventory

#### For NetBox:

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

#### For Nautobot:

Edit `inventory.yml`:

```yaml
all:
  children:
    NAUTOBOT:
      hosts:
        nautobot:
          ansible_host: nautobot.example.com
          api_token: "your-api-token-here"
```

### 6. Configure Host Variables

Edit `host_vars/nautobot.yml` (or create `host_vars/netbox.yml`):

```yaml
# Site-specific configuration
DC1:
  dc_defaults:
    # Your DC defaults here
  spine:
    defaults:
      # Spine defaults
    nodes:
      # Node-specific config
  l3leaf:
    defaults:
      # L3 leaf defaults
    node_groups:
      # Node groups
```

## Usage

### Generate AVD Configuration from NetBox

```bash
ansible-playbook -i inventory_netbox.yml PLAY_avdbuilder_netbox.yml
```

### Generate AVD Configuration from Nautobot

```bash
ansible-playbook -i inventory.yml PLAY_avdbuilder.yml
```

### Output

Generated files are placed in `avdbuilder_vars/`:

```
avdbuilder_vars/
├── TEST-FABRIC.yml      # Fabric-wide settings
├── DC1.yml              # DC1 spine/leaf configuration
├── DC1_SERVERS.yml      # DC1 server connections
├── DC1_TENANTS.yml      # DC1 tenant services
├── DC2.yml              # DC2 configuration
├── DC2_SERVERS.yml
└── DC2_TENANTS.yml
```

## Migration Tool (Nautobot → NetBox)

Migrate your data from Nautobot to NetBox:

### Install Migration Dependencies

```bash
cd migration
pip install -r requirements.txt
```

### Configure Migration

```bash
cp config.yaml.example config.yaml
# Edit config.yaml with your credentials
```

### Run Migration

```bash
# Dry run first
python migrate.py --config config.yaml --dry-run

# Full migration
python migrate.py --config config.yaml

# Migrate specific objects
python migrate.py --config config.yaml --objects tags,sites,devices
```

See `migration/README.md` for detailed migration documentation.

## Platform Setup Requirements

### Required Custom Fields

Create these custom fields in NetBox/Nautobot:

| Field Name | Type | Object Types | Description |
|------------|------|--------------|-------------|
| `bgp_asn` | Text | Device | BGP AS number |
| `device_id` | Integer | Device | Device ID (1-254) |
| `evpn_role` | Selection | Device | `client`, `server`, `none` |
| `ospf_enabled` | Boolean | VRF, VLAN | Enable OSPF |
| `mlag_ibgp_peering` | Boolean | VRF | Enable MLAG iBGP |
| `base_vni` | Integer | Tenant | MAC VRF VNI base |
| `ip_helpers` | Text | VLAN | Comma-separated IPs |
| `vxlan_enable` | Boolean | VLAN | Enable VXLAN |

### Required Tags

- `avd` - Mark objects for AVD processing (required)
- `uplink` - Mark uplink interfaces
- `peerlink` - Mark MLAG peer-link interfaces

### Required Device Roles

- `spine` - Spine switches
- `l3leaf` - Layer 3 leaf switches
- `l2leaf` - Layer 2 leaf switches
- `bgp_peer` - External BGP peer devices

## Troubleshooting

### Connection Issues

```bash
# Test NetBox connection
curl -H "Authorization: Token YOUR_TOKEN" https://netbox.example.com/api/

# Test Nautobot connection
curl -H "Authorization: Token YOUR_TOKEN" http://nautobot.example.com/api/
```

### GraphQL Errors

Ensure all required custom fields exist. NetBox/Nautobot may need a restart after creating custom fields.

### Missing Custom Fields

```bash
# Check custom fields in NetBox
curl -H "Authorization: Token YOUR_TOKEN" https://netbox.example.com/api/extras/custom-fields/
```

### Ansible Errors

```bash
# Verbose output
ansible-playbook -i inventory_netbox.yml PLAY_avdbuilder_netbox.yml -vvv

# Check syntax
ansible-playbook --syntax-check PLAY_avdbuilder_netbox.yml
```

## Modeling Conventions

See `Nautobot Modelling Conventions.md` for detailed data modeling requirements.

## License

MIT License

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request
