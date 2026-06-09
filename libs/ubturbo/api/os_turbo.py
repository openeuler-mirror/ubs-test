#! /bin/python3
# -*- coding: utf-8 -*-
# 版权所有 (c) 华为技术有限公司 2012-2025

"""
功能：osturbo服务、turbo框架-api测试(turbotest插件)、插件rmrs-api测试相关操作
"""

import os
import time
from typing import Literal
from libs.ubturbo.common import basic, file_transport
import libs.ubturbo.api.system as system
import re

from libs.ubturbo.model import systemctl

MIRROR_PATH = "/mnt/Packages/"

# osturbo服务基础路径
SERVICE_NAME_OSTURBO_DAEMON = 'ubturbo'
TURBO_WORK_PATH = '/opt/ubturbo'
OS_TURBO_CONF_PATH = f'{TURBO_WORK_PATH}/conf/'
TURBO_CONF_PATH = f'{TURBO_WORK_PATH}/conf'
TURBO_LIB_PATH = f'{TURBO_WORK_PATH}/lib'
TURBO_LOG_PATH = '/var/log/ubturbo'
# osturbo主程序相关配置、日志路径
TURBO_MAIN_CONF = 'ubturbo.conf'
TURBO_PLUGIN_CONF = 'ubturbo_plugin_admission.conf'
TURBO_MAIN_CONF_PATH = f'{TURBO_CONF_PATH}/ubturbo.conf'
TURBO_PLUGIN_CONF_PATH = f'{TURBO_CONF_PATH}/ubturbo_plugin_admission.conf'
TURBO_MAIN_LOG_PATH = f'{TURBO_LOG_PATH}/ubturbo.log'
TURBO_MAIN_SO_NAME = 'ubturbo_client'
TURBO_START_TIME = '/home/autotest/os/turbo_start_time'  # turbo服务启动时间
# rmrs插件相关配置路径
RMRS_PLUGIN = 'plugin_rmrs.conf'
RMRS_PLUGIN_CONF_PATH = f'{TURBO_CONF_PATH}/plugin_rmrs.conf'
# turbotest测试插件相关配置、日志路径
TURBO_TEST_PLUGIN_NAME = 'turbotest'
TURBO_TEST_SO_NAME = f'lib{TURBO_TEST_PLUGIN_NAME}_ubturbo_plugin'
TURBO_TEST_CONF_NAME = f'plugin_{TURBO_TEST_PLUGIN_NAME}'
TURBO_TEST_SO_PATH = f'{TURBO_LIB_PATH}/{TURBO_TEST_SO_NAME}.so'
TURBO_TEST_CONF_PATH = f'{TURBO_CONF_PATH}/{TURBO_TEST_CONF_NAME}.conf'
TURBO_TEST_LOG_PATH = f'{TURBO_LOG_PATH}/{TURBO_TEST_PLUGIN_NAME}.log'
TURBO_TEST_BASECASE_LOG_PATH = '/var/log/call_ipc_testfunc.log'
# 文件传输相关路径
TURBO_TEST_LOCAL_FILE_PATH = 'resource/OSTurbo/UBTurbo_API'  # 代码仓中框架api文件路径
RMRS_TEST_LOCAL_FILE_PATH = 'resource/OSTurbo/UBTurbo_RMRS_API'  # 代码仓中rmrsapi文件路径
OS_REMOTE_TEST_PATH = '/home/autotest/os'  # 执行环境父目录
TURBO_TEST_REMOTE_FILE_PATH = f'{OS_REMOTE_TEST_PATH}/UBTurbo_API'  # turbo-api目录
RMRS_TEST_REMOTE_FILE_PATH = f'{OS_REMOTE_TEST_PATH}/UBTurbo_RMRS_API'  # rms-api目录


def detect_osturbo(node):
    """
    检测osturbo-daemon是否运行
    """
    osturbo_on = False
    basic.logger.info('检测ubturbo状态')
    res = basic.run(node, f'systemctl status {SERVICE_NAME_OSTURBO_DAEMON} --no-pager')
    output = res.stdout + res.stderr
    if 'service could not be found.' in output:
        basic.logger.error(f'不存在该服务: {SERVICE_NAME_OSTURBO_DAEMON}')
    elif 'active (running)' in output:
        basic.logger.info('osturbo已启动')
        osturbo_on = True
    else:
        basic.logger.error('osturbo未启动')
    return osturbo_on


def check_rpm_installed(node, dep_rpm_list):
    """
    检查依赖组件是否安装
    """
    dep_ready = True
    for dep_name in dep_rpm_list:
        res = basic.run(node, f"rpm -qa | grep {dep_name}")
        output = res.stdout + res.stderr
        if dep_name in output:
            basic.logger.info(f"{dep_name}已安装")
        else:
            basic.logger.error(f"{dep_name}未安装")
            dep_ready = False
    return dep_ready


def install_rpm(node, dep_rpm_list):
    """
    安装依赖组件
    """
    for dep_name in dep_rpm_list:
        res = basic.run(node, f"yum install -y {dep_name}")
        output = res.stdout + res.stderr
        if "Complete!" in output:
            basic.logger.info(f"{dep_name}已安装")
        else:
            basic.logger.error(f"{dep_name}安装失败")


def install_osturbo(node):
    """
    安装osturbo
    """
    if not system.is_path_exist(node, MIRROR_PATH, True):
        basic.logger.error(f"镜像未挂载，无法安装osturbo")
        return False
    basic.run(node, f"rpm -ivh {MIRROR_PATH}{SERVICE_NAME_OSTURBO_DAEMON}-1.0.0-1.aarch64.rpm --force")
    return check_rpm_installed(node, SERVICE_NAME_OSTURBO_DAEMON)


def get_osturbo_log_level(node):
    """
    获取osturbo日志等级
    """
    if not system.is_path_exist(node, TURBO_CONF_PATH):
        basic.logger.error(f"osturbo配置文件不存在")
        return "INFO"
    res = basic.run(node, f"cat {TURBO_CONF_PATH}").stdout.strip("\r\n")
    match = re.search(r'log\.level=([A-Za-z]+)', res)
    if match:
        basic.logger.info(f"日志等级为{match.group(1)}")
        return match.group(1)
    else:
        basic.logger.error(f"未设置日志等级，默认使用INFO")
        return "INFO"


def check_osturbo_log_level(node, log_level):
    """
    检查osturbo日志等级是否一致
    """
    if not system.is_path_exist(node, TURBO_LOG_PATH):
        basic.logger.error(f"osturbo日志文件不存在")
        return False
    res = basic.run(node, f"cat {TURBO_LOG_PATH}").stdout.strip("\r\n")
    if f"[{log_level}]" in res:
        basic.logger.info(f"日志等级一致")
        return True
    else:
        return False


def reset_osturbo(node):
    """
    重启turbo服务并删除配置文件
    """
    status = restart_turbo(node, remove_config=True)
    if 'active' not in status:
        raise Exception(f"{SERVICE_NAME_OSTURBO_DAEMON}启动失败")


def restart_turbo(node, remove_config=False):
    """
    重启ubturbo服务, 并记录停止前的时刻, 根据入参决定是否清理对应配置文件
    :param node:
    :param remove_config: True删除配置文件后启动, False只重启
    :return:
    """
    service_turbo = systemctl.Service(node, SERVICE_NAME_OSTURBO_DAEMON)
    start_time = system.get_time(node, date_format='+\"[%Y-%m-%d %H:%M:%S\"')
    basic.run(node, f'touch {TURBO_START_TIME}')
    basic.run(node, f'echo {start_time} > {TURBO_START_TIME}')
    try:
        service_turbo.stop()
    except Exception as e:
        basic.logger.warn(e)
    if remove_config:
        system.rm(node, '/dev/shm/smap_config')
        system.rm(node, f'/dev/shm/{SERVICE_NAME_OSTURBO_DAEMON}_page_type.dat')
    time.sleep(5)  # 5秒后再启动, 避免与systemctl自身达到重试次数后拦截请求
    try:
        service_turbo.start()
    except Exception as e:
        basic.logger.warn(e)
    return service_turbo.status()


def init_turbo_api_test_env(node):
    """
    turbo-api测试环境初始化
    """
    basic.logger.tcStep("turbo-api初始化-步骤1、上传turbo-api测试依赖文件至测试环境")
    file_path = os.path.join(file_transport.THIS_PROJECT_PATH, TURBO_TEST_LOCAL_FILE_PATH)
    file_transport.send2remote(node, file_path, OS_REMOTE_TEST_PATH)

    basic.logger.tcStep("turbo-api初始化-步骤2、安装依赖的libboundscheck包")
    system.yum_install(node, 'libboundscheck')

    basic.logger.tcStep(f"turbo-api初始化-步骤3、配置{TURBO_TEST_PLUGIN_NAME}测试插件准入")
    basic.logger.info("准备测试插件so")
    system.cp(node, f"{TURBO_TEST_REMOTE_FILE_PATH}/{TURBO_TEST_SO_NAME}.so", TURBO_LIB_PATH)
    basic.run(node, f'chmod 777 {TURBO_TEST_SO_PATH}')
    basic.logger.info("准备测试插件配置文件")
    system.cp(node, f'{TURBO_TEST_REMOTE_FILE_PATH}/{TURBO_TEST_CONF_NAME}.conf', TURBO_TEST_CONF_PATH)
    system.update_conf_file(node, TURBO_PLUGIN_CONF_PATH, TURBO_TEST_PLUGIN_NAME, 776)

    basic.logger.tcStep(f"turbo-api初始化-步骤4、重启{SERVICE_NAME_OSTURBO_DAEMON}实现测试插件加载，并检查是否有对应关键日志")
    system.update_conf_file(node, TURBO_MAIN_CONF_PATH, 'log.level', 'DEBUG')  # turbo日志级别改为DEBUG, 有对应测试点
    start_time = system.get_time(node, date_format='+\"[%Y-%m-%d %H:%M:%S\"')
    status = restart_turbo(node)
    if 'active' not in status:
        raise Exception(f"{SERVICE_NAME_OSTURBO_DAEMON}启动失败")
    basic.logger.info("检查插件是否成功插入")

    def turbo_start():
        osturbo_log = system.find_message_in_log(node,
                                                 start_time=start_time,
                                                 target_log_path=TURBO_MAIN_LOG_PATH,
                                                 message=fr'Plugin \"{TURBO_TEST_PLUGIN_NAME}\" loaded successfully')
        if osturbo_log:
            return False
        return True

    res_time = basic.wait_until(condition_func=turbo_start, check_sep=5, timeout=20)
    if not res_time:
        raise Exception("插件加载失败")

    basic.logger.tcStep("turbo-api初始化-步骤5、执行call_ipc_testfunc程序(基础用例)，记录打印日志")
    basic.run(node,
              f'g++ -l{TURBO_MAIN_SO_NAME} {TURBO_TEST_REMOTE_FILE_PATH}/call_ipc_testfunc.cpp '
              f'-o {TURBO_TEST_REMOTE_FILE_PATH}/call_ipc_testfunc',
              timeout=120)
    cmd = f"""stdbuf -oL {TURBO_TEST_REMOTE_FILE_PATH}/call_ipc_testfunc | \\
    awk "{{
        if (\\$0 ~ /^调用服务:/) {{
            serv=\\$0;
            getline ret;
            print strftime(\\"[%Y-%m-%d %H:%M:%S]\\"), serv \\" \\" ret
        }}
    }}" > {TURBO_TEST_BASECASE_LOG_PATH} 2>&1"""
    basic.run(node, cmd)


def init_rmrs_api_test_env(node):
    """
    rmrs插件-api测试环境初始化
    """
    basic.logger.tcStep("rmrs-api初始化-步骤1、上传rmrs测试脚本")
    file_path = os.path.join(file_transport.THIS_PROJECT_PATH, RMRS_TEST_LOCAL_FILE_PATH)
    file_transport.send2remote(node, file_path, OS_REMOTE_TEST_PATH)

    basic.logger.tcStep("rmrs-api初始化-步骤2、确保ucache的ko插入,rmrs插件配置打开ucache开关并且在osturbo配置文件中配置准入,开启DEBUG级别日志")
    system.insmod(node, 'ucache', modprobe=True)
    system.update_conf_file(node, RMRS_PLUGIN_CONF_PATH, 'rmrs.ucache.enable', 'true')
    system.update_conf_file(node, TURBO_PLUGIN_CONF_PATH, 'rmrs', '777')
    system.update_conf_file(node, TURBO_MAIN_CONF_PATH, 'log.level', 'DEBUG')
    status = restart_turbo(node)
    if 'active' not in status:
        raise Exception(f"{SERVICE_NAME_OSTURBO_DAEMON}启动失败")

    basic.logger.tcStep("rmrs-api初始化-步骤3、拉起containerd服务,确保容器能力可用")
    basic.run(node, 'systemctl restart containerd')


def bakup_ubturbo_confs(node, turbo_conf_list, mode: Literal['mv', 'cp'] = 'mv'):
    """
    备份{turbo_conf_list}列表中的文件，当mode选择cp时，默认复制属主和文件权限
    :param turbo_conf_list:ubturbo的配置文件名列表
    :param mode:可选项，默认强制剪切
    """
    basic.run(node, "ll " + OS_TURBO_CONF_PATH, timeout=20)
    for conf_file in turbo_conf_list:
        ret = basic.run(node, f"test -e {OS_TURBO_CONF_PATH + conf_file}.mp.bak && echo 1 || echo 0 ",
                        timeout=120).stdout
        if not int(ret):
            # 未备份
            basic.logger.info(f"备份{conf_file}中")
            basic.run(node, f"{mode} {OS_TURBO_CONF_PATH + conf_file} {OS_TURBO_CONF_PATH + conf_file}.mp.bak", timeout=120)
            if mode == 'cp':
                system.set_chown_and_permission(node, file_path=OS_TURBO_CONF_PATH + conf_file, dest_file_path=f"{OS_TURBO_CONF_PATH + conf_file}.mp.bak")
    basic.run(node, "ll " + OS_TURBO_CONF_PATH, timeout=20)


def upload_turbo_confs(node, local_path, remote_tmp_path, turbo_conf_list, set_conf_chown='ubturbo:ubturbo', permission=600):
    """
    从本地上传文件到远程临时目录后，再复制到服务的对应配置文件目录下的，并设置属主与文件权限
    :param local_path:待传输目录，该目录将作为压缩包顶层目录（目录末尾不要放路径分隔符）
    :param remote_tmp_path:传输目标目录父路径 确保是目录（目录末尾不要放路径分隔符）
    :param turbo_conf_list:待传输的文件名列表
    :param set_conf_chown:文件的属主
    :param permission:文件的权限
    """
    for conf_file in turbo_conf_list:

        local_file_path = f"{local_path}/{conf_file}"
        remote_file_tmp_path = f"{remote_tmp_path}/{conf_file}"
        work_file_path = f"{OS_TURBO_CONF_PATH + conf_file}"

        file_transport.send2remote(node, local_file_path, remote_tmp_path)
        system.rm(node, work_file_path)
        basic.run(node, f"cp {remote_file_tmp_path} {work_file_path}", timeout=120)
        basic.run(node, f"chown {set_conf_chown} {work_file_path}")
        basic.run(node, f"chmod {permission} {work_file_path}")
    basic.run(node, f"ll {OS_TURBO_CONF_PATH}", timeout=20)


def restore_turbo_confs(node, turbo_conf_list):
    """
    使用强制覆盖的方式恢复ubturbo相关conf文件，与lib.api.os_turbo.py中的bakup_ubturbo_confs一起使用
    :param turbo_conf_list:ubturbo的配置文件名列表
    """
    for conf_file in turbo_conf_list:
        basic.run(node, f"mv -f {OS_TURBO_CONF_PATH + conf_file}.mp.bak {OS_TURBO_CONF_PATH + conf_file}", timeout=120)
    basic.run(node, f"ll {OS_TURBO_CONF_PATH}", timeout=20)
