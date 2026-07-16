#!/usr/local/python
# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2015-2025. All rights reserved.

import time
from pathlib import Path
import pytest

from libs.modules.ubsvirt.basecase.kubernetes_basecase import KubernetesBaseCase
from libs.modules.ubsvirt.api.client import get_date_timestamp


@pytest.mark.smoke
class TestContainerMemBorrow043(KubernetesBaseCase):
    """验证不绑numa容器清除压力后内存归还成功.

    CaseNumber:
        test_container_mem_borrow_043
    RunLevel:
        Level 1
    EnvType:

    CaseName:
        验证不绑numa容器清除压力后内存归还成功
    PreCondition:
        P1.环境中存在2个及以上节点
        P2.K8s/RackManager功能正常无异常，完成容器内存借用需要的环境部署工作
        P3.使用命令将环境设置为绑定node策略
            kubectl label nodes pod所在节点名 watermark-escape-strategy=node --overwrite
        P4.创建pod的yaml文件，request为14G，limits为16G
    TestStep:
        S1.创建pod
        S2.登录pod，借用前清理缓存，使用大页占用小页内存，每个numa预留内存
            命令：echo 3 > /proc/sys/vm/drop_caches
        S3.在pod使用redis模型进行加压触发内存借用
            加压命令：./redis-server redis.conf &
            ./redis-benchmark -t set,get -n 20000000 -c 128 -r 6500000 -h 127.0.0.1 -p 6379 -d 2048 --threads 64
        S4.在master节点使用kubectl get event查询借用事件，使用numastat -vm查询借用内存，借用值为4G
        S5.使用kill命令去除加压进程
            命令：kill -15 $(pgrep -f redis-server)
        S6.在日志中查看归还借用内存成功标志
            日志目录：/var/log/pods/kube-system_kube-matrix-agent-xxxxx（随机码）/kube-matrix-agent/
            归还成功标志：return memory success, borrow param: {Node1 [{0 0}]}, return borrow ids: [f561cad06e86cdff547633f10570d64c]
    ExpectedResult:
        E1.pod创建成功，没有报错
        E2.可以成功登录，清理缓存、预留内存成功
        E3.借用4G内存
        E4.查询到一次借用事件成功
        E5.杀掉加压进程成功
        E6.日志可以查到对应记录，且node上借用内存归还成功
    Author:
        dongrenchen 00889960
    """

    def init_mem_borrow_params(self):
        """初始化内存借用测试参数"""
        self.pod_name = "test-pod-01"
        self.filepath = "/tmp/memborrow"
        self.run_node_name = "worker1"
        self.borrow_size = 4096
        self.mem_reserved = 15.5 * 1024
        base_path = Path(__file__).parent.parent.parent.parent.parent / "resource" / "ubsvirt" / "yaml" / "test_container_mem_borrow_043"
        self.yaml_base_path = base_path

    def setup_method(self):
        """测试前置设置"""
        self.init_mem_borrow_params()

        self.logStep("P1.环境中存在2个及以上节点")
        node_num = self.get_node_number()
        self.assertGreaterEqual(node_num, 2, "节点数不大于等于2")

        self.logStep("P2.K8s/RackManager功能正常无异常，完成容器内存借用需要的环境部署工作")
        pod_list = self.get_pod_list_by_name("kube-matrix-agent")
        self.assertGreaterEqual(len(pod_list), 2, "pod数不大于等于2")

        self.logStep("P3.使用命令将环境设置为绑定node策略")
        self.set_label_node()

        self.logStep("P4.创建pod的yaml文件，request为14G，limits为16G")
        self.create_dir("master", self.filepath)
        params = {
            "source_file": f"{self.yaml_base_path}/pod_config.yaml",
            "destination_file": f"{self.filepath}/pod_config.yaml"
        }
        self.upload_file("master", params)

        self.delete_pod_by_name(self.pod_name)
        self.clear_huge_pages(self.node_dict.get('worker1'))
        self.clear_drop_cache("worker1")

    def test_container_mem_borrow_043(self):
        """测试不绑numa容器清除压力后内存归还成功"""

        self.logStep("S1.创建pod")
        create_result = self.create_pod_by_name("pod_config.yaml")

        self.logStep("E1.pod创建成功，没有报错")
        self.assertTrue(create_result, "创建测试pod失败")

        pod_running = self.watch_pod_for_status("kube-system", self.pod_name)
        self.assertTrue(pod_running, "pod未达到Running状态")

        self.logStep("S2.登录pod，借用前清理缓存，使用大页占用小页内存，每个numa预留内存")
        self.clear_huge_pages(self.node_dict['worker1'])
        self.set_watermark(75, 80, 85)

        node = self.node_dict[self.run_node_name]
        self.clear_huge_pages(node)
        self.set_node_reserved_size([self.run_node_name], self.mem_reserved)

        self.logStep("E2.可以成功登录，清理缓存、预留内存成功")
        self.node_dict['worker1'].run({'command': ['numastat -cvm']})

        self.logStep("S3.在pod使用redis模型进行加压触发内存借用")
        self.start_redis_server(self.run_node_name, self.pod_name)
        self.stress_redis("node", self.pod_name)

        self.logStep("E3.借用4G内存")
        flag1 = self.check_numa_borrow_size("worker1", self.borrow_size, 600)
        self.assertTrue(flag1, "borrow mem failed")

        self.logStep("S4.在master节点使用kubectl get event查询借用事件，使用numastat -vm查询借用内存")
        res = self.master.run({'command': ['kubectl get event -A | grep "mem borrow success"'], 'waitstr': '#'}).get("stdout")
        res = res.replace("root@#>", "")

        self.logStep("E4.查询到一次借用事件成功")
        self.assertIsNotNone(res, "kubectl get borrow event failed")

        self.logStep("S5.使用kill命令去除加压进程")
        self.clear_redis_stress(self.pod_name)

        self.logStep("E5.杀掉加压进程成功")

        self.logStep("S6.在日志中查看归还借用内存成功标志")
        flag2 = self.check_numa_mem_return("worker1")

        self.logStep("E6.日志可以查到对应记录，且node上借用内存归还成功")
        self.assertTrue(flag2, "mem return failed")

    def teardown_method(self):
        """测试清理"""
        self.set_watermark(80, 85, 92)
        self.clear_huge_pages(self.node_dict.get('worker1'))
        self.delete_pod_by_name(self.pod_name)