"""UBSVirt BaseCase classes for pytest testing."""

from libs.modules.ubsvirt.basecase.openstack_basecase import (
    OpenStackBaseCase,
    inject_openstack_basecase_dependencies,
)

__all__ = [
    "OpenStackBaseCase",
    "inject_openstack_basecase_dependencies",
]