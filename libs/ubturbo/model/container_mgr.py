import json
import time

from libs.ubturbo.api import system
from libs.ubturbo.common import basic, file_transport, string_utils

DEFAULT_PATH_TOP = '/home/container_overcommit'
DEFAULT_PATH_JSON = f'{DEFAULT_PATH_TOP}/json'

DEFAULT_POD_FILENAME_JSON = 'pod.json'
DEFAULT_CTR_FILENAME_JSON = 'container.json'

DEFAULT_TMP_CTR_FILES_DIR = '/tmp/ctrs'


class NodeContainerManager:
    def __init__(self, node):
        self.node = node
        self.runtime = CrictlRuntime(self.node)
        basic.run(self.node, 'systemctl start containerd')

    def create_pod(self, name=None, **kwargs) -> "Pod":
        pod_id, pod_json = self.runtime.create_pod(name, **kwargs)
        return Pod(self.runtime, pod_id, pod_json)

    def create_container(self, pod: "Pod", image=None, name=None, **kwargs) -> "Container":
        container_id = self.runtime.create_container(pod.id, pod.json, image, name, **kwargs)
        ctr = Container(self.runtime, container_id, pod)
        ctr.start()
        container_pid = self.runtime.query_container_pid(container_id)
        ctr.set_pid(container_pid)
        pod.containers.append(ctr)
        return ctr


class CrictlRuntime():
    def __init__(self, node):
        self.node = node
        self.tmp_folder_json = f'{DEFAULT_TMP_CTR_FILES_DIR}/json'
        self._prepare_json()

    @staticmethod
    def _generate_json(node, file_path, fp_local, force_overwrite: bool = False, **kwargs):
        if system.is_path_exist(node, file_path) and not force_overwrite:
            return
        with open(fp_local) as f:
            content = f.read()
        # 将文本输出到文件中
        folder = '/'.join(file_path.split('/')[:-1])
        system.mkdir(node, folder)
        file_transport.dump_text(node, content, file_path)

    @staticmethod
    def _build_create_cmd(pod_id, ctr_json, pod_json, image, name, params) -> str:
        cmd = f"crictl create {pod_id} {ctr_json} {pod_json}"
        if image:
            cmd += f" --image {image}"
        if name:
            cmd += f" --name {name}"
        for key, value in params.items():
            key = key.replace("_", "-")  # no_pivot -> no-pivot

            if isinstance(value, bool):
                if value:
                    cmd += f" --{key}"
            else:
                cmd += f" --{key} {value}"
        return cmd

    def create_pod(self, name, **kwargs):
        pod_json = self._prepare_pod_json()
        cmd = f"crictl runp {pod_json}"
        if name:
            cmd += f" --name {name}"
        pod_id = basic.run(self.node, cmd).stdout.strip()
        return pod_id, pod_json

    def create_container(self, pod_id, pod_json, image=None, name=None, **kwargs) -> str:
        ctr_json = self._prepare_ctr_json()
        cmd = self._build_create_cmd(pod_id, ctr_json, pod_json, image, name, kwargs)
        return basic.run(self.node, cmd).stdout.strip()

    def query_container_pid(self, container_id):
        res = basic.run(self.node, f"crictl inspect {container_id}")
        try:
            res = json.loads(res.stdout)
            return int(res["info"]["pid"])
        except json.JSONDecodeError:
            return None

    def start(self, container_id):
        return basic.run(self.node, f"crictl start {container_id}")

    def delete(self, container_id):
        return basic.run(self.node, f"crictl rm -f {container_id}")

    def _prepare_json(self):
        remote_pod_json = f'{DEFAULT_PATH_JSON}/{DEFAULT_POD_FILENAME_JSON}'
        remote_ctr_json = f'{DEFAULT_PATH_JSON}/{DEFAULT_CTR_FILENAME_JSON}'
        local_project_path = file_transport.THIS_PROJECT_PATH
        local_ctr_json = f'{local_project_path}/resource/ubsrmrs/Container_Overcommit/container_template.json'
        local_pod_json = f'{local_project_path}/resource/ubsrmrs/Container_Overcommit/pod_template.json'

        self._generate_json(self.node, remote_pod_json, local_pod_json)
        self._generate_json(self.node, remote_ctr_json, local_ctr_json)

    def _prepare_pod_json(self):
        pod_fn_formater_json = string_utils.into_template_name(f'{self.tmp_folder_json}/{DEFAULT_POD_FILENAME_JSON}')
        pod_fn_json = system.generate_filename_suffix_with_number(self.node, pod_fn_formater_json, 6)
        template_json = f'{DEFAULT_PATH_JSON}/{DEFAULT_POD_FILENAME_JSON}'
        pod_name = pod_fn_json.split('/')[-1].split('.')[0]

        # 拷贝生成临时json
        system.mkdir(self.node, self.tmp_folder_json)
        system.cp(self.node, template_json, pod_fn_json)
        basic.logger.info(f"创建临时pod文件：配置文件：{pod_fn_json}")

        # 修改json文件 pod名称和uuid
        cmd = fr'''sed -i 's/"name"[[:space:]]*:[[:space:]]*"[^\"]*"/"name": "{pod_name}"/' {pod_fn_json}'''
        basic.run(self.node, cmd)
        cmd = fr'''sed -i 's/"uid"[[:space:]]*:[[:space:]]*"[^\"]*"/"uid": "{pod_name}"/' {pod_fn_json}'''
        basic.run(self.node, cmd)
        return pod_fn_json

    def _prepare_ctr_json(self):
        ctr_fn_formater_json = string_utils.into_template_name(f'{self.tmp_folder_json}/{DEFAULT_CTR_FILENAME_JSON}')
        ctr_fn_json = system.generate_filename_suffix_with_number(self.node, ctr_fn_formater_json, 6)
        template_json = f'{DEFAULT_PATH_JSON}/{DEFAULT_CTR_FILENAME_JSON}'  # json模板
        ctr_name = ctr_fn_json.split('/')[-1].split('.')[0]  # ctr名称

        # 拷贝生成临时json
        system.mkdir(self.node, self.tmp_folder_json)
        system.cp(self.node, template_json, ctr_fn_json)
        basic.logger.info(f'创建临时ctr文件：配置文件：{ctr_fn_json}')

        # 修改json文件 ctr名称
        cmd = fr'''sed -i 's/"name"[[:space:]]*:[[:space:]]*"[^\"]*"/"name": "{ctr_name}"/' {ctr_fn_json}'''
        basic.run(self.node, cmd)
        return ctr_fn_json


class Pod:
    def __init__(self, runtime: CrictlRuntime, pod_id: str, pod_json: str):
        self.runtime = runtime
        self.id = pod_id
        self.json = pod_json
        self.containers = []

    def create_container(self, image=None, name=None, **kwargs) -> "Container":
        container = Container(self.runtime, self.runtime.create_container(self.id, self.json, image, name, **kwargs),
                              self)
        container.start()
        container_pid = self.runtime.query_container_pid(container.id)
        container.set_pid(container_pid)
        self.containers.append(container)
        return container

    def delete(self, force=True):
        cmd = f"crictl rpm {'-f ' if force else ''}{self.id}"
        return basic.run(self.runtime.node, cmd).stdout


class Container:
    def __init__(self, runtime: CrictlRuntime, container_id: str, pod: "Pod"):
        self.runtime = runtime
        self.id = container_id
        self.pid = None
        self.pod = pod

    @property
    def status(self):
        std = basic.run(self.runtime.node, f"crictl inspect {self.id}").stdout
        return json.loads(std)["status"]["state"]

    def start(self):
        self.runtime.start(self.id)

    def delete(self):
        self.runtime.delete(self.id)

    def exec(self, cmd_name, cmd_params):
        cmd = cmd_name + " " + cmd_params
        before = set(self.__get_all_pids_by_name(cmd_name))
        basic.run(self.runtime.node, f'crictl exec {self.id} sh -c "{cmd}"')
        time.sleep(2)
        after = set(self.__get_all_pids_by_name(cmd_name))
        return sorted(after - before)

    def set_pid(self, container_id):
        self.pid = container_id

    def __get_all_pids_by_name(self, cmd_name):
        "获取所有名为cmd_name的主机侧进程pid"
        res = basic.run(self.runtime.node, f"ps -e -o pid,comm |grep {cmd_name} |grep -v grep")
        lines = res.stdout.strip().split('\n')
        pids = []
        for line in lines:
            try:
                pid = line.strip().split()[0]
                pids.append(int(pid))
            except (IndexError, ValueError):
                continue
        return pids
