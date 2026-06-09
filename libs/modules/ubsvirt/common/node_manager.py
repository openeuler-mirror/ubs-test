import random
from libs.host.linux import Linux

path = "/root/manager"
manager_path = '/usr/local/softbus/ctrlbus'
cli_path = '/usr/local/softbus/ctrlbus-cli'


def get_new_connect(node: Linux):
    new_node = node.copy()
    new_node.login()
    return new_node


def get_new_sshconnect(node: Linux):
    new_node = node.copy()
    new_node.login()
    return new_node


def get_role_conf(node, path=manager_path):
    res = node.run({'command': [f"ls {path}/conf/rackmanager.conf"]})
    res = res.get("stdout").split("root@#>")[0]
    if res.find("No such file or directory") != -1:
        return False
    res = node.run({'command': [f"grep 'nodeRole' {path}/conf/rackmanager.conf"]})
    nodeRole = res.get('stdout').split("root@#>")[0].split('\r\n')[0]
    role = nodeRole.split('=')[1]
    if role.lower() != "master" or "agent":
        return False
    return role.lower()