#! /bin/python3
# -*- coding: utf-8 -*-
# 版权所有 (c) 华为技术有限公司 2012-2025
from typing import Optional
from typing import List
from libs.ubturbo.common import basic
from libs.ubturbo.common import env
import libs.ubturbo.api.system as system


logger = basic.logger


# 本地文件目录
FOLDER_SYSTEM_RESOURCE = '/opt/install/package'
PATH_SMAP_TOOLS_EXECUTABLE = 'smap_tools_executable'
# 环境文件目录
DEFAULT_PATH_FOLDER = '/home'
FULL_PATH_TOOLS_EXECUTABLE = f'{DEFAULT_PATH_FOLDER}/{PATH_SMAP_TOOLS_EXECUTABLE}'
# 可执行文件名
EXECUTABLE_CLI_CLIENT = 'cli_client'
EXECUTABLE_CLI_SERVER = 'cli_server'
EXECUTABLE_SMAP_CLIENT = 'smap_client'

CONSOLE_BASE = 'root:/cli>'


def smap_operate_sequence(node, operation: List[str], timeout=30):
    """
    运行连续的smap工具操作
    """
    inputs = []
    for op in operation:
        inputs += [CONSOLE_BASE, op]

    basic.run(
        node,
        f'{FULL_PATH_TOOLS_EXECUTABLE}/{EXECUTABLE_CLI_CLIENT}',
        waitstr=CONSOLE_BASE,
        input=[
            'attach 666',
            *inputs,
            CONSOLE_BASE, 'exit',
            CONSOLE_BASE,
        ],
        timeout=timeout,
    )


def set_smap_remote_numa_info(node, mem_size, src_numa=0, des_numa=5, timeout=30):
    """
    迁移前指定远端可用内存大小
    """
    logger.info(f'迁移前指定远端可用内存大小')
    smap_operate_sequence(node, [f'smap set_smap_remote_numa_info {src_numa} {des_numa} {mem_size}'], timeout=timeout)


def mig_out(node, pid, percent, numa_index=5, polling_interval=5, timeout=30):
    """
    smap内存迁移
    :param node:
    :param pid: 虚拟机/进程 pid
    :param percent: 迁移比例 0~100
    :param numa_index: numa节点序号
    :param polling_interval: 查询远端numaused的间隔
    :param timeout:
    """
    logger.info(f'smap内存迁移 pid: {pid} percent: {percent}')
    smap_operate_sequence(node, [f'smap smap_mig_out {numa_index} {pid} {percent} 1'], timeout=timeout)
    wait_mig_out_complete(node, numa_index, polling_interval, timeout=timeout)


def wait_mig_out_complete(node, dest_numa=5, polling_interval=5, convergence=50, timeout=30):
    """
    轮询迁移至迁移完成
    :param node:
    :param dest_numa:迁移目标numa
    :param polling_interval:查询远端numaused的间隔
    :param convergence:收敛值,单位MB
    :param timeout:
    :return:
    """
    last_value: Optional[int] = None

    def condition():
        nonlocal last_value

        cmd = (
            f"cat /sys/devices/system/node/node{dest_numa}/meminfo "
            f"| grep HugePages_Free | awk '{{print $4}}'"
        )

        ret = basic.run(node, cmd)
        output = ret.output.strip()

        if not output or not output.isdigit():
            return False

        current_value = int(output)

        if last_value is None:
            last_value = current_value
            return False

        diff = abs(current_value - last_value)
        last_value = current_value

        return diff <= convergence

    return basic.wait_until(condition, polling_interval, timeout)


def smap_remove(node, pid):
    """
    在smap管理列表中注销进程pid
    :param pid: 虚拟机/进程 pid
    """
    logger.info(f'smap移除pid: {pid}')
    smap_operate_sequence(node, [f'smap smap_remove {pid} 1'])


def init_smap_requirements(node) -> dict:
    """
    初始化smap命令运行环境
    """
    logger.info(
        f'拉起smap工具后台进程:\n'
        f'{FULL_PATH_TOOLS_EXECUTABLE}/{EXECUTABLE_CLI_SERVER}\n'
        f'{FULL_PATH_TOOLS_EXECUTABLE}/{EXECUTABLE_SMAP_CLIENT}'
    )

    init_status = {
        EXECUTABLE_CLI_SERVER: True,
        EXECUTABLE_SMAP_CLIENT: True,
    }
    for executable in init_status:
        if not system.find_process(node, executable):
            init_status[executable] = False  # 记录初始状态为False（未启动）
            res = basic.run(node, f'nohup {FULL_PATH_TOOLS_EXECUTABLE}/{executable} 1>/dev/null 2>&1 & sleep 1')
            if 'Exit' in res.stdout:
                raise Exception("smap-cli初始化失败")

    basic.run(
        node,
        f'{FULL_PATH_TOOLS_EXECUTABLE}/{EXECUTABLE_CLI_CLIENT}',
        waitstr=CONSOLE_BASE,
        input=[
            'attach 666',
            CONSOLE_BASE, 'smap smap_init 1',
            CONSOLE_BASE, 'exit',
            CONSOLE_BASE,
        ]
    )

    return init_status


def restore_smap_requirements(node, init_status: dict):  # 恢复后台进程初始状态
    """
    关闭smap，恢复启动smap前，后台进程smap_client、cli_server启动状态
    :param init_status: init_bg函数返回值
    """
    logger.info('关闭smap： smap_stop')
    basic.run(
        node,
        f'{FULL_PATH_TOOLS_EXECUTABLE}/{EXECUTABLE_CLI_CLIENT}',
        waitstr=CONSOLE_BASE,
        input=[
            'attach 666',
            CONSOLE_BASE, 'smap smap_stop',
            CONSOLE_BASE, 'exit',
            CONSOLE_BASE,
        ]
    )

    for executable, status in init_status.items():
        if not status:
            logger.info(f'清理后台进程：{executable}')
            system.find_process(node, executable, do_kill=True)
        else:
            logger.info(f'进程{executable}初始化前已启动，不清理')


def make_sure_executable_exist(node, path=FULL_PATH_TOOLS_EXECUTABLE):
    """
    确保smap可执行文件存在
    每次重新复制文件并修改权限，确保版本最新
    """
    system.mkdir(node, path)
    for fn in [EXECUTABLE_SMAP_CLIENT, EXECUTABLE_CLI_SERVER, EXECUTABLE_CLI_CLIENT]:
        system.cp(node, f'{FOLDER_SYSTEM_RESOURCE}/{fn}', path)
    basic.run(node, f'chmod 777 {path}/*')


def make_sure_ko(node, scene='virtualization'):
    """
    确保smap ko已插入
    容器场景
        HCCS参数为：insmod smap_tiering.ko node_modes=5,5,5,5,5,5 smap_mode=2 smap_pgsize=0
        UB参数为：insmod smap_tiering.ko node_modes=5,5,5,5,5,5 smap_mode=2 smap_pgsize=0 smap_scene=2
    虚拟化场景
        HCCS参数为：insmod smap_tiering.ko node_modes=5,5,5,5,5,5
        UB参数为：insmod smap_tiering.ko node_modes=5,5,5,5,5,5 smap_scene=2
    """
    if not basic.run(node, 'lsmod | grep smap').rc:
        logger.info('已插入smap相关ko')
        return

    basic.run(node, 'cd /lib/modules/smap')
    basic.run(node, 'insmod tracking-core.ko')
    basic.run(node, 'insmod access-tracking.ko')

    if basic.run(node, 'lsmod | grep tracking').rc:
        logger.warn('ko插入失败：tracking-core.ko access-tracking.ko')

    cmd_parts = ["insmod", "smap_tiering.ko", "node_modes=5,5,5,5,5,5"]
    env_type = env.get_env_type(node)
    if env_type == env.UB_simulation:
        cmd_parts.append("smap_scene=2")

    if scene != 'virtualization':
        cmd_parts += [
            "smap_mode=2",
            "smap_pgsize=0"
        ]

    cmd_ins_tiering = " ".join(cmd_parts)
    basic.run(node, cmd_ins_tiering)

    if basic.run(node, 'lsmod | grep smap').rc:
        logger.warn(f'ko插入失败 命令：{cmd_ins_tiering}')

    basic.run(node, 'cd -')


def clear_smap_config(node):
    """
    使用SMAP动态库的进程切换用户需删除
    """
    basic.run(node, "killall smap_client")  # 撤销以root-cli用户执行的smap_init操作
    basic.run(node, "systemctl stop osturbo-daemon")  # 撤销以osturbo用户执行的smap_init操作
    system.rm(node, '/dev/shm/smap_config')


def prepare_smap_executables(node):
    """
    准备smap工具包运行环境
    """
    clear_smap_config(node)
    make_sure_ko(node)
    make_sure_executable_exist(node)
    return init_smap_requirements(node)


def clean_smap_executables(node, init_status):
    """
    清理smap工具环境，但不删除工具文件
    """
    restore_smap_requirements(node, init_status)
    clear_smap_config(node)