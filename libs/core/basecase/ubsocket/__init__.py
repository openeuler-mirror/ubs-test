"""UBSocket BaseCase classes."""

from libs.core.basecase.ubsocket.ubsocket_basecase import UBSocketBaseCase
from libs.core.basecase.ubsocket.brpc_perf_basecase import BRPCPerfBaseCase, inject_brpc_perf_basecase_dependencies

__all__ = [
    "UBSocketBaseCase",
    "BRPCPerfBaseCase",
    "inject_brpc_perf_basecase_dependencies",
]