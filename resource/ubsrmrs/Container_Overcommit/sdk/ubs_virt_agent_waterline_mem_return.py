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
from ubs_virt_agent_types import ReturnRequestT
from ubs_virt_agent_base import UbsVirtAgentBase

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s"
)


class UbsVirtAgentWaterlineMemReturn(UbsVirtAgentBase):
    """UbsVirtAgentWaterlineMemReturn related interface"""

    def __init__(self):
        super().__init__()
        self.setup_mem_return_execute_functions()

    def ubs_virt_agent_waterline_mem_return(self, param: Dict[str, Any]):
        if not self.lib_ubse:
            raise ConnectionError("Native library not loaded")

        returnRequestParam = self.build_return_request_param(param)

        result = self.lib_ubse.ubs_virt_agent_waterline_mem_return(
            ctypes.byref(returnRequestParam),
        )
        if result != 0:
            raise RuntimeError(f"Failed to execute memory water return, error code: {result}")

        returnExecuteRes = {
            "code": result
        }
        logging.info(json.dumps(returnExecuteRes))
        return returnExecuteRes

    def setup_mem_return_execute_functions(self):
        """
        Set the prototype of the relevant function
        详情参照libvirt_agent_container.h中ubs_virt_agent_waterline_mem_return的声明
        """
        self.lib_ubse.ubs_virt_agent_waterline_mem_return.argtypes = [
            ctypes.POINTER(ReturnRequestT)
        ]
        self.lib_ubse.ubs_virt_agent_waterline_mem_return.restype = ctypes.c_int32

        # Set the free function(If it exists)
        if hasattr(self.lib_ubse, 'free'):
            self.lib_ubse.free.argtypes = [ctypes.c_void_p]
            self.lib_ubse.free.restype = None

    def build_return_request_param(self, param: Dict[str, Any]):
        """
        将python字典转换为c++结构体
        """
        returnRequestParam = ReturnRequestT()

        srcNid = param["borrowParam"]["srcNid"]
        if not isinstance(srcNid, str):
            raise ValueError("srcNid must be a string")
        returnRequestParam.borrowParam.srcNid = srcNid.encode('utf-8')

        srcLocations = param["borrowParam"]["srcLocations"]
        returnRequestParam.borrowParam.srcLocationsSize = len(srcLocations)
        for i, v in enumerate(srcLocations):
            returnRequestParam.borrowParam.srcLocations[i].socketId = v["socketId"]
            returnRequestParam.borrowParam.srcLocations[i].numaId = v["numaId"]

        borrowIds = param["borrowIds"]
        returnRequestParam.borrowIdsSize = len(borrowIds)
        for i, v in enumerate(borrowIds):
            idStr = v.encode("utf-8")
            returnRequestParam.borrowIds[i][:len(idStr)] = idStr
            returnRequestParam.borrowIds[i][len(idStr)] = 0

        pids = param["pids"]
        returnRequestParam.pidsSize = len(pids)
        for i, v in enumerate(pids):
            returnRequestParam.pids[i] = v
        return returnRequestParam


def main(param):
    """
    param形如：
     {
        "borrowParam": {
            "srcNid": "2",
            "srcLocations": [
                {"socketId": 36,
                 "numaId": 0}
            ],
        }
        "borrowIds": ["2@d1b9cf805f69ddf931e97eacad65e8a6"],
        "pids": []
    }
    """
    try:
        if isinstance(param, str):
            param = json.loads(param)
    except Exception as e:
        raise ValueError(f"JSON parse error: {e}") from e
    UbsVirtAgentWaterlineMemReturn().ubs_virt_agent_waterline_mem_return(param=param)


if __name__ == "__main__":
    import sys
    main(param=sys.argv[1])