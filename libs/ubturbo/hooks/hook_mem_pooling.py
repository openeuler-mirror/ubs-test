"""
Hook functions for MemPooling tests.

Migrated from legacy lib/hooks/HookMemPooling.py
Contains utility functions for test setup and environment management.
"""

import time
from libs.ubturbo.common import basic, file_transport
from libs.ubturbo.api import numa, system

WORK_PATH = "/home/mempooling-test/"
PXE_PATH = "/images/qcow2/"


def mk_work_dir(node, parent_dir, dest_folder_name_list):
    """
    在一个文件夹下创建多个子文件夹，这些子文件夹处于一个层级
    """
    for dest_folder_name in dest_folder_name_list:
        system.mkdir(node, parent_dir + dest_folder_name)


def download_qcow(node):
    path = WORK_PATH + 'img/openEuler-22.03-LTS-SP1-aarch64.qcow2'
    if not system.is_path_exist(node, path, is_folder=False):
        file_transport.download_file(node, PXE_PATH + 'openEuler-22.03-LTS-SP1-aarch64_mempooling_img.qcow2',
                                     WORK_PATH + 'img/openEuler-22.03-LTS-SP1-aarch64.qcow2')


def check_and_start_lcne(nodes):
    """
    Check and start lcne service on all nodes.
    
    Args:
        nodes: List of node objects
    """
    for node in nodes:
        res = basic.run(node, "SYSTEMD_COLORS=0 systemctl status ubm --no-pager | grep 'Active: active'", timeout=60)
        if res.rc != 0:
            basic.run(node, "systemctl start ubm")
    
    for node in nodes:
        _ = wait_until_lcne_active(node)


def wait_until_lcne_active(node, check_sep=10, timeout=600):
    """
    Wait until lcne service is active on the node.
    
    Args:
        node: Node object
        check_sep: Check interval in seconds
        timeout: Maximum wait time in seconds
    
    Returns:
        True if lcne is active, False otherwise
    """
    def check_lcne():
        ret = basic.run(node, "systemctl status ubm --no-pager").stdout
        if 'ubm service ready start' in ret:
            return True
        else:
            return False
    
    return basic.wait_until(check_lcne, timeout=timeout, check_sep=check_sep,
                            msg='Check if lcne service is active on node') > 0


def load_smap_kos(node, env_module=None):
    """
    Load smap kernel modules on the node.
    
    Args:
        node: Node object
        env_module: Environment module (optional)
    """
    from libs.ubturbo.common import env
    from libs.ubturbo.api import system
    
    env_type = env.get_env_type(node)
    if env_type == env.HCCS:
        system.check_yum_pkg_is_installed(node, ["smap"])
        basic.run(node, "cd /lib/modules/smap/", timeout=120)
        basic.run(node, "insmod tracking-core.ko", timeout=120)
        basic.run(node, "insmod access-tracking.ko", timeout=120)
        basic.run(node, "rmmod smap_tiering", timeout=120)
        basic.run(node, "insmod smap_tiering.ko node_modes=5,5,5,5,5,5", timeout=120)
    if env_type == env.UB_simulation:
        basic.run(node, "rmmod hist_tracking", timeout=60)


def refill_obmm_mempool(node_list, size, refill_timeout=60000):
    """
    Refill obmm mempool.
    
    Args:
        node_list: List of node objects
        size: Mempool size in GB
        refill_timeout: Timeout in ms
    """
    from libs.ubturbo.api.mempooling import set_hugePage_all_numa, get_numaInfos

    for node in node_list:
        numacnt = numa.get_numa_count(node)
        hugepage = size // numacnt * 1024 // 2
        set_hugePage_all_numa(node, size=hugepage)

        ret = basic.run(node, 'cat /proc/cmdline | grep pmd_mapping=100%')
        if ret.rc != 0:
            raise Exception('Error: pmd_mapping expected to be 100%')

        basic.run(node, "rmmod obmm")
        basic.run(node,f"modprobe obmm mempool_size={size}G mempool_allocator=hugetlb_pmd")

    for node in node_list:
        basic.wait_until(
            condition_func=lambda: not any(info['HugePages_Free'] != 0 for info in get_numaInfos(node)),
            check_sep=10,
            timeout=3 * 60,
            expect_times=1,
            msg="Waiting for obmm mempool refill"
        )


def mk_mp_work_dir(node):
    mk_work_dir(node, parent_dir=WORK_PATH, dest_folder_name_list=['img', 'log', 'xml', 'hardware_xml', 'sdk',
                                                                   'mem_info'])
