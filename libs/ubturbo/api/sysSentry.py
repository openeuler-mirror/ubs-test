#! /bin/python3
# -*- coding: utf-8 -*-
# 版权所有 (c) 华为技术有限公司 2012-2025

from libs.ubturbo.common import basic
import libs.ubturbo.api.system as system
SENTRY_SERVICE_PATH = "/usr/lib/systemd/system/sysSentry.service"


def deploy_sentry(self):
    """
    部署sysSentry
    """
    for node in self.nodes:
        if system.is_path_exist(node, SENTRY_SERVICE_PATH):
            continue
        system.yum_install(node, 'sysSentry sentry_msg_monitor')


def install_sySentry(node, reboot_timeout_ms=900000, panic_timeout_ms=900000, kernel_reboot_timeout_ms=900000):
    """
    安装sysSentry并设置劫持故障事件的时长（ms）
    :param reboot_timeout_ms:BMC下电事件
    :param panic_timeout_ms:panic事件
    :param kernel_reboot_timeout_ms:reboot事件
    """
    basic.run(node, "systemctl stop sysSentry")
    basic.run(node, "systemctl stop xalarmd")
    basic.run(node, "rmmod sentry_reporter")
    basic.run(node, "yum install -y sysSentry sentry_msg_monitor")
    basic.run(node, f"modprobe sentry_reporter reboot_timeout_ms={reboot_timeout_ms} oom_timeout_ms=60000")
    basic.run(node, "sudo modprobe sentry_remote_reporter")
    basic.run(node, "systemctl start xalarmd")
    basic.run(node, "systemctl start sysSentry")
    basic.run(node, f'sentryctl set sentry_remote_reporter --panic_timeout_ms={panic_timeout_ms} --kernel_reboot_timeout_ms={kernel_reboot_timeout_ms}')
    basic.run(node, 'cat /proc/sentry_remote_reporter/panic_timeout')
    basic.run(node, 'cat /proc/sentry_remote_reporter/kernel_reboot_timeout')