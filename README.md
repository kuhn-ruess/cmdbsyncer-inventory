# CMDBSyncer Inventory Plugin

[![PyPI version](https://badge.fury.io/py/cmdbsyncer-inventory.svg)](https://badge.fury.io/py/cmdbsyncer-inventory)
[![Python Support](https://img.shields.io/pypi/pyversions/cmdbsyncer-inventory.svg)](https://pypi.org/project/cmdbsyncer-inventory/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

An Ansible dynamic inventory plugin that fetches host and group information from CMDBSyncer.

## Installation

### Via pip (Recommended)

```bash
# Install the package
pip install cmdbsyncer-inventory

# Auto-install plugin for Ansible (run once after installation)
python -m cmdbsyncer_inventory
```

**That's it!** The plugin is now automatically available to Ansible. 

### Alternative methodm

**Method 1: Using the install command (if available)**
```bash
cmdbsyncer-install-plugin  # If console scripts work on your system
```

**Method 2: Manual copy to project** 
```bash
# Install the package
pip install cmdbsyncer-inventory

# Manually copy to your project
mkdir -p inventory_plugins
python -c "
import cmdbsyncer_inventory
from pathlib import Path
import shutil

src = Path(cmdbsyncer_inventory.__file__).parent / 'inventory_plugins' / 'cmdbsyncer_inventory.py'
shutil.copy2(src, 'inventory_plugins/cmdbsyncer_inventory.py')
print('Plugin copied to ./inventory_plugins/')
"
```

### Via pip from source

```bash
pip install git+https://github.com/kuhn-ruess/cmdbsyncer-inventory.git
python -m cmdbsyncer_inventory
```

## Usage

After installation and running `python -m cmdbsyncer_inventory`, the plugin is available to Ansible in two transport modes:

- **`local`** (default): shells out to the local `cmdbsyncer` CLI. Use this when the Ansible control node and the Syncer run on the same host — no auth, no HTTP, fastest.
- **`http`**: GETs `/api/v1/inventory/ansible/<provider>` from a remote Syncer over HTTPS. Use this from a separate Ansible control node.

### Local mode

```yaml
# inventory.yml
plugin: cmdbsyncer_inventory
mode: local         # default — can be omitted
provider: ansible   # default — names a provider registered in the Syncer
# cmdbsyncer_bin: /opt/cmdbsyncer/cmdbsyncer    # optional override
```

```bash
ansible-inventory -i inventory.yml --list
ansible-playbook -i inventory.yml your-playbook.yml
```

The Syncer's UI runner sets `CMDBSYNCER_INVENTORY_PROVIDER` per-playbook based on its manifest, so the same inventory YAML works for every dispatched playbook.

### HTTP mode

```yaml
# inventory.yml
plugin: cmdbsyncer_inventory
mode: http
provider: ansible
api_url: https://your-cmdbsyncer-instance.com
# username / password optional — prefer env vars
```

```bash
export CMDBSYNCER_APIUSER="your_username"
export CMDBSYNCER_APIPASSWORD="your_password"

ansible-inventory -i inventory.yml --list
```

## Configuration Options

| Option | Required | Type | Default | Description |
|--------|----------|------|---------|-------------|
| `plugin` | Yes | string | — | Must be `cmdbsyncer_inventory` |
| `mode` | No | string | `local` | `local` or `http` — see above |
| `provider` | No | string | `ansible` | Name of a provider registered in the Syncer's inventory registry (e.g. `ansible`, `cmk_sites`) |
| `cmdbsyncer_bin` | No | string | `cmdbsyncer` | Path to the cmdbsyncer CLI (local mode only) |
| `api_url` | http only | string | — | Syncer base URL (http mode only) |
| `username` | No | string | — | API username (http mode; falls back to `CMDBSYNCER_APIUSER`) |
| `password` | No | string | — | API password (http mode; falls back to `CMDBSYNCER_APIPASSWORD`) |
| `verify_ssl` | No | bool | `true` | Verify TLS certificates (http mode only) |

Both `mode` and `provider` may also be set via env vars (`CMDBSYNCER_INVENTORY_MODE`, `CMDBSYNCER_INVENTORY_PROVIDER`); env wins over the YAML so the same inventory file works for many playbooks.

## Example Output

The plugin will create Ansible inventory with hosts and groups based on your CMDBSyncer configuration. Example structure:

```json
{
  "_meta": {
    "hostvars": {
      "server1.example.com": {
        "ansible_host": "10.0.0.1",
        "ansible_user": "admin",
        "environment": "production"
      }
    }
  },
  "production": {
    "hosts": ["server1.example.com"]
  },
  "web": {
    "hosts": ["server1.example.com"]  
  }
}
```

## Requirements

- Python 3.7+
- Ansible Core 2.12+
- CMDBSyncer instance with API access

## Development

### Local Development Setup

```bash
# Clone the repository
git clone https://github.com/kuhn-ruess/cmdbsyncer-inventory.git
cd cmdbsyncer-inventory

# Install in development mode
pip install -e .

# Install plugin for Ansible
python -m cmdbsyncer_inventory

# Test the plugin
ansible-inventory -i example-inventory.yml --list
```

### Building for PyPI

```bash
# Install build tools
pip install build twine

# Build package
python -m build

# Upload to PyPI
python -m twine upload dist/*
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

- � Email: info@kuhn-ruess.de
- �🐛 Issues: [GitHub Issues](https://github.com/kuhn-ruess/cmdbsyncer-inventory/issues)
- 📖 Documentation: [Wiki](https://github.com/kuhn-ruess/cmdbsyncer-inventory/wiki)
