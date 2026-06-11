import re
import time
import logging


logger = logging.getLogger(__name__)
packages_path = '/opt/install/package'

def get_version(node, name):
    wait_time = 0
    while wait_time < 60:
        rpm_version_res = node.run({'command': [f"rpm -qi {name}"]})
        stderr = rpm_version_res.get('stderr')
        stdout = rpm_version_res.get('stdout')
        res1 = str(stdout) + str(stderr)
        if 'not installed' in res1:
            return False, False
        if stdout is not None:
            version_info = stdout.split('\r\nroot@#>')[0].split('\n')[:-5]
            version = version_info[1].split(': ')[1].split('\r')[0]
            release = version_info[2].split(': ')[1].split('\r')[0]
            return version, release
        wait_time = wait_time + 5
        time.sleep(5)
    return False, False


def rpm_action(node, action, package, tar_path=packages_path):
    actions = {
        'install': '-ivh',
        'install_force': '-ivh --force',
        'update': '-Uvh',
        'downgrade': '-Uvh --oldpackage',
        'uninstall': '-evh'
    }
    if action != 'uninstall':
        res = node.run({'command': [f'rpm {actions[action]} {tar_path}/{package}']})
        res = str(res.get('stdout')) + str(res.get('stderr'))
        if res is None:
            return False
        if '*' in package:
            return False
        name = re.match(r'^(.*?)-[0-9].*\.(?:rpm|noarch\.rpm|aarch64\.rpm)$', package).group(1)
        result, _ = get_version(node, name)
        if result:
            return True
        return False
    else:
        res = node.run({'command': [f'rpm {actions[action]} {package}']})
        res = str(res.get('stdout')) + str(res.get('stderr'))
        if res is None:
            return False
        result, _ = get_version(node, package)
        if result:
            return False
        return True


def exec_service(node, action, service_name='ubse'):
    res = node.run({'command': [f"systemctl {action} {service_name}"]})
    return str(res.get('stdout')) + str(res.get('stderr'))
