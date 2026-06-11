"""Node run AW migrated from legency/testcase/ubscomm/hcom/lib/common/node_run_aw.py"""

import time
import logging
import paramiko

logger = logging.getLogger(__name__)


def node_run(node, command, directory=None, input_str=None, waitstr="@#>", timeout=600) -> dict:
    """Run command on node and return result dict."""
    if directory is not None and input_str is not None:
        res = node.run({
            'command': command,
            'cmd_timeout_interrupt': True,
            'directory': directory,
            'input': input_str,
            'waitstr': waitstr,
            'timeout': timeout
        })
    elif input_str is not None:
        res = node.run({
            'command': command,
            'cmd_timeout_interrupt': True,
            'input': input_str,
            'waitstr': waitstr,
            'timeout': timeout
        })
    elif directory is not None:
        res = node.run({
            'command': command,
            'cmd_timeout_interrupt': True,
            'directory': directory,
            'waitstr': waitstr,
            'timeout': timeout
        })
    else:
        res = node.run({
            'command': command,
            'cmd_timeout_interrupt': True,
            'waitstr': waitstr,
            'timeout': timeout
        })
    return res


def create_ssh(node):
    """Create SSH session connection."""
    if hasattr(node, 'phy_address'):
        ip = node.phy_address if node.phy_address else node.localIP
    else:
        ip = node.localIP
    port = int(node.port)
    username = node.username
    password = node.password
    trans = paramiko.Transport((ip, port))
    trans.connect(username=username, password=password)
    ssh = paramiko.SSHClient()
    ssh._transport = trans
    channel = ssh.invoke_shell()
    return channel, ssh


def close_ssh(sshs):
    """Close SSH session connections."""
    for ssh in sshs:
        ssh.close()


def send_cmd(ch, cmd, time_wait=1):
    """Send command through channel."""
    ch.send(cmd)
    time.sleep(time_wait)


def send_cmd_list(ch, cmd=None, time1=1, inputs=None, time2=1):
    """Send command list through channel with inputs."""
    ch.send(cmd)
    time.sleep(time1)
    if inputs is not None:
        for cmd in inputs:
            ch.send(f'{cmd}\n')
            time.sleep(time2)


def node_ssh(node):
    """Create SSH session and return Linux host object."""
    username = node.username
    password = node.password
    params = node.rawParams
    params.pop('command')
    from libs.host.linux import Linux
    Linux.discover(params)
    return Linux(username, password, params)