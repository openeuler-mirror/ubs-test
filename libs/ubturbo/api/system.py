#! /bin/python3
# -*- coding: utf-8 -*-
# 版权所有 (c) 华为技术有限公司 2012-2025
import shlex
import time
from ast import literal_eval
from datetime import datetime, timezone, timedelta
from typing import Optional, Union, List, Dict, Literal, Set

import libs.ubturbo.api.docker as docker
from libs.ubturbo.common import basic, string_utils
from libs.ubturbo.common.string_utils import STR_ENTER


def is_path_exist(node, path, is_folder=False) -> bool:
    """判断路径是否存在"""
    sign = "d" if is_folder else "f"
    return bool(basic.run(node, f"[ ! -{sign} {path} ]").rc)


def mkdir(node, path):
    """创建目录，支持一次创建多级不存在的目录"""
    return basic.run(node, f"mkdir -p {path}")


def cp(node, src, dest, force=True):
    """拷贝文件/目录"""
    args = "-r"
    if force:
        args += "f"
    return basic.run(node, f"/bin/cp {args} {src} {dest}")


def rm(node, path):
    """删除文件、目录"""
    return basic.run(node, f"rm -rf {path}")


def ls(node, path="") -> List[str]:
    """获取目录下所有文件、目录名"""
    arg = f'"{path}"' if path else ""
    res = basic.run(node, f'python -c \'print(__import__("os").listdir({arg}))\'')
    if not res.stdout:
        raise Exception(f"{arg}目录不存在")
    files = literal_eval(res.stdout)
    return files


def read_file(node, path):
    """读取文件内容"""
    res = basic.run(node, f"[ -f {path} ] && cat {path}")
    return res.stdout


def find_process(node, name, do_kill=0) -> Optional[int]:
    """根据名称查找进程 可选发送信号"""
    if do_kill is True:
        do_kill = 9
    pid = None
    res = basic.run(node, f'pgrep -f "{name}"')
    if res.stdout:
        pid_info = string_utils.get_table_content(res.stdout, rows=slice(0, -1))
        pids = [int(i[0]) for i in pid_info]
        basic.logger.info(f"pgrep -f {name}结果: {pids}")
        if pids:
            pid = pids[0]
    if pid is not None and do_kill:
        basic.run(node, f"kill -{do_kill} {pid}")
    return pid


def kill_by_name(node, name: str, do_kill: int = 2):
    """根据命令的一部分kill对应进程"""
    if do_kill is True:
        do_kill = 9
    return basic.run(node, f'kill -{do_kill} $(pgrep -f "{name}")')


def get_cmd_by_pid(node, pid: Union[int, str]) -> str:
    """根据pid获取对应命令"""
    res = basic.run(node, f"ps -p {pid} -o cmd=")
    return res.stdout


def get_memory_status(node, row_name: str = "Mem") -> Dict[str, str]:
    """解析free命令结果"""
    res = basic.run(node, "free")
    table = {}
    tb = string_utils.get_table_content(res.stdout, rows=slice(0, -1))
    head = tb[0]
    for ln in tb[1:]:
        if ln[0] == row_name + ":":
            for i, h in enumerate(head):
                table[h] = ln[i + 1]
            break
    return table


def is_module_inserted(node, module_name: str, auto_parse_name=True) -> bool:
    """检测指定内核是否已插入"""
    if auto_parse_name:
        module_name = module_name.split("/")[-1]
        if module_name.endswith(".ko"):
            module_name = module_name[:-3]
        module_name = module_name.replace("-", "_")
    res = basic.run(node, f'lsmod | awk \'$1 == "{module_name}" {{print}}\'')
    return bool(res.stdout.strip())


def rmmod(node, fn: str):
    """卸载模块"""
    res = basic.run(node, f"rmmod {fn}")
    if res.rc:
        basic.logger.warn(f"卸载 {fn} 报错")
    return res


def insmod(node, fn: str, *args: str, modprobe=False):
    """插入内核模块"""
    args = [arg or "" for arg in args]
    args = " ".join(args)
    if not modprobe:
        ins_cmd = "insmod"
    else:
        ins_cmd = "modprobe"
    res = basic.run(node, f"{ins_cmd} {fn} {args}")
    if res.rc:
        raise Exception(f"插入{fn}模块报错")


def yum_install(node, pkg_name, arg: str = None, timeout=120) -> bool:
    """yum安装软件包"""
    cmd = f"yum -y install {pkg_name}"
    if arg:
        cmd += f" {arg}"
    return basic.run(node, cmd, timeout=timeout).rc == 0


def check_yum_pkg_is_installed(node, pkg_list, arg: str = None, install_timeout=120):
    """判断yum包是否已安装"""
    for pkg in pkg_list:
        res = basic.run(node, f"yum list installed {pkg}", timeout=120)
        if res.rc:
            basic.logger.info(f"未安装{pkg},尝试安装")
            if not yum_install(node, pkg, arg, timeout=install_timeout):
                raise Exception(f"无法安装{pkg}")


def generate_filename_suffix_with_number(
    node, formater: str, length: int = 6, used_names: Set[str] = None
) -> str:
    """生成随机文件名"""
    used_names = used_names or set()
    start_index = 1
    while True:
        random_str = f"{start_index:0{length}}"
        fn = formater % random_str
        if not is_path_exist(node, fn) and fn not in used_names:
            return fn
        start_index += 1


def gcc_compile(node, src, dst=None, args="-lobmm") -> basic.Result:
    """编译单个c语言文件"""
    dst = dst or src.rstrip(".c")
    return basic.run(node, f"gcc {args} {src} -o {dst}")


def gcc_compile_all_c_files(node, folder, args="-lobmm"):
    """编译目录下所有以.c结尾的文件"""
    for file in ls(node, folder):
        if file.endswith(".c"):
            gcc_compile(node, f"{folder}/{file}", args=args)


def compile_cpp(node, src, dst=None, args="-lubturbo_client") -> basic.Result:
    """编译单个cpp语言文件"""
    dst = dst or src.rstrip(".cpp")
    return basic.run(node, f"g++ {args} {src} -o {dst}")


def grant_rx_permissions(node, user: str, group: str):
    return basic.run(node, f"sudo chown -R {user}:{group} /home/{user}")


def user_exists_on_remote(node, username) -> bool:
    """在远端检查用户是否存在"""
    result = basic.run(node, f"getent passwd {username}")
    user_exist = result.rc == 0
    basic.logger.info(f"{username} 存在状态: {user_exist}")
    return user_exist


def group_exists_on_remote(node, groupname) -> bool:
    """在远端检查组是否存在"""
    result = basic.run(node, f"getent group {groupname}")
    group_exist = result.rc == 0
    basic.logger.info(f"{groupname} 组存在状态: {group_exist}")
    return group_exist


def create_user_and_group_on_remote(node, username, groupname):
    """检查远端用户和组是否存在"""
    if not group_exists_on_remote(node, groupname):
        basic.logger.info(f"远端组 {groupname} 不存在，正在创建组 {groupname}.")
        basic.run(node, f"groupadd {groupname}")
    if not user_exists_on_remote(node, username):
        basic.run(node, f"useradd -m -g {groupname} {username}")
        basic.logger.info(f"远端用户 {username} 已创建，并添加到组 {groupname}.")


def remove_user_and_group(node, user):
    """在远程系统上删除用户和对应的组"""
    rm(node, f"/home/{user}")
    basic.logger.info(f"已删除用户 {user} 的主目录")
    basic.run(node, f"groupdel {user}")
    basic.logger.info(f"已删除用户组 {user}")
    basic.run(node, f"userdel {user}")
    basic.logger.info(f"已删除用户 {user}")


def update_udev_rules_on_remote(node, username, mode_value=None):
    udev_file_path = "/etc/udev/rules.d/99-obmm.rules"
    if not is_path_exist(node, udev_file_path):
        basic.logger.error(f"UDEV配置文件 {udev_file_path} 不存在！")
        return
    basic.run(node, f"sed -i 's/OWNER=\"[^\"]*\"/OWNER=\"{username}\"/' {udev_file_path}")
    basic.run(node, f"sed -i 's/GROUP=\"[^\"]*\"/GROUP=\"{username}\"/' {udev_file_path}")
    read_file(node, udev_file_path)


def get_time(node, date_format: str = '+"%b %e %T"'):
    """获取系统启动至今的时间"""
    res = basic.run(node, f"date {date_format}").stdout.strip(string_utils.STR_ENTER)
    return res


def find_message_in_log(
    node,
    start_time: str,
    target_log_path: str = "/var/log/messages",
    message: str = None,
    end_time: str = None,
    return_rc=True,
) -> Union[int, str]:
    """传入时间格式形如: Mar  6 11:44:58"""
    log_cmd = (
        f'awk \'$0 >= "{start_time}" && $0 <= "{end_time}"\' {target_log_path}'
        if end_time is not None
        else f'awk \'$0 >= "{start_time}"\' {target_log_path}'
    )
    if message is not None:
        log_cmd += f' | grep -v "/bin/bash" | grep -E "{message}"'
    res = basic.run(node, log_cmd)
    if return_rc:
        return res.rc
    return res.stdout.strip()


def find_multiple_messages_in_log(node, start_time, target_log_path, messages):
    """批量查找同一日志中的多个关键日志内容"""
    results = {}
    for msg in messages:
        res = find_message_in_log(
            node, start_time=start_time, target_log_path=target_log_path, message=msg
        )
        if res != 0:
            raise RuntimeError(f"Log message not found: '{msg}' in {target_log_path} (node: {node})")
        results[msg] = res
    return results


def ping(execute_node, target_ip: str, expect: bool = True, times: int = 5):
    """持续ping参考下面调用"""
    result = basic.run(execute_node, f"ping -w {times} {target_ip}")
    if result.rc and expect:
        basic.logger.info(f"{target_ip} ping不通")
        return 0
    if not result.rc and not expect:
        basic.logger.info(f"{target_ip} ping通了")
        return 0
    return 1


def touch(node, path, filename):
    mkdir(node, path)
    return basic.run(node, f"touch {path}/{filename}")


def dump_logs(node, case_name, log_dir="/var/log/ubse", output_dir="/var/log/ostest/"):
    """按照北京时间转储日志"""
    beijing_tz = timezone(timedelta(hours=8))
    basic.run(node, f"mkdir -p {output_dir}")
    timestamp = datetime.now(beijing_tz).strftime("%Y%m%d_%H%M%S")
    archive_name = f"{case_name}_{timestamp}.tar.gz"
    archive_path = output_dir + archive_name
    basic.run(node, f"tar -czvf {archive_path} {log_dir}")


def run_cpp(node, *args, background=False):
    """执行编译好的命令"""
    cmd = " ".join(shlex.quote(str(p)) for p in list(args))
    if background:
        cmd += " > /dev/null 2>&1 & sleep 1"
        res = basic.run(node, cmd)
        if "Exit" in res.stdout:
            res.rc = 5
        return res
    return basic.run(node, cmd)


def update_conf_file(
    node,
    path,
    key,
    value=None,
    mode: Literal["set", "delete", "comment", "uncomment"] = "set",
):
    """更新配置项"""
    active_regex = fr"^[[:space:]]*{key}[[:space:]]*=[[:space:]]*.*"
    comment_regex = fr"^[[:space:]]*#[[:space:]]*\({key}[[:space:]]*=[[:space:]]*.*\)"

    if mode == "delete":
        basic.run(node, f"sed -i '/{key}=.*/d' {path}")
        basic.logger.info(f"已删除配置项: {key}")
        return

    if mode == "comment":
        basic.run(node, f"sed -i 's|{active_regex}|# &|' {path}")
        basic.logger.info(f"已注释配置项: {key}")
        return

    if mode == "uncomment":
        basic.run(node, f"sed -i 's|{comment_regex}|\\1|' {path}")
        basic.logger.info(f"已打开配置项: {key}")
        return

    if mode == "set":
        has_active = basic.run(node, f"grep -q '{active_regex}' {path}").rc
        if has_active == 0:
            basic.run(node, f"sed -i 's|{active_regex}|{key}={value}|' {path}")
            return
        has_comment = basic.run(node, f"grep -q '{comment_regex}' {path}").rc
        if has_comment == 0:
            basic.run(node, f"sed -i 's|{comment_regex}|{key}={value}|' {path}")
            return
        basic.run(node, f"echo >> {path}")
        basic.run(node, f"echo '{key}={value}' >> {path}")
        return

    raise ValueError(f"未知 mode: {mode}")


def get_hostname(node):
    """查询主机名"""
    hostname = basic.run(node, "hostname").stdout.strip(STR_ENTER)
    return hostname


def symbolic_to_numeric(perm_string):
    """将文件权限-rw-r--r--，以'644'格式返回"""
    perm_string = perm_string[1:]
    mapping = {"r": 4, "w": 2, "x": 1, "-": 0}

    def calc_group(group):
        value = 0
        for c in group:
            value += mapping.get(c, 0)
        return str(value)

    groups = [perm_string[i:i + 3] for i in range(0, 9, 3)]
    numeric = "".join(calc_group(g) for g in groups)
    return numeric


def get_chown_and_permission(node, file_path):
    """获得某个文件的权限和属主"""
    ret = basic.run(node, f"ll {file_path}").stdout
    res_list = ret.strip().split()
    if res_list[0][0] == "d":
        raise ValueError(f"Error:{file_path} is a directory,not a file")
    info = {}
    info["permission"] = symbolic_to_numeric(res_list[0])
    info["chown"] = f"{res_list[2]}:{res_list[3]}"
    return info


def set_chown_and_permission(node, file_path, dest_file_path):
    """复制文件的属主和权限"""
    basic.run(node, f"ll {file_path}")
    info = get_chown_and_permission(node, file_path=file_path)
    chown = info.get("chown")
    permission = info.get("permission")
    basic.logger.info(f"文件{file_path}的属主为{chown},权限为{permission}")
    basic.run(node, f"chown {chown} {dest_file_path}", timeout=120)
    basic.run(node, f"chmod {permission} {dest_file_path}", timeout=120)
    basic.run(node, f"ll {dest_file_path}")


def dos2unix(node, path):
    basic.run(node, f"dos2unix {path}")


def filter_kernel_msg(
    node, keywords, expect_times=1, start_time=None, end_time=None, after_boot=None
):
    """根据环境重启后的时间开始搜索，检测journalctl日志"""
    if after_boot:
        start_time = basic.run(node, "uptime -s").stdout.strip()
        end_time = basic.run(
            node,
            f'date -d "$(date -d "$(uptime -s)" +"%a %b %e %I:%M:%S %p %Z %Y") +{after_boot} sec" +"%Y-%m-%d %H:%M:%S"',
        ).stdout.strip()
    res = basic.run(
        node,
        f'journalctl -k --since "{start_time}" --no-pager --until "{end_time}" | grep -m{expect_times} "{keywords}"',
    )
    count = res.stdout.count(keywords)
    if count >= expect_times:
        return True
    return False