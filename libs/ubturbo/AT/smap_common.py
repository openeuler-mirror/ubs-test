import time
from libs.utils.logger_compat import Log
from libs.ubturbo.AT.smap_global_var import CLI_PATH, TARGET_DIR, REDIS_PATH
logger = Log.getLogger("AT_Common")


def cli_smap_mig_out(self, node, mode, pid, ratio):
    """
        函数说明: 内存迁出
        参数说明:
                self   (obj): 实例化用例对象
                node   (obj): 节点对象
                mode   (str)：场景id
                pid    (str)：进程id
                ratio  (str)：迁出比例
        函数返回:无
    """
    cmd_init = f'smap smap_init {mode}'
    cmd_mig_out = f'smap smap_mig_out 5 {pid} {ratio} {mode}'
    show_back_ret = 'ret(0)'
    t = node.run({'command': ["cd {};./cli_client".format(CLI_PATH)], 'waitstr': 'root:/cli>', 'timeout': 10,
                  'input': ['attach 666', 'root:/cli>', cmd_init, 'root:/cli>', cmd_mig_out, show_back_ret, 'exit']})

    self.assertEqual(0, t['rc'], msg='迁出失败')


def cli_smap_mig_back(self, node):
    """
        函数说明: 内存迁回
        参数说明:
                self   (obj): 实例化用例对象
                node   (obj): 节点对象
        函数返回:无
    """
    cmd_mig_back1 = 'smap smap_mig_back 5 0x68b000000000 0x68bfffffffff'
    cmd_mig_back2 = 'smap smap_mig_back 5 0x487000000000 0x487fffffffff'
    show_back_ret = 'ret(0)'
    ret = node.run({'command': ["cd {};./cli_client".format(CLI_PATH)], 'waitstr': 'root:/cli>', 'timeout': 5,
                    'input': ['attach 666', 'root:/cli>', cmd_mig_back1, show_back_ret, cmd_mig_back2,
                              show_back_ret, 'exit']})

    self.assertEqual(0, ret['rc'], msg='迁回失败')


def cli_smap_enable(self, node):
    """
        函数说明: 使能节点
        参数说明:
                self   (obj): 实例化用例对象
                node   (obj): 节点对象
        函数返回:无
    """
    cmd_enable = 'smap smap_enable 1 5'
    show_back_ret = 'ret(0)'
    ret = node.run({'command': ["cd {};./cli_client".format(CLI_PATH)], 'waitstr': 'root:/cli>', 'timeout': 5,
                    'input': ['attach 666', 'root:/cli>', cmd_enable, show_back_ret, 'exit']})

    self.assertEqual(0, ret['rc'], msg='使能失败')


def cli_smap_remove(self, node, pid, mode):
    """
        函数说明: 进程移除管理并关闭smap
        参数说明:
                self   (obj): 实例化用例对象
                node   (obj): 节点对象
                mode   (str)：场景id
                pid    (str)：进程id
        函数返回:无
    """
    cmd_remove = f'smap smap_remove {pid} {mode}'
    cmd_stop = 'smap smap_stop'
    show_back_ret = 'ret(0)'
    ret = node.run({'command': ["cd {};./cli_client".format(CLI_PATH)], 'waitstr': 'root:/cli>', 'timeout': 5,
                    'input': ['attach 666', 'root:/cli>', cmd_remove, show_back_ret, cmd_stop, 'root:/cli>', 'exit']})

    self.assertEqual(0, ret['rc'], msg='移除进程失败')


def search_pro(self, node, name):
    """
        函数说明: 内存迁出
        参数说明:
                self   (obj): 实例化用例对象
                node   (obj): 节点对象
                name   (str): 进程名称
        函数返回:无
    """
    pid_resu = node.run({'command': ["pgrep -f {}".format(name)], 'waitstr': '#'})
    if not pid_resu['stdout']:
        return -1
    pids = pid_resu['stdout']
    pid = ""
    for c in pids:
        if not c.isdigit():
            break
        pid = pid + c
    return pid


def smap_init(self, node):
    """
        函数说明: smap环境初始化 挂起必需进程 rm借内存
        参数说明:
                self   (obj): 实例化用例对象
                node   (obj): 节点对象
        函数返回:无
    """
    # 1.检查目录是否存在，如果不存在则创建
    show_target_dir_res = node.run({'command': ["[ -d {} ]".format(TARGET_DIR)], 'waitstr': '#'})
    if not show_target_dir_res['stdout']:
        node.run({'command': ["mkdir -p {}".format(TARGET_DIR)], 'waitstr': '#'})

    # 2.检查./bin/agent
    bin_agent_pid = search_pro(self, node, './bin/agent')
    # 2.1检查回显结果，如果不为空则说明./bin/agent正在运行
    if bin_agent_pid == -1:
        node.run({'command': ["source {}/exp.sh".format(CLI_PATH)], 'waitstr': '#'})
        start_cli_server_res = node.run({'command': ["nohup ./bin/agent conf/rm_agent_mem.conf &"], 'waitstr': '#'})
        if start_cli_server_res['rc'] != 0:
            logger.error("./bin/agent无法启动")
    logger.info("./bin/agent就绪")

    time.sleep(5)

    # 3.检查./bin/manager
    bin_manager_pid = search_pro(self, node, './bin/manager')
    # 3.1检查回显结果，如果不为空则说明./bin/manager正在运行
    if bin_manager_pid == -1:
        node.run({'command': ["source {}/exp.sh".format(CLI_PATH)], 'waitstr': '#'})
        start_cli_server_res = node.run({'command': ["nohup ./bin/manager conf/rm_mem.conf &"], 'waitstr': '#'})
        if start_cli_server_res['rc'] != 0:
            logger.error("./bin/manager无法启动")
    logger.info("./bin/manager就绪")

    time.sleep(5)

    # 4.检查从节点./bin/agent
    node.run({'command': ["ssh 90.90.113.64"], 'waitstr': '#'})
    # 4.1检查./bin/agent是否正在运行
    sla_bin_agent_pid = search_pro(self, node, './bin/agent')
    # 4.2如果./bin/agent没有运行
    if sla_bin_agent_pid == -1:
        # 4.3启动./bin/agent
        node.run({'command': ["source {}/exp.sh".format(CLI_PATH)], 'waitstr': '#'})
        start_agent_res = node.run({'command': ["nohup ./bin/agent conf/rm_agent_mem.conf &"], 'waitstr': '#'})
        if start_agent_res['rc'] != 0:
            logger.error("从节点./bin/agent无法启动")
    logger.info("从节点./bin/agent就绪")
    # 4.4退出从节点
    node.run({'command': ["exit"], 'waitstr': '#'})

    time.sleep(5)

    # 5.主节点检查cli_server smap_client
    # 5.1检查cli_server
    cli_server_pid = search_pro(self, node, 'cli_server')
    if cli_server_pid == -1:
        node.run({'command': ["cd {}/mf_release/bin/".format(CLI_PATH)], 'waitstr': '#'})
        node.run({'command': ["nohup ./cli_server &"], 'waitstr': '#'})

    smap_client_pid = search_pro(self, node, 'smap_client')
    if smap_client_pid == -1:
        node.run({'command': ["nohup export LD_LIBRARY_PATH=/lib/modules/smap:$LD_LIBRARY_PATH;"
                              "/home/smap_automation/mf_release/bin/smap_client &"], 'waitstr': '#'})

    node.run({'command': ["echo 9200 > /sys/devices/system/node/node0/hugepages/hugepages-2048kB/nr_hugepages"],
              'waitstr': '#'})

    time.sleep(5)

    # 6.rm借内存
    memfree = get_numastat(self, node, 'MemFree', 7)
    if int(memfree) == 0:
        node.run({'command': ["nohup ./cli_client"], 'waitstr': 'root:/cli>', 'timeout': 3,
                            'input': ['attach 456', 'root:/cli>', 'rm RackMemCtrlMalloc 4096 NODE11348 0 0',
                                      'root:/cli>',
                                      'exit']})
        node.run({'command': ["nohup ./cli_client"], 'waitstr': 'root:/cli>', 'timeout': 3,
                            'input': ['attach 456', 'root:/cli>', 'rm RackMemCtrlMalloc 4096 NODE11348 0 0',
                                      'root:/cli>',
                                      'exit']})
        node.run({'command': ["nohup ./cli_client"], 'waitstr': 'root:/cli>', 'timeout': 3,
                            'input': ['attach 456', 'root:/cli>', 'rm RackMemCtrlMalloc 1024 NODE11348 0 0',
                                      'root:/cli>',
                                      'exit']})

    time.sleep(5)

    # 7.分大页、起虚机
    # 7.1检查虚机是否启动
    check_vm_status_res = node.run({'command': ["virsh list --all"], 'waitstr': '#'})
    vm_status_output = check_vm_status_res['stdout']
    if 'smap-4u8g-2' in vm_status_output and 'running' in vm_status_output:
        logger.info("虚机 smap-4u8g-2 已启动")
        # 7.2虚机存在 销毁虚机
        node.run({'command': ["virsh destroy smap-4u8g-2"], 'waitstr': '#'})

    node.run({'command': ["echo 4200 > /sys/devices/system/node/node5/hugepages/hugepages-2048kB/nr_hugepages"],
              'waitstr': '#'})
    node.run({'command': ["virsh create /home/smap_automation/vm/xml/smap-4u8g-2.xml"], 'waitstr': '#'})


def smap_post(self, node):
    """
        函数说明: smap环境清理 杀死进程
        参数说明:
                self   (obj): 实例化用例对象
                node   (obj): 节点对象
        函数返回:无
    """
    # 主节点清理环境
    kill_pro(self, node, 'cli_client')
    kill_pro(self, node, 'smap_client')
    kill_pro(self, node, 'cli_server')
    kill_pro(self, node, './bin/manager')
    kill_pro(self, node, './bin/agent')

    # 从节点清理环境
    node.run({'command': ["ssh 90.90.113.64"], 'waitstr': '#'})
    kill_pro(self, node, './bin/agent')
    node.run({'command': ["exit"], 'waitstr': '#'})


def kill_pro(self, node, name):
    """
        函数说明: 杀进程
        参数说明:
                self   (obj): 实例化用例对象
                node   (obj): 节点对象
                name   (str): 进程号
        函数返回:无
    """
    pid = search_pro(self, node, name)
    if pid != -1:
        node.run({'command': ["kill -9 {}".format(pid)], 'waitstr': '#'})


def search_vm(self, node, name):
    """
        函数说明: 查虚机进程号
        参数说明:
                self   (obj): 实例化用例对象
                node   (obj): 节点对象
                name   (str): 虚机名
        函数返回:无
    """
    str = '{print $2}'
    vm_resu = node.run(
        {'command': ["ps -ef | grep {} | grep -v grep | awk '{}'".format(name, str)], 'waitstr': '#'})
    vm = vm_resu['stdout']
    vm_pid = ""
    for c in vm:
        if not c.isdigit():
            break
        vm_pid = vm_pid + c
    return vm_pid


def get_numastat(self, node, item, col):
    """
        函数说明: 获取numastat某一列字段对应值
        参数说明:
                self   (obj): 实例化用例对象
                node   (obj): 节点对象
                item   (str): 字段
                col    (int): 列号
        函数返回:无
    """
    str = '{print $(col)}'
    num_resu = node.run(
        {'command': ["numastat -vm | grep {} | awk -v col={} '{}'".format(item, col, str)], 'waitstr': '#'})
    pages = num_resu['stdout']
    page_num = ""
    for c in pages:
        if not c.isdigit():
            break
        page_num = page_num + c
    return page_num


def ko_init(self, node, mode):
    """
        函数说明: 插ko
        参数说明:
                self   (obj): 实例化用例对象
                node   (obj): 节点对象
                mode   (int): 场景
        函数返回:无
    """
    core_resu = node.run({'command': ['lsmod | grep tracking_core'], 'waitstr': '#'})
    access_resu = node.run({'command': ['lsmod | grep access-tracking'], 'waitstr': '#'})
    smap_resu = node.run({'command': ['lsmod | grep smap_tiering.ko'], 'waitstr': '#'})

    if core_resu['stout'] is not None:
        node.run({'command': ['rmmod tracking_core'], 'waitstr': '#'})
    if access_resu['stout'] is not None:
        node.run({'command': ['rmmod access-tracking'], 'waitstr': '#'})
    if smap_resu['stout'] is not None:
        node.run({'command': ['rmmod smap_tiering'], 'waitstr': '#'})

    node.run({'command': ['echo 0 > /proc/sys/kernel/numa_balancing'], 'waitstr': '#'})
    node.run({'command': ['echo 0 > /proc/sys/vm/compaction_proactiveness'], 'waitstr': '#'})
    node.run({'command': ['echo never > /sys/kernel/mm/transparent_hugepage/defrag'], 'waitstr': '#'})
    node.run({'command': ['echo never > /sys/kernel/mm/transparent_hugepage/enabled'], 'waitstr': '#'})

    node.run({'command': ['cd /lib/modules/smap'], 'waitstr': '#'})
    node.run({'command': ['insmod tracking-core.ko'], 'waitstr': '#'})
    node.run({'command': ['insmod access-tracking.ko'], 'waitstr': '#'})
    if mode == 1:
        # 虚拟化场景
        node.run({'command': ['insmod smap_tiering.ko node_modes=5,5,5,5,5,5 qemu_name=qemu-system-aarch64'], 'waitstr': '#'})
    elif mode == 0:
        # 通用场景
        node.run({'command': ['insmod smap_tiering.ko node_modes=5,5,5,5,5,5 smap_mode=2 smap_pgsize=0'], 'waitstr': '#'})
    else:
        logger.error('非法模式')


def check_mig_out(self, node, origin_mem, ratio):
    """
        函数说明: 检查迁出是否正常
        参数说明:
                self         (obj): 实例化用例对象
                node         (obj): 节点对象
                origin_mem   (str): 虚机大小
                ratio        (int): 迁出比例
        函数返回:无
    """
    ratio = ratio / 100.0
    mig_out_mem_less = origin_mem * (ratio - 0.05)
    mig_out_mem_more = origin_mem * (ratio + 0.05)

    if mig_out_mem_less < 0:
        mig_out_mem_less = 0

    if mig_out_mem_more > origin_mem:
        mig_out_mem_more = 1

    # 获取实际迁出大页
    remote_node_total = int(get_numastat(self, node, 'HugePages_Total', 7))
    remote_node_free = int(get_numastat(self, node, 'HugePages_Free', 7))
    mig_out_mem = remote_node_total - remote_node_free

    if mig_out_mem >= int(mig_out_mem_less) or mig_out_mem <= int(mig_out_mem_more):
        flag = 1
        logger.info('迁出成功，迁出比例正确')
    else:
        flag = -1
        logger.error('迁出失败，迁出比例错误')
    self.assertEqual(1, flag, msg='迁出失败，迁出比例错误')


def check_mig_back(self, node):
    """
        函数说明: 检查是否迁回
        参数说明:
                self   (obj): 实例化用例对象
                node   (obj): 节点对象
        函数返回:无
    """
    total_pages = int(get_numastat(self, node, 'HugePages_Total', 7))
    free_pages = int(get_numastat(self, node, 'HugePages_Free', 7))
    if total_pages != free_pages:
        flag = -1
        logger.error('迁回失败')
    else:
        flag = 1
        logger.info('迁回成功')
    self.assertEqual(1, flag, msg='迁出失败，迁出比例错误')


def cli_smap_mig_out_wrong(self, node, nid, mode, pid, ratio, show_back_ret):
    """
        函数说明: 内存迁出错误场景
        参数说明:
                self   (obj): 实例化用例对象
                node   (obj): 节点对象
                nid    (int): 远端节点
                mode   (str)：场景id
                pid    (str)：进程id
                ratio  (str)：迁出比例
                show_back_ret (str): 返回码
        函数返回:无
    """
    cmd_init = f'smap smap_init {mode}'
    cmd_mig_out = f'smap smap_mig_out {nid} {pid} {ratio} {mode}'
    t = node.run({'command': ["cd {};./cli_client".format(CLI_PATH)], 'waitstr': 'root:/cli>', 'timeout': 10,
                      'input': ['attach 666', 'root:/cli>', cmd_init, 'root:/cli>', cmd_mig_out, show_back_ret,
                                'exit']})

    self.assertEqual(0, t['rc'], msg='异常场景但是迁出成功')


def cli_smap_mig_out_wrong_type(self, node, nid, mode, pid, ratio, show_back_ret):
    """
        函数说明: 内存迁出错误场景
        参数说明:
                self   (obj): 实例化用例对象
                node   (obj): 节点对象
                nid    (int): 远端节点
                mode   (str)：场景id
                pid    (str)：进程id
                ratio  (str)：迁出比例
                show_back_ret (str): 返回码
        函数返回:无
    """
    mode = int(mode)
    mode_1, mode_2 = mode, 1 - mode
    cmd_init = f'smap smap_init {mode_1}'
    cmd_mig_out = f'smap smap_mig_out {nid} {pid} {ratio} {mode_2}'
    t = node.run({'command': ["cd {};./cli_client".format(CLI_PATH)], 'waitstr': 'root:/cli>', 'timeout': 10,
                      'input': ['attach 666', 'root:/cli>', cmd_init, 'root:/cli>', cmd_mig_out, show_back_ret,
                                'exit']})

    self.assertEqual(0, t['rc'], msg='异常场景但是迁出成功')


def cli_smap_mig_out_wrong_negative(self, node, nid, mode, pid, ratio):
    """
        函数说明: 内存迁出错误场景
        参数说明:
                self   (obj): 实例化用例对象
                node   (obj): 节点对象
                nid    (int): 远端节点
                mode   (str)：场景id
                pid    (str)：进程id
                ratio  (str)：迁出比例
                show_back_ret (str): 返回码
        函数返回:无
    """
    cmd_init = f'smap smap_init {mode}'
    cmd_mig_out = f'smap smap_mig_out {nid} {pid} {ratio} {mode}'
    resu = node.run({'command': ["cd {};./cli_client".format(CLI_PATH)], 'waitstr': 'root:/cli>', 'timeout': 10,
                      'input': ['attach 666', 'root:/cli>', cmd_init, 'root:/cli>', cmd_mig_out, 'root:/cli>',
                                'exit']})
    flag = 0
    if resu['stdout'] is not None and 'negative' in resu['stdout']:
        flag = 1
    self.assertEqual(1, flag, msg='异常场景但是迁出成功')


def redis_init(self, node):
    node.run({'command': ['cd {}'.format(REDIS_PATH)], 'waitstr': '#'})
    node.run({'command': ['cd {}'.format(REDIS_PATH)], 'waitstr': '#'})
    node.run({'command': ['taskset -c 0 ./src/redis-server ./redis.conf &'], 'waitstr': '#'})
    node.run({'command': ['./src/redis-benchmark -t set,get -n 10000000 -c 8 -r 1640000'
                          ' -h 127.0.0.1 -p 6379 -d 2048 --threads 8'], 'waitstr': '#'})




