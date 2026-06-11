#!/usr/local/python
# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2012-2024. All rights reserved.
import os
import subprocess
from ubse.ubs_engine_topo import ubs_topo_node_local_get
from ubse.ubse_engine import ubs_engine_client_initialize, ubs_engine_client_finalize

if __name__ == '__main__':
    try:
        ubs_engine_client_initialize('')
    except RuntimeError as e:
        os.system(f"echo {-1}")
    local_node = ubs_topo_node_local_get()
    # 处理socket-id
    socket_ids = ', '.join(sorted([str(s) for s in local_node.socket_ids], key=int))

    # 处理numa-id
    numa_ids = [str(numa[0]) for numa in local_node.numa_ids]
    numa_ids_sorted = sorted(numa_ids, key=int)

    node_info = {
        'socket-id': socket_ids,
        'numa-id': numa_ids_sorted,
        'hostname': local_node.host_name
    }

    subprocess.run(['echo', f"sdk res: {node_info}"], check=True)
    ubs_engine_client_finalize()