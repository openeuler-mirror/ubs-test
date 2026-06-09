
from typing import Union
from paramiko.ssh_exception import BadAuthenticationType
from threading import Thread
from libs.host.linux import Linux
from libs.ubturbo.common import basic


def copy(node: Linux, timeout: int = 300, **kwargs) -> Linux:
    """
    复制节点信息，新建一个连接。可以修改连接的部分信息
    示例：
        # 通过复制UB仿真节点连接信息，修改端口为22，创建到物理机的连接
        node_phy = copy(node_ub_simulate, port=22)
    :param node: 原节点对象
    :param timeout: 超时时间
    :param kwargs: 修改待复制节点的部分参数，如端口号
    :return:
    """
    params = {i: j for i, j in node.rawParams.items() if i not in ['command']}
    params['type_'] = params['type']
    del params['type']
    params.update(kwargs)
    node = create(**params, timeout=timeout)
    return node


def create(
        password: str,
        ipv4_address: str = None,
        username: str = 'root',
        port: Union[int, str] = 22,
        type_: str = 'standSSH',
        timeout: int = 300,
        **kwargs: str,
) -> Linux:
    """
    根据用户名、密码、ip创建新连接，返回对应节点对象
    :param password: 密码
    :param ipv4_address: ip地址
    :param username: 用户名 默认root
    :param port: 通信端口，默认22
    :param type_: 通信协议，默认为 'standSSH'，取值范围["storSSH", "standSSH", "local", "telnet", "xmlrpc"]
    :param timeout: 连接超时时间
    :param kwargs: 其他参数，包括：
        phy_address: UB仿真物理机ip
        ipv6_address: 主机的ipv6地址
        os: 主机操作系统类型
        detail: 节点信息 {'host_role': 'master'}
    :return: 新建节点对象
    """
    # 整理主机信息字典
    host_info = {
        'username': username,
        'password': password,
        'port': str(port),
        'type': type_,
        **kwargs
    }
    if ipv4_address:
        host_info['ipv4_address'] = ipv4_address
    elif not kwargs.get('ipv6_address', False):
        raise Exception('需要指定ipv4_address 或 ipv6_address')

    # 尝试创建连接
    host = None
    exception_word = ''

    def _create():
        nonlocal host, exception_word
        try:
            host = Linux.discover(host_info)
        except BadAuthenticationType:
            exception_word = '密码错误'

    ip = kwargs.get('phy_address') or ipv4_address or kwargs["ipv6_address"]
    check_sep = 5  # 检测是否连接成功的时间间隔 单位：s

    basic.logger.info(f'尝试连接{ip}:{port}')
    Thread(target=_create, daemon=True).start()
    basic.wait_until(
        lambda: bool(host or exception_word),
        timeout=timeout,
        check_sep=check_sep,
        msg=f'{ip}:{port}连接状态'
    )  # 等待连接
    if not host:
        raise Exception(f'{ip}连接失败 {exception_word}')

    return host


def makesure_connection_normal(node, **kwargs):
    """
    检测当前连接是否存在回显错乱，如果是，则重连，规避影响
    备注：
        回显错乱一般由
            1. 命令超时
            2. 命令或输出中包含waitstr
        两种情况导致。后果为后续所有命令/回显都会变成前一个回显/命令
        复现方式（情况2）：
            from libs.ubturbo.common import basic
            res = basic.run('echo @#>')  # 提前检测到终端提示符，认为命令已执行结束，此时标准输出为空
            print(res.stdout)  # 为空，而不是预期的“@#>”
    :param node:
    :param kwargs:
    :return:
    """
    basic.logger.info('检测是否存在回显错乱')
    stdout = basic.run(node, 'echo 测试消息', **kwargs).stdout
    if '测试消息\n' != stdout:
        basic.logger.warn('重连，避免被上一个用例回显错乱影响')
        node.reconnect()


