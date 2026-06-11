#!/usr/local/python
# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2012-2024. All rights reserved.
import json
import os
import subprocess
from ubse.ubs_engine_topo import ubs_topo_node_list
from ubse.ubse_engine import ubs_engine_client_initialize, ubs_engine_client_finalize

if __name__ == '__main__':
    try:
        ubs_engine_client_initialize('')
    except RuntimeError as e:
        os.system(f"echo {-1}")
    node_list = ubs_topo_node_list()
    subprocess.run(['echo', "sdk res: "], check=True)

    keys = {
        'socket ids': 'socket-id',
        'numa ids': 'numa-id',
        'host name': 'hostname'
    }

    result_dict = {}
    for local_node in node_list:
        # 直接从对象属性获取数据，更加可靠
        slot_id = str(local_node.slot_id)

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
        result_dict[slot_id] = node_info

    # 打印格式化后的JSON
    subprocess.run(['echo', json.dumps(result_dict, indent=2)], check=True)
    ubs_engine_client_finalize()
