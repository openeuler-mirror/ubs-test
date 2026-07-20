import re
import logging

logger = logging.getLogger(__name__)


def escape_sed_pattern(s: str) -> str:
    """转义 sed 正则模式内所有特殊元字符 . \ / [ ] ( ) * + ? ^ $"""
    return re.sub(r'([\.\\/\[\]()*+?^$])', r'\\\1', s)


def escape_sed_repl(s: str) -> str:
    """转义 sed 替换段特殊字符 & 和分隔符 #"""
    s = s.replace("&", r"\&")
    s = s.replace("#", r"\#")
    return s


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
    # 转义正则特殊字符
    esc_key = escape_sed_pattern(key)
    esc_val = escape_sed_repl(str(value))

    for node in nodes:
        # 使用 # 作为 sed 分隔符，避免路径/值中 / 冲突
        sed_cmd = (
            f"sed -i 's#{esc_key}[[:space:]]*=[[:space:]]*[^ ]*#{esc_key}={esc_val}#g' {file_path}"
        )
        node.run({'command': [sed_cmd]})

        # grep 同样转义 key，防止正则误匹配
        grep_cmd = f"grep -E '^{esc_key}=' {file_path}"
        res = node.run({'command': [grep_cmd]}).get('stdout')
        if res is None or len(res.strip()) == 0:
            return False

        # 提取实际值对比
        res = res.split('=')[1].split()[0].replace('"', "'")
        if res != str(value):
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