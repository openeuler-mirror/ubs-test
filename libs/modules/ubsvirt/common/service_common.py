import logging
import time

logger = logging.getLogger(__name__)


def wait_ubse_status(node, nodes, timeout, wait_interval):
    """
    功能：判断ubse状态是否正常
    参数：
        node: 查询节点
        nodes: 所有节点
        timeout: 查询时间
        wait_interval: 查询间隔
    返回值：rpm动作返回回显信息
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        flag = True
        status_dict = get_ubse_status(node)
        for ssh_node in nodes:
            host_name = ssh_node.getHostname()
            if host_name == 'controller' and ssh_node != 22:
                continue
            if status_dict.get(host_name) != 'ok':
                flag = False
                break
        if flag:
            time.sleep(30)  # ubse进程恢复后再等待30s，提高用例稳定性
            return True
        time.sleep(wait_interval)
    return False


def get_ubse_status(node):
    """
    功能：获取ubse状态
    参数：
        node: 执行节点
    返回值：status_dict
    """
    status_dict = {}
    res = node.run({'command': [f'sudo -u ubse ubsectl check memory']}).get('stdout')
    if res:
        lines = res.splitlines()
        for line in lines:
            line = line.strip()
            if line and not line.startswith(('-', 'root')) and 'node' not in line:
                parts = line.split()
                node_str = parts[0]
                status = parts[4].rstrip(';')
                base_node = node_str.split('(')[0] if '(' in node_str else node_str
                status_dict[base_node] = status
    return status_dict


def exec_service(node, action, service_name, timeout=10):
    """
    功能：systemctl动作并返回回显信息
    参数：
        nodes: 执行节点
        action: 执行动作
        timeout: 命令执行返回时间
    返回值：rpm动作返回回显信息
    """
    res = node.run({'command': [f'systemctl {action} {service_name}'], 'timeout': timeout})
    return str(res.get('stdout')) + str(res.get('stderr'))