# !/usr/bin/python3
# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2025-2025. All rights reserved.
# virtagent is licensed under Mulan PSL v2.
# You can use this software according to the terms and conditions of the Mulan PSL v2.
# You may obtain a copy of Mulan PSL v2 at:
#          http://license.coscl.org.cn/MulanPSL2
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND,
# EITHER EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT,
# MERCHANTABILITY OR FIT FOR A PARTICULAR PURPOSE.
# See the Mulan PSL v2 for more details.
import ctypes
import json
import logging
from typing import Dict, Any
from ubs_virt_agent_types import WatermarkT
from ubs_virt_agent_base import UbsVirtAgentBase

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s"
)


class UbsContainerInjectWaterLine(UbsVirtAgentBase):
    """UbsVirtAgentWaterlineMemReturn related interface"""

    def __init__(self):
        super().__init__()
        self.setup_mem_inject_execute_functions()

    def ubs_container_inject_waterLine(self, param: Dict[str, Any]):
        if not self.lib_ubse:
            raise ConnectionError("Native library not loaded")

        injectRequestParam = self.build_waterline_request_param(param)

        result = self.lib_ubse.ubs_container_inject_waterLine(
            ctypes.byref(injectRequestParam),
        )
        if result != 0:
            raise RuntimeError(f"Failed to execute inject waterline, error code: {result}")

        executeRes = {
            "code": result
        }
        logging.info(json.dumps(executeRes))
        return executeRes

    def setup_mem_inject_execute_functions(self):
        """
        Set the prototype of the relevant function
        详情参照libvirt_agent_container.h中ubs_virt_agent_waterline_mem_return的声明
        """
        self.lib_ubse.ubs_container_inject_waterLine.argtypes = [
            ctypes.POINTER(WatermarkT)
        ]
        self.lib_ubse.ubs_container_inject_waterLine.restype = ctypes.c_int32

        # Set the free function(If it exists)
        if hasattr(self.lib_ubse, 'free'):
            self.lib_ubse.free.argtypes = [ctypes.c_void_p]
            self.lib_ubse.free.restype = None

    def build_waterline_request_param(self, param: Dict[str, Any]):
        """
        将python字典转换为c++结构体
        """
        injectRequestParam = WatermarkT()
        injectRequestParam.highWaterMark = param["highWaterMark"]
        injectRequestParam.lowWaterMark = param["lowWaterMark"]

        return injectRequestParam


def main(param):
    """
    param形如：
    {
        “highWaterMark”： 92，
        “lowWaterMark”： 80
    }
    """
    try:
        if isinstance(param, str):
            param = json.loads(param)
    except Exception as e:
        raise ValueError(f"JSON parse error: {e}") from e
    UbsContainerInjectWaterLine().ubs_container_inject_waterLine(param=param)


if __name__ == "__main__":
    import sys
    main(param=sys.argv[1])