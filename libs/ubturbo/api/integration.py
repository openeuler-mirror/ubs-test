# -*- coding: utf-8 -*-
"""Integration API — stub functions pending full migration from legacy."""

from typing import Any, List, Tuple
from xml.etree.ElementTree import Element


def get_cpuset_range_at_numa(numa_index: int, node: Any) -> Tuple[int, int]:
    """
    Get the CPU set range for a given NUMA node.

    NOTE: This is a stub — full implementation pending migration from legacy.
    """
    raise NotImplementedError(
        f"get_cpuset_range_at_numa(numa_index={numa_index}): "
        "full implementation pending migration from legacy"
    )


def change_cpuset_at_vcpu(vcpu_index: int, cpuset: int, xml_tree: Element) -> None:
    """
    Change the cpuset assignment for a vCPU in the domain XML.

    NOTE: This is a stub — full implementation pending migration from legacy.
    """
    raise NotImplementedError(
        f"change_cpuset_at_vcpu(vcpu_index={vcpu_index}): "
        "full implementation pending migration from legacy"
    )


def change_emulatorpin_cpuset(cpuset_range: str, xml_tree: Element) -> None:
    """
    Change the emulatorpin cpuset in the domain XML.

    NOTE: This is a stub — full implementation pending migration from legacy.
    """
    raise NotImplementedError(
        f"change_emulatorpin_cpuset(cpuset_range={cpuset_range}): "
        "full implementation pending migration from legacy"
    )
