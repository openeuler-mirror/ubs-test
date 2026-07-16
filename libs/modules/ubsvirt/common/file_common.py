import logging

logger = logging.getLogger(__name__)


def change_file(nodes, key, value, file_path):
    """
    功能：改变文件配置项的值
    参数：
        nodes: 执行节点
        key: 对应配置项
        value: 要改变的值
        file_path：文件路径
    返回值：True/False
    """
    for node in nodes:
        node.run({'command': [f"sed -i 's/{key}[[:space:]]*=[[:space:]]*[^ ]*/{key}={value}/g' {file_path}"]})

        res = node.run({'command': [f"grep -E '^{key}=' {file_path}"]}).get('stdout')
        if res is None:
            return False
        res = res.split('=')[1].split()[0].replace('"', "'")
        if res != value:
            return False
    return True


def copy_file(node, file_name, file_new_name):
    """
    功能：复制文件
    参数：
        node: 执行节点
        file_name: 原文件
        file_new_name: 复制后文件
    """
    if file_new_name is None:
        file_new_name = f"{file_name}.bak"
    command = f"\\cp -rp {file_name} {file_new_name}"
    node.run({'command': [command]})

def mv_file(node, file_name, file_new_name):
    """
    功能：移动文件
    参数：
        node: 执行节点
        file_name: 原文件
        file_new_name: 移动后文件
    """
    if file_new_name is None:
        file_new_name = f"{file_name}.bak"
    command = f"\\cp -rp {file_name} {file_new_name}"
    node.run({'command': [command]})
    node.run({'command': [f'rm -rf {file_name}']})