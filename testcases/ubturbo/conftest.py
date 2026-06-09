# -*- coding: utf-8 -*-
"""
Pytest fixtures for UBTurbo MemPooling tests.

Converted from legacy HookMemPooling.py hook implementation.
"""

import os
import time

import pytest

from libs.ubturbo.api import mempooling_api as api
from libs.ubturbo.api import numa, sysSentry, system
from libs.ubturbo.api.mempooling import (
    MP_PATH,
    check_memborrow_mode,
    get_numaInfos,
    set_hugePage_all_numa,
    upload_sh_files,
    upload_vm_files,
    uplode_restart_file,
    wait_for_urma_22,
)
from libs.ubturbo.api.os_turbo import (
    RMRS_PLUGIN,
    SERVICE_NAME_OSTURBO_DAEMON,
    TURBO_MAIN_CONF,
    TURBO_PLUGIN_CONF,
    bakup_ubturbo_confs,
    restore_turbo_confs,
    upload_turbo_confs,
)
from libs.ubturbo.api.rack_manager import (
    MEMPOOLNG_PLUGIN_CONF,
    RACK_CONF,
    RACK_CONF_PATH,
    RACK_PLUGIN_ADIMISSION_CONF,
    RACK_PLUGIN_CONF_PATH,
    SERVICE_NAME_SCBUS_DAEMON,
    bakup_rack_confs,
    restore_rack_confs,
    upload_rack_confs,
    wait_for_master_consistency,
)
from libs.ubturbo.common import basic, env, file_transport
from libs.ubturbo.model import libvirt
from libs.ubturbo.model.mempoolingcli import REMOTE_MEMPOOLING_CLI_PATH
from libs.core.fixtures import resource_config

rack_conf_files = [RACK_PLUGIN_ADIMISSION_CONF]
rack_plugin_conf_files = [MEMPOOLNG_PLUGIN_CONF]
os_turbo_confs = [TURBO_PLUGIN_CONF, RMRS_PLUGIN, TURBO_MAIN_CONF]
WORK_PATH = "/home/mempooling-test/"
WORK_PATH_WITHOUT_SEP = "/home/mempooling-test"
PXE_PATH = "/images/qcow2/"
SDK_LOCAL_PATH = os.path.join(MP_PATH, "sdk/")
SDK_REMOTE_PATH = os.path.join(WORK_PATH, "sdk")
MEM_INFO_LOCAL_PATH = os.path.join(MP_PATH, "mem_info/")
MEM_INFO_REMOTE_PATH = os.path.join(WORK_PATH, "mem_info")
local_path = os.path.join(file_transport.THIS_PROJECT_PATH, "resource/MemPooling/")


def load_smap_kos(node):
    if env.get_env_type(node) == env.HCCS:
        system.check_yum_pkg_is_installed(node, ["smap"])
        basic.run(node, "cd /lib/modules/smap/", timeout=120)
        basic.run(node, "insmod tracking-core.ko", timeout=120)
        basic.run(node, "insmod access-tracking.ko", timeout=120)
        basic.run(node, "rmmod smap_tiering", timeout=120)
        basic.run(node, "insmod smap_tiering.ko node_modes=5,5,5,5,5,5", timeout=120)
    if env.get_env_type(node) == env.UB_simulation:
        basic.run(node, "rmmod hist_tracking", timeout=60)


def mk_work_dir(node, parent_dir, dest_folder_name_list):
    for dest_folder_name in dest_folder_name_list:
        system.mkdir(node, parent_dir + dest_folder_name)


def download_qcow(node):
    path = WORK_PATH + "img/openEuler-22.03-LTS-SP1-aarch64.qcow2"
    if not system.is_path_exist(node, path, is_folder=False):
        file_transport.download_file(
            node,
            PXE_PATH + "openEuler-22.03-LTS-SP1-aarch64_mempooling_img.qcow2",
            WORK_PATH + "img/openEuler-22.03-LTS-SP1-aarch64.qcow2",
        )


def upload_sdk_scripts(node):
    file_transport.send2remote(node, SDK_LOCAL_PATH + "call_virt.py", SDK_REMOTE_PATH)
    basic.run(node, f"ll {SDK_REMOTE_PATH}")


def upload_and_compile_mem_info_scripts(node):
    file_transport.send2remote(
        node, MEM_INFO_LOCAL_PATH + "getAllBorrowInfo.c", MEM_INFO_REMOTE_PATH
    )
    basic.run(node, f"cd {MEM_INFO_REMOTE_PATH}")
    basic.run(node, f"ll")
    basic.run(node, "gcc getAllBorrowInfo.c -o getAllBorrowInfo -I /usr/include/ubse -lubse-client")


def refill_obmm_mempool(node_list, size, refill_timeout=60000):
    if env.get_env_type(node_list[0]) == env.UB_simulation:
        skip_cache_maintain = "true"
    else:
        skip_cache_maintain = "false"

    for node in node_list:
        numacnt = numa.get_numa_count(node)
        hugepage = size // numacnt * 1024 // 2
        set_hugePage_all_numa(node, size=hugepage)
        cur_mempool_size = numa.get_obmm_mempool_total_ub(node)
        ret = basic.run(node, "cat /proc/cmdline | grep pmd_mapping=100%")
        if ret.rc != 0:
            raise Exception("异常：pmd_mapping预期等于100%")
        if cur_mempool_size != size:
            basic.logger.info(f"当前环境mempool_size为{cur_mempool_size}GB,重新设置为{size}GB")
            basic.run(node, "rmmod ham_migrate")
            basic.run(node, "rmmod obmm")
            basic.run(
                node,
                f"modprobe obmm mempool_refill_timeout=60000 mempool_size={size}G mempool_allocator=hugetlb_pmd skip_cache_maintain={skip_cache_maintain}",
            )
            basic.run(node, "insmod /lib/modules/ham/ham_migrate.ko")

    for node in node_list:
        basic.wait_until(
            condition_func=lambda: not any(
                info["HugePages_Free"] != 0 for info in get_numaInfos(node)
            ),
            check_sep=10,
            timeout=600,
            expect_times=1,
            msg="等待obmm蓄水池重新填充",
        )


def install_mempooling_cli(node):
    rack_lib_path = "/usr/lib64"
    package_path = "/opt/install/package/"
    file_transport.send2remote(node, local_path + "mempoolingcli", package_path)
    basic.run(node, f"mkdir -p {REMOTE_MEMPOOLING_CLI_PATH}")
    basic.run(
        node,
        f"yes | cp {package_path}/mempoolingcli/cli_client_mempooling {REMOTE_MEMPOOLING_CLI_PATH}/cli_client",
        timeout=300,
    )
    basic.run(
        node,
        f"yes | cp {package_path}/mempoolingcli/cli_server_mempooling {REMOTE_MEMPOOLING_CLI_PATH}/cli_server",
        timeout=300,
    )
    basic.run(
        node,
        f"yes | cp {package_path}/mempoolingcli/libmempoolingcli.so {rack_lib_path}",
        timeout=300,
    )
    basic.run(
        node,
        f"yes | cp {package_path}/mempoolingcli/plugin_mempoolingcli.conf {RACK_PLUGIN_CONF_PATH}",
        timeout=300,
    )
    basic.run(node, f"chown root:root {rack_lib_path}*")
    basic.run(node, f"chmod 755 {rack_lib_path}*")
    basic.run(node, f"chown root:root {RACK_PLUGIN_CONF_PATH}*")
    basic.run(node, f"chmod 644 {RACK_PLUGIN_CONF_PATH}*")
    basic.run(node, f"chmod 755 {REMOTE_MEMPOOLING_CLI_PATH}/*")


@pytest.fixture(scope="session")
def mempooling_environment(request):
    """
    Session-scoped fixture for MemPooling test environment setup and teardown.

    Provides:
    - Environment initialization (urma devices, obmm mempool, work directories)
    - Configuration file backup and replacement
    - Service restart and verification
    - Cleanup after all tests complete

    Yields:
        dict: Environment information including nodes and configuration
    """
    nodes = request.config.getoption("--nodes", default=None)
    if not nodes:
        raise ValueError("Nodes must be provided via --nodes option")

    nodemaster = nodes[0]
    nodeagent = nodes[1] if len(nodes) > 1 else None
    num_of_numa = numa.get_numa_count_with_cpu(nodemaster)

    if env.get_env_type(nodemaster) == env.UB_simulation:
        hook_timeout = 600
    else:
        hook_timeout = 180

    node_list = nodes

    basic.logger.tcStep("0、检查环境上urma设备是否加载完成")
    wait_for_urma_22(nodes)

    basic.logger.tcStep("1、关闭ubse、ubturbo,删除smap记录文件,重设碎片场景,清空ubse数据库")
    for node in node_list:
        ret = basic.run(node, f"systemctl stop {SERVICE_NAME_SCBUS_DAEMON}", timeout=hook_timeout)
        if ret.rc != 0:
            raise Exception(f"停止ubse超过{hook_timeout}s未返回，任务结束")
        ret = basic.run(node, f"systemctl stop {SERVICE_NAME_OSTURBO_DAEMON}", timeout=hook_timeout)
        if ret.rc != 0:
            raise Exception(f"停止ubturbo超过{hook_timeout}s未返回，任务结束")
        basic.run(node, f"rm -fr /var/lib/ubse/data/* /var/lib/ubse/sync/*", timeout=hook_timeout)
        basic.run(node, f"ll /var/lib/ubse/*", timeout=hook_timeout)
        basic.run(node, f"rm -fr /dev/shm/smap_config", timeout=hook_timeout)
        basic.run(node, f"rm -fr /dev/shm/ubturbo_page_type.dat", timeout=hook_timeout)

    basic.logger.tcStep("2、停止ubse服务后，重设obmm蓄水池")
    refill_obmm_mempool(node_list, 8 * num_of_numa)

    basic.logger.info("删除原有工作路径上文件")
    for node in nodes:
        basic.run(node, "rm -rf /home/mempooling-test")

    nodeIdx = 1
    for node in node_list:
        titleStr = f"3-{nodeIdx}"
        basic.logger.tcStep(f"{titleStr}、修改节点配置")

        basic.logger.tcSubStep(f"{titleStr}.1、创建工作路径并下载依赖镜像")
        mk_work_dir(
            node,
            parent_dir=WORK_PATH,
            dest_folder_name_list=["img", "log", "xml", "hardware_xml", "sdk", "mem_info"],
        )
        download_qcow(node)

        basic.logger.tcSubStep(f"{titleStr}.2、重插smap")
        load_smap_kos(node)

        basic.logger.tcSubStep(f"{titleStr}.3、备份原始配置文件")
        ubse_plugin_admission_conf_info = system.get_chown_and_permission(
            node, file_path=f"{RACK_CONF_PATH+RACK_PLUGIN_ADIMISSION_CONF}"
        )
        bakup_rack_confs(node, rack_conf_files, plugin=False, mode="mv")
        bakup_rack_confs(node, rack_plugin_conf_files, plugin=True, mode="mv")
        bakup_rack_confs(node, [RACK_CONF], mode="cp")
        bakup_ubturbo_confs(node, turbo_conf_list=os_turbo_confs, mode="mv")

        basic.logger.tcSubStep(f"{titleStr}.4、替换内存碎片配置文件，上传所需xml文件")
        upload_rack_confs(
            node,
            local_path=MP_PATH + "rack_conf",
            remote_tmp_path=WORK_PATH + "rack_conf",
            rack_conf_files=rack_conf_files,
            plugin=False,
            set_conf_chown=ubse_plugin_admission_conf_info.get("chown"),
            permission=ubse_plugin_admission_conf_info.get("permission"),
        )

        upload_rack_confs(
            node,
            local_path=MP_PATH + "rack_plugin_conf",
            remote_tmp_path=WORK_PATH + "rack_plugin_conf",
            rack_conf_files=rack_plugin_conf_files,
            plugin=True,
            set_conf_chown="root:root",
            permission=644,
        )

        upload_turbo_confs(
            node,
            local_path=MP_PATH + "os_turbo_conf",
            remote_tmp_path=WORK_PATH + "os_turbo_conf",
            turbo_conf_list=os_turbo_confs,
            set_conf_chown="ubturbo:ubturbo",
            permission=600,
        )

        upload_vm_files(node)
        upload_sh_files(node)
        upload_sdk_scripts(node)
        upload_and_compile_mem_info_scripts(node)

        basic.logger.tcSubStep(f"{titleStr}.5、上传所需重启sh文件")
        uplode_restart_file(node)

        file_transport.send2remote(node, MP_PATH + "chemu.c", WORK_PATH_WITHOUT_SEP)
        system.gcc_compile(node, src=WORK_PATH + "chemu.c", dst=WORK_PATH + "chemu", args="")
        nodeIdx += 1

    basic.logger.tcStep("4、安装sysSentry、mempoolingcli")
    for node in nodes:
        sysSentry.install_sySentry(node)
        install_mempooling_cli(node)
    for node in nodes:
        basic.run(node, "sentryctl list")

    basic.logger.tcStep("5、重启服务")
    for node in node_list:
        ret = basic.run(
            node, f"systemctl restart {SERVICE_NAME_OSTURBO_DAEMON}", timeout=hook_timeout
        )
        if ret.rc != 0:
            raise Exception(f"重启ubturbo超过{hook_timeout}s未返回，任务结束")
    time.sleep(10)

    for node in node_list:
        ret = basic.run(
            node, f"systemctl restart {SERVICE_NAME_SCBUS_DAEMON}", timeout=hook_timeout
        )
        if ret.rc != 0:
            raise Exception(f"重启ubse超过{hook_timeout}s未返回，任务结束")
    basic.logger.info(f"等待rackmanager启动中")
    wait_for_master_consistency(nodes)

    basic.logger.tcStep("6、开启vm插件内存碎片场景")
    if check_memborrow_mode(nodes):
        wait_for_master_consistency(nodes)
        basic.logger.info(f"mxe启动成功，内存碎片模式")
    else:
        raise Exception(f"mxe启动有误，非内存碎片模式")

    basic.logger.tcStep("7、关闭ubs-scheduler-agent.service服务")
    for node in node_list:
        ret = basic.run(node, "systemctl stop ubs-scheduler-agent.service", timeout=hook_timeout)

    yield {
        "nodes": nodes,
        "nodemaster": nodemaster,
        "nodeagent": nodeagent,
        "num_of_numa": num_of_numa,
    }

    for node in node_list:
        libvirt.TempVirtualMachine.clear_all(node)
    for node_id, node in enumerate(node_list):
        ret = api.function_return(node, node_id)
        basic.logger.info(f"ret: {ret}")
        basic.run(node_list[node_id], "numastat -cvm")
    for node in node_list:
        basic.run(node, f"bash {RACK_CONF_PATH}/shutdown.sh", timeout=120)
        basic.run(node, f"systemctl stop {SERVICE_NAME_OSTURBO_DAEMON}", timeout=120)
    for node in node_list:
        restore_rack_confs(node, rack_conf_files, plugin=False)
        restore_rack_confs(node, [RACK_CONF], plugin=False)
        restore_rack_confs(node, rack_plugin_conf_files, plugin=True)
        restore_turbo_confs(node, os_turbo_confs)
    for node in node_list:
        basic.run(node, f"systemctl restart {SERVICE_NAME_OSTURBO_DAEMON}", timeout=120)
    for node in node_list:
        basic.run(node, f"systemctl restart {SERVICE_NAME_SCBUS_DAEMON}", timeout=120)
    wait_for_master_consistency(node_list)
