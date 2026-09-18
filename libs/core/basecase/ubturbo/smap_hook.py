import time
from asyncio import timeout
from typing import List

from libs import TestCase
from libs.core.basecase.ubturbo.smap_host import SmapHost


class SmapHook(TestCase):

    def _init_from_fixture(self, nodes, custom_params):
        """Fixture 注入入口。框架传入 SSH 节点列表和 test-params 字典。
        在这里初始化 self.nodes、self.install_path 等实例属性"""

        self.nodes = nodes
        self.page_type = custom_params.get("page_type", "2m")
        self.resource_path = custom_params.get("package_path", "/home/ubturbo-test/smap")
        self.hosts: List[SmapHost] = [SmapHost(self.resource_path, node, i) for i, node in
                                      enumerate(self.nodes, start=0)]

    def beforePreTestSet(self, **kwargs):
        self.hosts[0].upload_resource(self.resource_path)
        result = self.hosts[0].check_file_exists(f"{self.resource_path}/change_mod_linqu.sh")
        if result:
            for nid in self.hosts[1].get_local_numa():
                self.hosts[1].assign_huge_pages(nid, 2048, 8500)
            self.hosts[0].run(f"bash -x {self.resource_path}/change_mod_linqu.sh {self.page_type}", timeout=1800)
        time.sleep(5)  # 加上等待时间 防止自动化过快导致进程还未启动

    def afterPostTestSet(self, **kwargs):
        self.hosts[0].run("pkill -9 smap")
        self.hosts[0].run(
            "ubsectl display memory -t borrow_detail | grep -oP smap-test-[^\ ]+ | xargs -i sudo -u ubse ubsectl delete memory -t numa -n {}", timeout=1800)