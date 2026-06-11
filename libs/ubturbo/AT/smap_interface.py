from typing import Any

from libs.ubturbo.AT.smap_global_var import CLI_PATH
from libs.ubturbo.AT.smap_common import search_vm


def smap_init_interface(self: Any, node: Any, mode: str) -> None:
    cmd_init = f'smap smap_init {mode}'
    ret = node.run({'command': ["cd {};./cli_client".format(CLI_PATH)], 'waitstr': 'root:/cli>', 'timeout': 5,
                    'input': ['attach 666', 'root:/cli>', cmd_init, 'root:/cli>', 'exit']})

    self.assertEqual(0, ret['rc'], msg='初始化失败')


def smap_stop_interface(self: Any, node: Any) -> None:
    cmd_stop = 'smap smap_stop'
    ret = node.run({'command': ["cd {};./cli_client".format(CLI_PATH)], 'waitstr': 'root:/cli>', 'timeout': 5,
                    'input': ['attach 666', 'root:/cli>', cmd_stop, 'root:/cli>', 'exit']})

    self.assertEqual(0, ret['rc'], msg='停止失败')


# 调用SmapRemove接口，进程数量为1，pid正确，pidType=0，返回码为0
def test_smap_remove_001(self: Any, node: Any, pid: str, mode: str) -> None:
    cmd_init = f'smap smap_init {mode}'
    cmd_mig_out = f'smap smap_mig_out 5 {pid} 0 {mode}'
    cmd_remove = f'smap smap_remove {pid} {mode}'
    cmd_stop = 'smap smap_stop'
    show_back_ret = 'ret(0)'
    ret = node.run({'command': ["cd {};./cli_client".format(CLI_PATH)], 'waitstr': 'root:/cli>', 'timeout': 5,
                    'input': ['attach 666', 'root:/cli>', cmd_init, 'root:/cli>', cmd_mig_out, show_back_ret,
                              cmd_remove, show_back_ret, cmd_stop, 'root:/cli>', 'exit']})

    self.assertEqual(0, ret['rc'], msg='移除进程结果不符合预期')


def test_smap_remove_002(self: Any, node: Any, pid: str) -> None:
    cmd_init = 'smap smap_init 1'
    cmd_mig_out = f'smap smap_mig_out 5 {pid} 0 1'
    cmd_remove = f'smap smap_remove {pid} 0'
    cmd_stop = 'smap smap_stop'
    show_back_ret = 'ret(-22)'
    ret = node.run({'command': ["cd {};./cli_client".format(CLI_PATH)], 'waitstr': 'root:/cli>', 'timeout': 5,
                    'input': ['attach 666', 'root:/cli>', cmd_init, 'root:/cli>', cmd_mig_out, show_back_ret,
                              cmd_remove, show_back_ret, cmd_stop, 'root:/cli>', 'exit']})

    self.assertEqual(0, ret['rc'], msg='移除进程结果不符合预期')


def test_smap_remove_003(self: Any, node: Any, pid: str) -> None:
    cmd_init = 'smap smap_init 1'
    cmd_remove = f'smap smap_remove {pid} 0'
    cmd_stop = 'smap smap_stop'
    show_back_ret = 'ret(-22)'
    ret = node.run({'command': ["cd {};./cli_client".format(CLI_PATH)], 'waitstr': 'root:/cli>', 'timeout': 5,
                    'input': ['attach 666', 'root:/cli>', cmd_init, 'root:/cli>', cmd_remove, show_back_ret,
                              cmd_stop, 'root:/cli>', 'exit']})

    self.assertEqual(0, ret['rc'], msg='移除进程结果不符合预期')


def test_smap_remove_004(self: Any, node: Any, pid: str, mode: str) -> None:
    cmd_init = f'smap smap_init {mode}'
    cmd_remove = f'smap smap_remove {pid} {mode}'
    cmd_stop = 'smap smap_stop'
    show_back_ret = 'ret(-22)'
    ret = node.run({'command': ["cd {};./cli_client".format(CLI_PATH)], 'waitstr': 'root:/cli>', 'timeout': 5,
                    'input': ['attach 666', 'root:/cli>', cmd_init, 'root:/cli>', cmd_remove, show_back_ret,
                              cmd_stop, 'root:/cli>', 'exit']})

    self.assertEqual(0, ret['rc'], msg='移除进程结果不符合预期')


def test_smap_remove_005(self: Any, node: Any, pid: str, mode: str) -> None:
    cmd_init = f'smap smap_init {mode}'
    cmd_mig_out = f'smap smap_mig_out 5 {pid} 0 {mode}'
    cmd_remove = f'smap smap_remove {pid} {mode}'
    cmd_stop = 'smap smap_stop'
    show_back_ret = 'ret(0)'
    show_back_err_ret = 'ret(-22)'
    ret = node.run({'command': ["cd {};./cli_client".format(CLI_PATH)], 'waitstr': 'root:/cli>', 'timeout': 5,
                    'input': ['attach 666', 'root:/cli>', cmd_init, 'root:/cli>', cmd_mig_out, show_back_ret,
                              cmd_remove, show_back_ret, cmd_remove, show_back_err_ret,
                              cmd_stop, 'root:/cli>', 'exit']})

    self.assertEqual(0, ret['rc'], msg='移除进程结果不符合预期')


def test_smap_remove_006(self: Any, node: Any, pid: str) -> None:
    cmd_init = f'smap smap_init 1'
    cmd_mig_out = f'smap smap_mig_out 5 {pid} 0 1'
    cmd_err_remove = f'smap smap_remove {pid} -1'
    cmd_remove = 'smap smap_remove {pid} 1'
    cmd_stop = 'smap smap_stop'
    show_back_ret = 'ret(0)'
    show_back_err_ret = 'ret(-22)'
    ret = node.run({'command': ["cd {};./cli_client".format(CLI_PATH)], 'waitstr': 'root:/cli>', 'timeout': 5,
                    'input': ['attach 666', 'root:/cli>', cmd_init, 'root:/cli>', cmd_mig_out, show_back_ret,
                              cmd_err_remove, show_back_err_ret, cmd_remove, show_back_ret, cmd_stop,
                              'root:/cli>', 'exit']})

    self.assertEqual(0, ret['rc'], msg='移除进程结果不符合预期')


def test_smap_black_001(self: Any, node: Any) -> None:
    p_name = 'redis'
    cmd_init = f'smap smap_init 1'
    cmd_black = f'smap smap_black {p_name}'
    cmd_stop = 'smap smap_stop'
    show_back_ret = 'ret(0)'
    ret = node.run({'command': ["cd {};./cli_client".format(CLI_PATH)], 'waitstr': 'root:/cli>', 'timeout': 5,
                    'input': ['attach 666', 'root:/cli>', cmd_init, 'root:/cli>', cmd_black, show_back_ret, cmd_stop,
                              'root:/cli>', 'exit']})

    self.assertEqual(0, ret['rc'], msg='加入黑名单结果不符合预期')


def test_smap_black_002(self: Any, node: Any) -> None:
    p_name = 'redis'
    cmd_black = f'smap smap_black {p_name}'
    show_back_ret = 'ret(-1)'
    ret = node.run({'command': ["cd {};./cli_client".format(CLI_PATH)], 'waitstr': 'root:/cli>', 'timeout': 5,
                    'input': ['attach 666', 'root:/cli>', cmd_black, show_back_ret, 'exit']})

    self.assertEqual(0, ret['rc'], msg='加入黑名单结果不符合预期')


def test_smap_black_003(self: Any, node: Any) -> None:
    p_name = 'chemu'
    pid = search_vm(self, node, p_name)
    cmd_init = f'smap smap_init 0'
    cmd_mig_out = f'smap smap_mig_out 5 {pid} 0 0'
    cmd_remove = f'smap smap_remove {pid} 0'
    cmd_black = f'smap smap_black {p_name}'
    cmd_stop = 'smap smap_stop'
    show_back_ret = 'ret(0)'
    show_back_false = 'ret(-17)'
    ret = node.run({'command': ["cd {};./cli_client".format(CLI_PATH)], 'waitstr': 'root:/cli>', 'timeout': 5,
                    'input': ['attach 666', 'root:/cli>', cmd_init, 'root:/cli>', cmd_mig_out, show_back_ret,
                              cmd_black, show_back_false, cmd_remove, show_back_ret, cmd_stop, 'root:/cli>', 'exit']})

    self.assertEqual(0, ret['rc'], msg='加入黑名单结果不符合预期')


def test_smap_black_004(self: Any, node: Any) -> None:
    p_name = 'asdfghjklhddfghjtyuitfvdfdsfssdffffdfdsfsgffdhhrdfgdfgdgdffdhfdsadad'
    cmd_init = f'smap smap_init 1'
    cmd_black = f'smap smap_black {p_name}'
    cmd_stop = 'smap smap_stop'
    show_back_ret = 'is invaild'
    ret = node.run({'command': ["cd {};./cli_client".format(CLI_PATH)], 'waitstr': 'root:/cli>', 'timeout': 5,
                    'input': ['attach 666', 'root:/cli>', cmd_init, 'root:/cli>', cmd_black, show_back_ret, cmd_stop,
                              'root:/cli>', 'exit']})

    self.assertEqual(0, ret['rc'], msg='加入黑名单结果不符合预期')


def test_smap_black_005(self: Any, node: Any) -> None:
    p_name_01 = 'qemu-kvm'
    p_name_02 = 'qemu-system-aarch64'
    cmd_init = f'smap smap_init 1'
    cmd_black_01 = f'smap smap_black {p_name_01}'
    cmd_black_02 = f'smap smap_black {p_name_02}'
    cmd_stop = 'smap smap_stop'
    show_back_ret = 'ret(-22)'
    ret = node.run({'command': ["cd {};./cli_client".format(CLI_PATH)], 'waitstr': 'root:/cli>', 'timeout': 5,
                    'input': ['attach 666', 'root:/cli>', cmd_init, 'root:/cli>', cmd_black_01, show_back_ret,
                              cmd_black_02, show_back_ret, cmd_stop, 'root:/cli>', 'exit']})

    self.assertEqual(0, ret['rc'], msg='加入黑名单结果不符合预期')


def test_smap_black_006(self: Any, node: Any) -> None:
    p_name = 'chemu'
    pid = search_vm(self, node, p_name)
    cmd_init = f'smap smap_init 1'
    cmd_mig_out = f'smap smap_mig_out 5 {pid} 25 0'
    cmd_black = f'smap smap_black {p_name}'
    cmd_stop = 'smap smap_stop'
    show_back_ret = 'ret(0)'
    show_back_false = 'ret(-1)'
    ret = node.run({'command': ["cd {};./cli_client".format(CLI_PATH)], 'waitstr': 'root:/cli>', 'timeout': 5,
                    'input': ['attach 666', 'root:/cli>', cmd_init, 'root:/cli>', cmd_black, show_back_ret,
                              cmd_mig_out, show_back_false, cmd_stop, 'root:/cli>', 'exit']})

    self.assertEqual(0, ret['rc'], msg='加入黑名单结果不符合预期')


def test_smap_black_007(self: Any, node: Any) -> None:
    p_name = 'redis'
    cmd_init = f'smap smap_init 1'
    cmd_black = f'smap smap_black {p_name}'
    cmd_stop = 'smap smap_stop'
    show_back_ret = 'ret(0)'
    ret = node.run({'command': ["cd {};./cli_client".format(CLI_PATH)], 'waitstr': 'root:/cli>', 'timeout': 5,
                    'input': ['attach 666', 'root:/cli>', cmd_init, 'root:/cli>', cmd_black, show_back_ret, cmd_black,
                              show_back_ret, cmd_stop, 'root:/cli>', 'exit']})

    self.assertEqual(0, ret['rc'], msg='加入黑名单结果不符合预期')


def test_smap_unblack_001(self: Any, node: Any) -> None:
    p_name = 'redis'
    cmd_init = f'smap smap_init 1'
    cmd_black = f'smap smap_black {p_name}'
    cmd_unblack = f'smap smap_unblack {p_name}'
    cmd_stop = 'smap smap_stop'
    show_back_ret = 'ret(0)'
    ret = node.run({'command': ["cd {};./cli_client".format(CLI_PATH)], 'waitstr': 'root:/cli>', 'timeout': 5,
                    'input': ['attach 666', 'root:/cli>', cmd_init, 'root:/cli>', cmd_black, show_back_ret,
                              cmd_unblack, show_back_ret, cmd_stop, 'root:/cli>', 'exit']})

    self.assertEqual(0, ret['rc'], msg='加入黑名单结果不符合预期')


def test_smap_unblack_002(self: Any, node: Any) -> None:
    p_name = 'redis'
    cmd_unblack = f'smap smap_unblack {p_name}'
    show_back_ret = 'ret(-1)'
    ret = node.run({'command': ["cd {};./cli_client".format(CLI_PATH)], 'waitstr': 'root:/cli>', 'timeout': 5,
                    'input': ['attach 666', 'root:/cli>', cmd_unblack, show_back_ret, 'exit']})

    self.assertEqual(0, ret['rc'], msg='加入黑名单结果不符合预期')


def test_smap_unblack_003(self: Any, node: Any) -> None:
    p_name = 'asdfghjklhddfghjtyuitfvdfdsfssdffffdfdsfsgffdhhrdfgdfgdgdffdhfdsadad'
    cmd_init = f'smap smap_init 1'
    cmd_unblack = f'smap smap_unblack {p_name}'
    cmd_stop = 'smap smap_stop'
    show_back_ret = 'is invaild'
    ret = node.run({'command': ["cd {};./cli_client".format(CLI_PATH)], 'waitstr': 'root:/cli>', 'timeout': 5,
                    'input': ['attach 666', 'root:/cli>', cmd_init, 'root:/cli>', cmd_unblack, show_back_ret, cmd_stop,
                              'root:/cli>', 'exit']})

    self.assertEqual(0, ret['rc'], msg='加入黑名单结果不符合预期')


def test_smap_unblack_004(self: Any, node: Any) -> None:
    p_name = 'redis'
    cmd_init = f'smap smap_init 1'
    cmd_unblack = f'smap smap_unblack {p_name}'
    cmd_stop = 'smap smap_stop'
    show_back_ret = 'ret(-22)'
    ret = node.run({'command': ["cd {};./cli_client".format(CLI_PATH)], 'waitstr': 'root:/cli>', 'timeout': 5,
                    'input': ['attach 666', 'root:/cli>', cmd_init, 'root:/cli>', cmd_unblack, show_back_ret,
                              cmd_stop, 'root:/cli>', 'exit']})

    self.assertEqual(0, ret['rc'], msg='加入黑名单结果不符合预期')
