#!/usr/bin/python3
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
from __future__ import annotations

import ctypes

LIB_PATH = '/usr/lib64/libubs-virt-agent.so'


class UbsVirtAgentBase:
    def __init__(self):
        self.lib_ubse = None
        self._handle = None
        self._load_library()
        self._setup_function_prototypes()

    def ubs_virt_agent_initialize(self: str, conf_path: str | None = None) -> None:
        pass

    def ubs_virt_agent_finalize(self) -> None:
        pass

    def _setup_function_prototypes(self):
        pass

    def _load_library(self):
        self.lib_ubse = ctypes.CDLL(LIB_PATH)
