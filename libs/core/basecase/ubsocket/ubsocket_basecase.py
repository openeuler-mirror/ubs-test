"""UBSocketBaseCase - Base class for UBSocket tests.

Migrated from: legency/testcase/ubscomm/ubsocket/lib/basecase/ubsocket/UBSocketBaseCase.py
"""

import logging
from pathlib import Path

from libs.core.basecase.hcom.turbo_comm_basecase import TurboCommBaseCase
from libs.ubsocket import k8s_api as k8s
from libs.ubsocket import brpc_utils

logger = logging.getLogger(__name__)

CODE_PATCH_PATH = str(Path(__file__).resolve().parents[3])


class UBSocketBaseCase(TurboCommBaseCase):
    """Base class for UBSocket tests."""
    
    def get_pod_name_ip_id(self, pod_grep="default", get_dev=True, get_cpu=True):
        """Get pod info including name, IP, and container ID."""
        pods_info = {}
        ret = k8s.get_pods_wide(self.master, grep=pod_grep)
        res = brpc_utils.parse_output(ret)
        for info_dict in res:
            if info_dict.get("STATUS") != "Running":
                self.logWarn("Container not running")
            id = k8s.get_container_id(self.master, info_dict.get("NAME"))
            urma_dev = brpc_utils.get_container_device(self.master, info_dict.get("NAME")) if get_dev else None
            cpu = brpc_utils.get_container_cpu(self.master, info_dict.get("NAME")) if get_cpu else None
            pods_info[info_dict.get("NAME")] = {
                "namespace": info_dict.get("NAMESPACE"),
                "ip": info_dict.get("IP"),
                "node": info_dict.get("NODE"),
                "id": id,
                "cpu": cpu,
                "urma_dev": urma_dev
            }
        return pods_info