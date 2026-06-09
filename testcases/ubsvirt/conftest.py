"""pytest configuration for all testcases.

This file imports and exposes fixtures from libs/core/fixtures.py,
making them available to all tests under testcases/ directory.

pytest fixture discovery mechanism:
  pytest searches conftest.py files from test directory upward to root.
  This top-level conftest.py makes libs/core/fixtures.py fixtures available globally.
"""

from libs.modules.ubsvirt.basecase.openstack_basecase import inject_openstack_basecase_dependencies as inject_virtualization_openstack_basecase_dependencies
from libs.modules.ubsvirt.basecase.vmxml_basecase import inject_vmxml_basecase_dependencies
