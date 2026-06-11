import re
from typing import Union
from libs.ubturbo.common import basic
from libs.ubturbo.common import cida


# 1）PXE服务器IP
NAME_FILE_SERVER = 'FILE_SERVER_IP'  # 环境中配置的文件服务器ip
DEFAULT_FILESERVER_IP = '90.91.106.84'  # 默认文件服务器，只适合HCCS日构建

# 2）环境类型
NAME_ENV_TYPE = 'ENV_TYPE'  # 环境类型变量名

HCCS = 'HCCS'  # 默认环境类型
UB_simulation = 'UB_simulation'
UB_hardware = 'UB_hardware'

# 3）节点角色
NAME_HOST_ROLE = 'host_role'  # 节点角色变量名，默认为None


# 缓存节点信息
cache_env_info = {}


def get_phy_ip(node) -> str:
    """
    获取节点物理ip
    主要用于判断仿真节点物理机ip
    :param node:
    :return:
    """
    return node.ip


def get_node_identity(node) -> str:
    """
    使用"节点ip:端口号"的字符串作为节点id，防止重连后无法判断是否同一个节点
    :param node:
    :return:
    """
    address = get_phy_ip(node)
    port = node.port
    identity = f'{address}:{port}'
    return identity


def get_env_info(node, argument: str, default: str = None, use_cache: bool = True):
    """
    从多个地方获取变量值（编号越小，优先级越高）。一般建议放在测试床detail标签中，修改次数会较少。
    配置方法：
    1）CIDA执行器透传参数
        在任务配置的“执行器透传参数”中，加入键值对: {"参数名": {"节点物理ip[:端口号]": "参数值"}}
        ip信息中的数字可使用*进行匹配（*不匹配非数字）
        示例，指定PXE服务器ip：
            1. 指定节点和对应文件服务器：{"FILE_SERVER_IP": {"61.47.17.136": "PXE服务器ip"}}
            2. 指定网段和对应文件服务器：{"FILE_SERVER_IP": {"61.47.17.*": "PXE服务器ip"}}
            3. 指定端口和对应文件服务器：{"FILE_SERVER_IP": {"61.47.17.136:5000": "PXE服务器ip"}}

    2）测试床detail标签
        示例，配置环境类型（ENV_TYPE）、PXE服务器ip（FILE_SERVER_IP）、节点类型（host_role），文件：test_bed.xml：
            <host id="2">
                <communication 节点信息，此处省略/>
                <detail ENV_TYPE="UB_simulation" FILE_SERVER_IP="61.47.17.121" host_role="agent01"/>
            </host>

    3）环境变量
        在/etc/profile或者~/.bashrc文件末尾增加"export 变量=值"语句
        示例，配置环境类型（ENV_TYPE）：
        在~/.bashrc文件末尾增加一行：
            export ENV_TYPE="UB_simulation"

    :param node:
    :param argument: 参数名，如"ENV_TYPE"
    :param default: 默认值
    :param use_cache: 使用本地字典缓存
    :return: 获取的值
    """
    # 设置初始值
    value = None

    # 拼接节点"ip:端口号"字符串作为节点判断对象
    address_port = get_node_identity(node)

    # 检查缓存中是否已有数据，如果有，直接返回
    if use_cache:
        value = cache_env_info.get((address_port, argument))
        if value is not None:
            return value

    # 检查CIDA执行器透传参数
    value_config = cida.CIDA_PARAMS.get(argument)
    # 通过正则表达式实现"*"匹配数字功能，方便参数配置
    if value is None and value_config:
        for k, v in value_config.items():
            if '*' in k:
                k = k.replace('*', '\\d+')
            if re.findall(k, address_port):
                value = v
                break

    # 检测测试床detail标签
    if value is None:
        value = (node.detail or {}).get(argument)

    # 检测环境变量
    if value is None:
        basic.logger.info(f'检测节点信息')
        res = basic.run(node, f'echo ${argument}', timeout=30)
        if not res.rc:  # 确保echo命令没有报错
            value = res.stdout.strip() or None  # 确保不是空字符串

    # 使用默认值
    if value is None:
        basic.logger.info(f'CIDA、测试床、环境变量均未定义，使用默认值: {default}')
        value = default

    # 放入缓存
    cache_env_info[(address_port, argument)] = value

    return value


def get_env_type(node) -> str:
    """检测环境类型（HCCS、UB仿真、UB硬件）"""
    return get_env_info(node, NAME_ENV_TYPE, default=HCCS)


def get_file_server_ip(node) -> str:
    """获取本机文件服务器ip"""
    return get_env_info(node, NAME_FILE_SERVER, default=DEFAULT_FILESERVER_IP)


def get_node_index(node) -> int:
    """
    获取节点排序
    :param node:
    :return:根据host_role属性判断序号：
                master: 0
                其他名称，末尾带数字: 数字
    """
    role = get_env_info(node, NAME_HOST_ROLE)
    if role == 'master':
        return 0
    elif role:  # 只要名称末尾带有数字即可，前缀不是必须为agent
        return int(re.findall(r'\d+$', role)[0])

    basic.logger.warn(f'请检查测试床是否配置主从节点（host_role属性），当前节点{get_node_identity(node)}无相关配置，视作主节点')
    return 0




