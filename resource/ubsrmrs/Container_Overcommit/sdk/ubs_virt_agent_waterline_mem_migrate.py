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
from ubs_virt_agent_types import MemMigrateRequestT
from ubs_virt_agent_base import UbsVirtAgentBase

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s"
)


class UbsVirtAgentWaterlineMemMigrate(UbsVirtAgentBase):
    """UbsVirtAgentWaterlineMemMigrate related interface"""

    def __init__(self):
        super().__init__()
        self.setup_mem_migrate_execute_functions()

    def ubs_virt_agent_waterline_mem_migrate(self, param: Dict[str, Any]):
        if not self.lib_ubse:
            raise ConnectionError("Native library not loaded")

        migrateRequestParam = self.build_migrate_request_param(param)

        result = self.lib_ubse.ubs_virt_agent_waterline_mem_migrate(
            ctypes.byref(migrateRequestParam),
        )
        if result != 0:
            raise RuntimeError(f"Failed to execute memory water migrate, error code: {result}")

        migrateExecuteRes = {
            "code": result
        }
        logging.info(json.dumps(migrateExecuteRes))
        return migrateExecuteRes

    def setup_mem_migrate_execute_functions(self):
        """
        Set the prototype of the relevant function
        详情参照libvirt_agent_container.h中ubs_virt_agent_waterline_mem_migrate的声明
        """
        self.lib_ubse.ubs_virt_agent_waterline_mem_migrate.argtypes = [
            ctypes.POINTER(MemMigrateRequestT)
        ]
        self.lib_ubse.ubs_virt_agent_waterline_mem_migrate.restype = ctypes.c_int32

        # Set the free function(If it exists)
        if hasattr(self.lib_ubse, 'free'):
            self.lib_ubse.free.argtypes = [ctypes.c_void_p]
            self.lib_ubse.free.restype = None

    def build_migrate_request_param(self, param: Dict[str, Any]):
        """
        将python字典转换为c++结构体
        """
        migrateRequestParam = MemMigrateRequestT()

        srcNid = param["borrowParam"]["srcNid"]
        if not isinstance(srcNid, str):
            raise ValueError("srcNid must be a string")
        migrateRequestParam.borrowParam.srcNid = srcNid.encode('utf-8')

        srcLocations = param["borrowParam"]["srcLocations"]
        migrateRequestParam.borrowParam.srcLocationsSize = len(srcLocations)
        for i, v in enumerate(srcLocations):
            migrateRequestParam.borrowParam.srcLocations[i].socketId = v["socketId"]
            migrateRequestParam.borrowParam.srcLocations[i].numaId = v["numaId"]

        borrowIds = param["borrowIds"]
        migrateRequestParam.borrowIdsSize = len(borrowIds)
        for i, v in enumerate(borrowIds):
            idStr = v.encode("utf-8")
            migrateRequestParam.borrowIds[i][:len(idStr)] = idStr
            migrateRequestParam.borrowIds[i][len(idStr)] = 0

        containerParam = param["containerParam"]
        migrateRequestParam.containerParamSize = len(containerParam)
        for i, v in enumerate(containerParam):
            migrateRequestParam.containerParam[i].pid = v["pid"]
            migrateRequestParam.containerParam[i].ratio = v["ratio"]
        return migrateRequestParam


def main(param):
    """
    param形如：
    {
        "borrowParam": {
            "srcNid": "1",
            "srcLocations": [
                {"socketId": 36,
                 "numaId": 0}
            ],
        }
        "borrowIds": ["2@0dfb53500edd83be6b5e0765da499740"],
        "containerParam": [
            {
                "pid": 1146409,
                "ratio": 100
            }, {
                "pid": 1146410,
                "ratio": 100
            }, {
                "pid": 1146411,
                "ratio": 100
            }
        ]
    }
    """
    try:
        if isinstance(param, str):
            param = json.loads(param)
    except Exception as e:
        raise ValueError(f"JSON parse error: {e}") from e
    UbsVirtAgentWaterlineMemMigrate().ubs_virt_agent_waterline_mem_migrate(param=param)


if __name__ == "__main__":
    import sys
    main(param=sys.argv[1])
