# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2025-2025. All rights reserved.
import asyncio
from typing import List
from poc_tools.common.validator import validate_config, validate_vm_num_and_name, \
    validate_echo_line_format
from poc_tools.mem_free import mem_free
from poc_tools.common.config import init_config
from poc_tools.common.log import LOG, init_log
from poc_tools.common.utils import retry, send_pipe_scripts
from poc_tools.virsh_cmd import virsh_undefine_vm, virsh_destroy_vm
from poc_tools.vm_monitor import monitor_delete_vm, wait_vm_release_mem


async def get_vm_num_and_name():
    LOG.info("Get the number of vm and the name of the vm to be deleted.")
    echo = await send_pipe_scripts([["virsh", "list", "--all"]])
    output_lines = echo.splitlines()
    vm_lines = await get_valid_vm_lines(output_lines)
    if len(vm_lines) == 1:
        vm_line = vm_lines[0].strip()
        parts = vm_line.split()
        vm_name = await validate_echo_line_format(parts)
        return len(vm_lines), vm_name
    return len(vm_lines), None


async def destroy_active_vm_by_name(vm_name: str):
    try:
        echo = await send_pipe_scripts([["virsh", "list"]])
        output_lines = echo.splitlines()
        vm_line = await get_valid_vm_lines(output_lines)
        if vm_line:
            await virsh_destroy_vm(vm_name)
            return
        LOG.warning(f"Vm: {vm_name} is not alive.")
    except Exception as e:
        LOG.error("Destroy active vm by name failed due to %s", str(e))


async def get_valid_vm_lines(output_lines: List[str]):
    LOG.info("Start getting valid vm lines.")
    valid_lines = []
    for line in output_lines:
        line = line.strip()
        if not line or line.startswith('-----'):
            continue
        parts = line.split()
        if len(parts) >= 3 and (parts[0].isdigit() or parts[0] == '-'):
            valid_lines.append(line)
    LOG.debug(f"Get valid vm line: {valid_lines}")
    return valid_lines


async def delete():
    try:
        LOG.info("Start deleting vm.")
        await validate_config()
        vm_num, vm_name = await get_vm_num_and_name()
        await validate_vm_num_and_name(vm_num, vm_name)

        LOG.info("Start collecting the information of borrowed node.")
        await virsh_undefine_vm(vm_name)
        await destroy_active_vm_by_name(vm_name)
        LOG.info(f"Send script to delete vm: {vm_name} successful.")

        await monitor_delete_vm(vm_name)
        await retry(wait_vm_release_mem)
        LOG.info("Delete vm successful.")
        await retry(mem_free)
    except Exception as e:
        LOG.error(str(e))
        raise SystemExit(1) from e


if __name__ == "__main__":
    init_config()
    init_log()
    asyncio.run(delete())
