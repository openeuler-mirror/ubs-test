#!/usr/local/python
# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2012-2024. All rights reserved.
import os
import subprocess
from ubse.ubs_engine_topo import ubs_topo_link_list
from ubse.ubse_engine import ubs_engine_client_initialize, ubs_engine_client_finalize

if __name__ == '__main__':
    try:
        ubs_engine_client_initialize('')
    except RuntimeError as e:
        os.system(f"echo {-1}")
    cpu_links = ubs_topo_link_list()
    subprocess.run(['echo', "sdk res: "], check=True)

    # 集中输出所有链接信息
    output_lines = []
    for link in cpu_links:
        link_info = f"""INFO: ubse_cpu_topo_info(
      slot id={link.slot_id}
      socket ids={link.socket_id}
      port id={link.port_id}
      peer slot id={link.peer_slot_id}
      peer socket ids={link.peer_socket_id}
      peer port id={link.peer_port_id}
    )"""
        output_lines.append(link_info)

    # 使用单个echo命令输出所有内容
    full_output = "\n".join(output_lines)
    subprocess.run(['echo', full_output], check=True)
    ubs_engine_client_finalize()
