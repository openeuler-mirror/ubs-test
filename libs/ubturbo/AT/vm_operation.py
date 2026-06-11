import time
from libs.utils.logger_compat import Log
logger = Log.getLogger("AT_Common")


def vm_suspend(self, node, name):
    check_vm_status_res = node.run({'command': ["virsh list --all"], 'waitstr': '#'})
    vm_status_output = check_vm_status_res['stdout']
    if name in vm_status_output and 'running' in vm_status_output:
        logger.info("虚机已启动")
    check_vm_status_res = node.run({'command': ["virsh suspend {}".format(name)], 'waitstr': '#'})
    self.assertEqual(0, check_vm_status_res['rc'], msg='虚机暂停失败')


def vm_resume(self, node, name):
    check_vm_status_res = node.run({'command': ["virsh list --all"], 'waitstr': '#'})
    vm_status_output = check_vm_status_res['stdout']
    if name in vm_status_output and 'paused' in vm_status_output:
        logger.info("虚机已暂停")
    check_vm_status_res = node.run({'command': ["virsh resume {}".format(name)], 'waitstr': '#'})
    self.assertEqual(0, check_vm_status_res['rc'], msg='虚机恢复失败')


