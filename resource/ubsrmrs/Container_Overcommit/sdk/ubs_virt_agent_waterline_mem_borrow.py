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
from ubs_virt_agent_base import UbsVirtAgentBase
from ubs_virt_agent_types import MemBorrowRequestT

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s"
)


class UbsVirtAgentWaterlineMemBorrow(UbsVirtAgentBase):
    """UbsVirtAgentWaterlineMemBorrow related interface"""

    def __init__(self):
        super().__init__()
        self.setup_mem_borrow_execute_functions()


    def ubs_virt_agent_waterline_mem_borrow(self, param: Dict[str, Any]):
        if not self.lib_ubse:
            raise ConnectionError("Native library not loaded")

        borrowRequestParam = self.build_borrow_request_param(param)

        borrowIds = ctypes.POINTER(ctypes.c_char_p)()
        borrowIdsPtr = ctypes.pointer(borrowIds)
        borrowIdsSize = ctypes.c_uint32(0)
        result = self.lib_ubse.ubs_virt_agent_waterline_mem_borrow(
            ctypes.byref(borrowRequestParam),
            borrowIdsPtr,
            ctypes.byref(borrowIdsSize)
        )
        if result != 0:
            raise RuntimeError(f"Failed to execute memory water borrow, error code: {result}")
        if not borrowIdsPtr:
            raise RuntimeError(f"borrow_ids_ptr is null")
        if borrowIdsSize.value == 0:
            raise RuntimeError(f"borrow_ids_size is zero or numa_ids_size is zero")

        borrowIdsRes = []
        for i in range(borrowIdsSize.value):
            borrowId = ctypes.string_at(borrowIds[i]).decode("utf-8")
            borrowIdsRes.append(borrowId)

        borrowExecuteRes = {
            "code": result,
            "borrowIds": borrowIdsRes
        }
        logging.info(json.dumps(borrowExecuteRes))
        return borrowExecuteRes

    def setup_mem_borrow_execute_functions(self):
        """
        Set the prototype of the relevant function
        详情参照libvirt_agent_container.h中ubs_virt_agent_waterline_mem_borrow的声明
        """
        self.lib_ubse.ubs_virt_agent_waterline_mem_borrow.argtypes = [
            ctypes.POINTER(MemBorrowRequestT),
            ctypes.POINTER(ctypes.POINTER(ctypes.c_char_p)),
            ctypes.POINTER(ctypes.c_uint32)
        ]
        self.lib_ubse.ubs_virt_agent_waterline_mem_borrow.restype = ctypes.c_int32

        # Set the free function(If it exists)
        if hasattr(self.lib_ubse, 'free'):
            self.lib_ubse.free.argtypes = [ctypes.c_void_p]
            self.lib_ubse.free.restype = None


    def build_borrow_request_param(self, param: Dict[str, Any]):
        """
        将python字典转换为c++结构体
        """
        borrowRequestParam = MemBorrowRequestT()
        srcNid = param["borrowParam"]["srcNid"]
        if not isinstance(srcNid, str):
            raise ValueError("srcNid must be a string")
        borrowRequestParam.borrowParam.srcNid = srcNid.encode('utf-8')

        srcLocations = param["borrowParam"]["srcLocations"]
        borrowRequestParam.borrowParam.srcLocationsSize = len(srcLocations)
        for i, v in enumerate(srcLocations):
            borrowRequestParam.borrowParam.srcLocations[i].socketId = v["socketId"]
            borrowRequestParam.borrowParam.srcLocations[i].numaId = v["numaId"]

        borrowSizes = param["borrowSizes"]
        borrowRequestParam.borrowSizesSize = len(borrowSizes)
        for i, v in enumerate(borrowSizes):
            borrowRequestParam.borrowSizes[i] = v

        borrowRequestParam.waterMark.highWaterMark = param["waterMark"]["highWaterMark"]
        borrowRequestParam.waterMark.lowWaterMark = param["waterMark"]["lowWaterMark"]
        return borrowRequestParam


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
        "borrowSizes": [1073741824],
        "waterMark": {
          "highWaterMark": 92,
          "lowWaterMark": 80
        }
    }
    """
    try:
        if isinstance(param, str):
            param = json.loads(param)
    except Exception as e:
        raise ValueError(f"JSON parse error: {e}") from e
    UbsVirtAgentWaterlineMemBorrow().ubs_virt_agent_waterline_mem_borrow(param=param)


if __name__ == "__main__":
    import sys
    main(param=sys.argv[1])
