# inventory_plugins/cmdbsyncer_inventory.py
"""
Ansible dynamic inventory plugin for the CMDB Syncer.

Two modes:

- ``local`` (default): shells out to ``cmdbsyncer inventory ansible
  <provider> --list`` against the Syncer binary on the same host.
  Used when the playbook runs on the Syncer itself — no HTTP, no auth,
  fast.

- ``http``: GETs ``/api/v1/inventory/ansible/<provider>`` from a remote
  Syncer. Used when the Ansible control node is a different host than
  the Syncer.

Both transports go through the same Syncer-side function, so the
inventory data is identical regardless of mode.
"""
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import json
import os
import shutil
import subprocess

from ansible.errors import AnsibleError
from ansible.plugins.inventory import BaseInventoryPlugin
from ansible.utils.display import Display

try:
    import requests
except ImportError:  # pragma: no cover - http mode only
    requests = None


DOCUMENTATION = r'''
    name: cmdbsyncer_inventory
    plugin_type: inventory
    short_description: Inventory Plugin for CMDB Syncer
    description:
      - Reads dynamic inventory from CMDB Syncer.
      - In `local` mode (default) shells out to the local `cmdbsyncer`
        CLI for zero-overhead access on the Syncer host.
      - In `http` mode talks to the Syncer's REST API for use from a
        remote Ansible control node.
    options:
      plugin:
        description: cmdbsyncer_inventory
        required: true
        choices: ['cmdbsyncer_inventory']
      mode:
        description: Transport. `local` shells the cmdbsyncer CLI; `http` calls the REST API.
        required: false
        type: string
        choices: ['local', 'http']
        default: local
      provider:
        description: Name of the inventory provider registered in the Syncer.
        required: false
        type: string
        default: ansible
      cmdbsyncer_bin:
        description: Path / name of the cmdbsyncer binary (local mode only).
        required: false
        type: string
        default: cmdbsyncer
      api_url:
        description: Syncer base URL (http mode only). Trailing path is appended automatically.
        required: false
        type: string
      username:
        description: API username (http mode). Falls back to env CMDBSYNCER_APIUSER.
        required: false
        type: string
      password:
        description: API password (http mode). Falls back to env CMDBSYNCER_APIPASSWORD.
        required: false
        type: string
      verify_ssl:
        description: Verify TLS certificates (http mode only).
        required: false
        type: bool
        default: true
'''


class InventoryModule(BaseInventoryPlugin):
    NAME = 'cmdbsyncer_inventory'

    def verify_file(self, path):
        valid = super().verify_file(path)
        if not valid:
            return False
        return path.endswith(('.yml', '.yaml'))

    def parse(self, inventory, loader, path, cache=True):
        super().parse(inventory, loader, path)
        self._read_config_data(path)
        display = Display()

        # Env vars beat plugin options so the Syncer's UI runner can
        # set provider/mode per playbook without rewriting the YAML.
        mode = (os.environ.get('CMDBSYNCER_INVENTORY_MODE')
                or self.get_option('mode')
                or 'local').strip().lower()
        provider = (os.environ.get('CMDBSYNCER_INVENTORY_PROVIDER')
                    or self.get_option('provider')
                    or 'ansible').strip()

        if mode == 'local':
            data = self._fetch_local(provider, display)
        elif mode == 'http':
            data = self._fetch_http(provider, display)
        else:
            raise AnsibleError(f"Unknown mode {mode!r} (expected local or http)")

        self._populate_from_api(data)

    # ------------------------------------------------------------------
    # Transports
    # ------------------------------------------------------------------

    def _fetch_local(self, provider, display):
        """Run the local cmdbsyncer CLI and parse its JSON output."""
        binary = self.get_option('cmdbsyncer_bin') or 'cmdbsyncer'
        # Allow `cmdbsyncer_bin: cmdbsyncer` to work even when only a
        # relative ./cmdbsyncer is on disk.
        resolved = shutil.which(binary) or binary
        cmd = [resolved, 'inventory', 'ansible', provider, '--list']
        display.vvv(f"cmdbsyncer_inventory: local exec {' '.join(cmd)}")
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, check=False,
            )
        except FileNotFoundError as exc:
            raise AnsibleError(
                f"cmdbsyncer binary not found ({binary!r}). "
                f"Either put it on PATH, set `cmdbsyncer_bin:` in the inventory "
                f"YAML, or switch to mode: http. Underlying error: {exc}"
            ) from exc
        if proc.returncode != 0:
            raise AnsibleError(
                f"cmdbsyncer CLI exited {proc.returncode}: {proc.stderr.strip()}"
            )
        try:
            return json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise AnsibleError(
                f"cmdbsyncer CLI returned non-JSON output: {exc}\n"
                f"First 200 chars: {proc.stdout[:200]!r}"
            ) from exc

    def _fetch_http(self, provider, display):
        """GET the Ansible-format inventory from the Syncer REST API."""
        if requests is None:
            raise AnsibleError(
                "http mode requires the `requests` package. "
                "Install it or switch to mode: local."
            )
        api_url = self.get_option('api_url')
        if not api_url:
            raise AnsibleError("http mode requires `api_url` in the inventory YAML.")
        username = os.environ.get('CMDBSYNCER_APIUSER') or self.get_option('username')
        password = os.environ.get('CMDBSYNCER_APIPASSWORD') or self.get_option('password')
        verify_ssl = self.get_option('verify_ssl')
        endpoint = f"{api_url.rstrip('/')}/api/v1/inventory/ansible/{provider}"
        display.vvv(f"cmdbsyncer_inventory: http GET {endpoint}")
        headers = {}
        if username and password:
            headers['x-login-user'] = f'{username}:{password}'
        try:
            resp = requests.get(
                endpoint, headers=headers, timeout=10, verify=verify_ssl,
            )
        except requests.RequestException as exc:
            raise AnsibleError(f"REST API call failed: {exc}") from exc
        if resp.status_code != 200:
            raise AnsibleError(
                f"REST API returned {resp.status_code}: {resp.text[:200]}"
            )
        return resp.json()

    # ------------------------------------------------------------------
    # Common population path
    # ------------------------------------------------------------------

    def _populate_from_api(self, data):
        """
        Parse the standard Ansible inventory shape::

            {
                "_meta": {"hostvars": {"<host>": {...vars...}}},
                "all": {"hosts": ["<host>", ...]}
            }

        Hostvars may include `ansible_groups: [...]` to map a host into
        groups; the key is popped so it does not leak as a host var.
        """
        all_hosts = data.get('all', {}).get('hosts', [])
        hostvars = data.get('_meta', {}).get('hostvars', {})

        for hostname in all_hosts:
            self.inventory.add_host(hostname)
            host_vars = hostvars.get(hostname, {})
            groups = host_vars.pop('ansible_groups', ['ungrouped'])
            if not isinstance(groups, list):
                groups = [groups] if groups else ['ungrouped']
            for key, value in host_vars.items():
                self.inventory.set_variable(hostname, key, value)
            for group_name in groups:
                if not self.inventory.groups.get(group_name):
                    self.inventory.add_group(group_name)
                self.inventory.add_host(hostname, group=group_name)
