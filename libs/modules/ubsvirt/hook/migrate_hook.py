from libs.core.base import TestCase
import libs.modules.ubsvirt.common.file_common as file_aw
import libs.modules.ubsvirt.common.service_common as service_aw


class MigrateHook(TestCase):
    plugin_vm_file_path = f'/etc/ubse/plugins/plugin_virt_agent.conf'
    plugin_vm_file_path_bak = f'{plugin_vm_file_path}.bak'

    def _init_from_fixture(self, nodes: list, custom_params: dict) -> None:
        """Initialize instance attributes from fixture-injected dependencies.

        Called by the package_hook_fixture after instantiation,
        to replace the legacy __init__ pattern.

        Args:
            nodes: List of libs.host.Linux SSH host objects from --resource-config
            custom_params: Dict from --test-params JSON
        """
        self.nodes = nodes
        self.node_filter_list = []
        for node in nodes:
            host_name = node.getHostname()
            if host_name == 'controller' and node.port != 22:
                continue
            self.node_filter_list.append(node)

    def beforePreTestSet(self, **kwargs):
        self.logger.info("备份配置文件")
        for node in self.node_filter_list:
            file_aw.copy_file(node, self.plugin_vm_file_path, self.plugin_vm_file_path_bak)
        self.logger.info("修改high.watermark,low.watermark配置")
        change_res1 = file_aw.change_file(self.node_filter_list, 'high.watermark', '70', self.plugin_vm_file_path)
        if not change_res1:
            raise ValueError("修改high.watermark失败")
        change_res1 = file_aw.change_file(self.node_filter_list, 'low.watermark', '60', self.plugin_vm_file_path)
        if not change_res1:
            raise ValueError("修改low.watermark失败")
        for node in self.node_filter_list:
            service_aw.exec_service(node, 'restart', 'ubse')
        wait_res = service_aw.wait_ubse_status(self.node_filter_list[0], self.node_filter_list, 900, 10)
        if not wait_res:
            raise ValueError("重启ubse失败")


    def afterPostTestSet(self, **kwargs):
        self.logger.info("还原配置文件")
        for node in self.node_filter_list:
            file_aw.mv_file(node, self.plugin_vm_file_path_bak, self.plugin_vm_file_path)

        for node in self.node_filter_list:
            service_aw.exec_service(node, 'restart', 'ubse')
        wait_res = service_aw.wait_ubse_status(self.node_filter_list[0], self.node_filter_list, 900, 10)
        if not wait_res:
            raise ValueError("重启ubse失败")