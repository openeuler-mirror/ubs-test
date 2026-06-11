#! /bin/python3
# -*- coding: utf-8 -*-
# 版权所有 (c) 华为技术有限公司 2012-2025

from typing import Union, Dict, Set, List
from threading import Thread
from libs.ubturbo.common import string_utils
from libs.ubturbo.common import basic
from libs.ubturbo.common import file_transport
from libs.ubturbo.common import env
import libs.ubturbo.api.ssh as ssh
import libs.ubturbo.api.system as system
import libs.ubturbo.api.virtualization as virtualization
import libs.ubturbo.api.libvirt as lv_api


DEFAULT_PATH_TOP = '/home/vm'  # 默认顶层数据目录
DEFAULT_PATH_XML = f'{DEFAULT_PATH_TOP}/xml'  # 默认虚拟机配置存放目录
DEFAULT_PATH_IMG = f'{DEFAULT_PATH_TOP}/img'  # 默认虚拟机镜像存放目录

DEFAULT_FILENAME_XML = 'memlink_16g.xml'  # 配置文件模板
DEFAULT_FILENAME_IMG = 'openEuler-22.03-LTS-SP1-aarch64.qcow2'  # 镜像模板

DEFAULT_TMP_VMFILES_DIR = '/home/temporary_vms'

DEFAULT_VM_USER = 'root'
DEFAULT_VM_PASSWORD = 'openEuler12#$'


def generate_memlink_xml(
        node,
        file_path=f'{DEFAULT_PATH_XML}/{DEFAULT_FILENAME_XML}',
        fp_local=f'{file_transport.THIS_PROJECT_PATH}/resource/Memlink/template_memlink_16g.xml',
        force_overwrite: bool = False,
        **kwargs
):
    """
    生成 memlink_16g.xml 文件，内容为虚拟机配置，支持动态生成字段。
    :param node:
    :param file_path: 待生成xml路径
    :param fp_local: 代码仓xml路径
    :param force_overwrite: 强制覆盖，默认否
    :param kwargs: xml文件参数
    :return:
    """
    # 存在对应文件则直接返回
    if system.is_path_exist(node, file_path) and not force_overwrite:
        return

    # 定义 XML 内容模板，注意这里使用 `{}` 作为占位符来支持动态替换
    content = open(fp_local).read()
    # 默认参数，可通过传入具名参数更改
    values = {
        'memory': 16,
        'page_size': 2,
        'page_unit': 'MiB',
        'allocation_mode': 'hugepage-ondemand',
        'memballoon_model': 'virtio',
    }
    values.update(kwargs)
    # 修改xml文件
    xml_content = content.format(**values)

    # 将文本输出到文件中
    folder = '/'.join(file_path.split('/')[:-1])
    system.mkdir(node, folder)  # 确保目录存在
    file_transport.dump_text(node, xml_content, file_path)


def check_and_download_qcow2(
        node,
        directory: str = DEFAULT_PATH_IMG,
        filename: str = DEFAULT_FILENAME_IMG,
        src_path: str = 'images/qcow2/openEuler-22.03-LTS-SP1-aarch64_memlink.qcow2',
        enforce_download: bool = False,
):
    """
    检查并下载虚拟机默认镜像模板
    :param node:
    :param directory: 目标目录
    :param filename: 目标文件名
    :param src_path: 源文件下载路径 具体规则请查看download_file函数注释
    :param enforce_download: 不检查，强制下载
    :return:
    """
    filepath = f"{directory}/{filename}"  # 镜像路径
    if not enforce_download:
        if system.is_path_exist(node, filepath):
            basic.logger.info(f'{filename} 文件已存在，跳过下载')
            return
        else:
            basic.logger.info(f"{filename} 文件不存在，准备下载...")
    else:
        basic.logger.info(f'删除原镜像文件: {filepath}')
        system.rm(node, filepath)

    system.mkdir(node, directory)
    file_transport.download_file(
        node,
        src_path,
        filepath
    )
    res = basic.run(node, f'md5sum {filepath}', timeout=6 * 60)  # 某些qcow2可能很大，加长超时时间
    basic.logger.info(f'镜像文件md5值：{res.stdout}')


class VirtualMachine:
    """
    虚拟机管理
    """
    def __init__(
            self,
            node,
            fn='vm1.xml',
            vm_user=DEFAULT_VM_USER,
            vm_password=DEFAULT_VM_PASSWORD,
            init_create=True,
            init_login=True
    ):
        """
        node: 当前机器node对象
        fn: 虚拟机xml配置文件路径（设为DEFAULT_PATH_XML目录下的相对路径也可以搜索到）
        vm_password: 虚拟机密码 第一次登录时会配置公钥实现免密登录 因此仅需第一次使用时提供
        vm_user: 虚拟机用户名
        init_create: 是否要在初始化对象时创建虚拟机；方便更改xml文件
        init_login: 是否要在创建时配置免密登录，如果不，将节省大量时间
        """
        self.fn_xml = fn
        self.node = node
        self.vm_name = None
        self.vm_ip = None
        self.vm_user = vm_user
        self.vm_password = vm_password
        self.vm_ip = None
        self.env_type = env.get_env_type(node)

        # 当无法找到路径时，尝试在DEFAULT_PATH_XML中查找
        if not system.is_path_exist(self.node, self.fn_xml):
            self.fn_xml = f'{DEFAULT_PATH_XML}/{self.fn_xml}'

        if init_create:
            self.create()

            if init_login:
                self.init_login()

    def create(self):
        timeout = {
            env.UB_simulation: 1000,
        }.get(self.env_type, 60)
        self.vm_name = lv_api.vm_create(self.node, self.fn_xml, timeout=timeout)

    def init_login(self) -> None:
        # 初始化登录，生成公钥、拷贝公钥至虚拟机，实现免密登录
        pub_key = ssh.generate_rsa(self.node)
        # 登录虚拟机
        self.vm_ip = lv_api.get_vm_ip(
            self.node,
            self.vm_name,
            timeout={  # 整体超时时间
                env.UB_simulation: 30 * 60,
            }.get(self.env_type, 60),
            sep={  # 检测间隔
                env.UB_simulation: 30,
            }.get(self.env_type, 10),
            cmd_timeout={  # 命令超时时间
                env.UB_simulation: 60,
            }.get(self.env_type, 30),
        )  # 获取ip
        login_status = ssh.init_login(
            self.node,
            self.vm_ip,
            self.vm_user,
            self.vm_password,
            login_func=lambda node, usr, ip: ssh.ssh_login(
                node,
                usr,
                ip,
                timeout={
                    env.UB_simulation: 60,
                }.get(self.env_type, 10),
            ),
            timeout={
                    env.UB_simulation: 30 * 60,
                }.get(self.env_type, 3 * 60),
        )

        if login_status == ssh.AUTO_LOGIN_NOT_READY:
            ssh.set_ps1(self.node)
            ssh.add_public_key(self.node, pub_key)

        ssh.ssh_exit(self.node)

    def login(self, timeout=3) -> None:
        basic.logger.info(f'登录虚拟机: {self.vm_name}')
        ssh.ssh_login(self.node, self.vm_user, self.vm_ip, timeout=timeout)

    def logout(self) -> int:
        basic.logger.info(f'登出虚拟机: {self.vm_name}')
        # 检验当前机器是否主机，防止虚机创建失败后退出主机
        if not system.is_path_exist(self.node, self.fn_xml):  # 不存在该文件，当前为虚拟机
            ret = ssh.ssh_exit(self.node).rc
            return ret
        else:
            basic.logger.info('当前为主机，不执行退出')
            return -1

    def execute_without_login(
            self,
            cmd: str,
            **kwargs
    ) -> basic.Result:  # 在主机端让虚拟机执行一次命令（省去登录、登出过程，速度更快）
        if 'timeout' not in kwargs:
            kwargs['timeout'] = {
                env.UB_simulation: 1000,
            }.get(self.env_type, 30)
        result = ssh.execute(self.node, self.vm_user, self.vm_ip, cmd, **kwargs)
        return result

    def get_pid(self):
        # 通过匹配qemu进程的“guest=<vm_name>,”字段寻找pid
        return lv_api.get_pid(self.node, self.vm_name)

    def destroy(self):
        if not self.vm_name:
            basic.logger.info(f'虚拟机启动失败，无需销毁')
            return

        basic.logger.info('销毁前尝试登出，确保此时不在虚拟机内')
        self.logout()

        if self.vm_name in lv_api.get_all_vm_names(self.node):
            basic.logger.info(f'销毁虚拟机: {self.vm_name}')
            lv_api.vm_destroy(self.node, self.vm_name)
        else:
            basic.logger.info(f'虚拟机{self.vm_name}不存在，跳过销毁过程')

    def __enter__(self):
        """
        支持with语法登录登出虚拟机
        示例：
            vm = VirtualMachine()
            with vm:  # 此处登录
                basic.run(node, cmd)
                basic.run(node, cmd)
            # 此处登出
        """
        self.login()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.logout()


class TempVMInfo:
    used_names = set()

    def __init__(
            self,
            node,
            tmp_fn_xml=None,
            tmp_fn_img=None,
            template_xml=None,
            template_img=None,
            vm_name=None,
            tmp_folder=None,
            template_base_img=None,
            random_string_length=6,
    ):
        """
        存储临时虚拟机信息
        这里只计算合适的路径，并进行不生成与修改
        正常只需传入2个参数：
            1. template_xml
            2. template_img

        :param node: 节点对象
        :param tmp_fn_xml: 指定临时xml文件路径
        :param tmp_fn_img: 指定临时虚拟机镜像文件路径
        :param template_xml: xml文件临时生成所用模板
        :param template_img: 镜像文件临时生成所用模板
        :param vm_name: 指定虚拟机名称，不指定则为xml文件名
        :param tmp_folder: 指定临时目录 目录下xml、img目录分别存储对应类型文件
        :param template_base_img: 基础镜像模板路径（某些镜像需要依赖同目录下一个基础镜像才能启动）
        :param random_string_length: 临时文件名随机字符串长度
        """
        # 临时文件存放位置
        self.tmp_folder = tmp_folder or DEFAULT_TMP_VMFILES_DIR
        self.tmp_folder_xml = f'{self.tmp_folder}/xml'
        self.tmp_folder_img = f'{self.tmp_folder}/img'
        # 模板路径
        self.template_xml = template_xml or f'{DEFAULT_PATH_XML}/{DEFAULT_FILENAME_XML}'  # xml模板路径
        self.template_img = template_img or f'{DEFAULT_PATH_IMG}/{DEFAULT_FILENAME_IMG}'  # 镜像模板路径
        self.template_base_img = template_base_img or ''  # 基础镜像模板路径
        # 提取文件名
        fn_template_xml = self.template_xml.split('/')[-1]  # xml模板文件名
        fn_template_img = self.template_img.split('/')[-1]  # 镜像模板文件名
        fn_base_img = self.template_base_img.split('/')[-1]  # 基础镜像模板路径

        # 生成临时文件名
        if not tmp_fn_xml:  # 如果不指定，则生成随机xml文件名
            fn_formater_xml = string_utils.into_template_name(f'{self.tmp_folder_xml}/{fn_template_xml}')
            tmp_fn_xml = system.generate_filename_suffix_with_number(
                node,
                fn_formater_xml,
                random_string_length,
                self.__class__.used_names,
            )
        if not tmp_fn_img:  # 如果不指定，则生成随机镜像文件名
            fn_formater_img = string_utils.into_template_name(f'{self.tmp_folder_img}/{fn_template_img}')
            tmp_fn_img = system.generate_filename_suffix_with_number(
                node,
                fn_formater_img,
                random_string_length,
                self.__class__.used_names,
            )

        self.used_names.add(tmp_fn_xml)
        self.used_names.add(tmp_fn_img)

        # 临时文件路径
        self.tmp_fn_xml = tmp_fn_xml  # 临时xml路径
        self.tmp_fn_img = tmp_fn_img  # 临时镜像路径
        self.tmp_base_img = f'{self.tmp_folder_img}/{fn_base_img}'  # 临时镜像模板路径
        # 虚拟机名称
        self.vm_name = vm_name or self.tmp_fn_xml.split('/')[-1].split('.')[0]

    @classmethod
    def from_dict(cls, node, info_dict: dict) -> 'TempVMInfo':
        """
        新生成一份信息，并用字典参数替换一部分信息
        示例：
            TempVMInfo.from_dict(
                node,
                {
                    'template_xml': 'xxx/xxx.xml',  # 指定xml模板文件路径
                    'tmp_fn_img': 'xxx/xxx.img'  # 指定临时镜像文件路径(该文件此时不需存在，会新建)
                }
            )  # 指定xml、镜像模板路径
        """
        tmp_vm_info = TempVMInfo(node)
        tmp_vm_info.__dict__.update(info_dict)
        return tmp_vm_info


class TempVirtualMachine(VirtualMachine):
    """
    拷贝文件，生成临时的虚拟机
    """
    # 下方字典key值通过lib.common.env.get_node_identity(node)获取
    macs: Set[str] = set()  # 存储已有mac地址，防止重复（重复会导致无法启动虚拟机）
    uuids: Set[str] = set()  # 存储已有uuid，防止重复（重复会导致无法启动虚拟机）

    def __init__(
            self,
            node,
            *args,
            tmp_vm_info: Union[TempVMInfo, dict] = None,
            delete=True,
            **kwargs
    ):
        """
        拷贝xml、镜像文件，新建临时虚拟机
        一般仅需指定tmp_vm_info
        示例：
            temp_vm = TempVirtualMachine(
                node,
                tmp_vm_info={'template_xml': '/path/to/xxx.xml', 'template_img': '/path/to/xxx.qcow2'},
                )
        :param node: 节点对象
        :param args:
        :params tmp_vm_info: 临时虚拟机信息，不提供则随机生成
        :param delete: 销毁虚拟机后删除临时xml、镜像文件
        :param kwargs:
        """
        # 节点ID
        self.node_identity = env.get_node_identity(node)

        # 基础参数配置
        self.delete = delete  # 是否在销毁虚拟机时删除对应文件
        # 临时虚拟机参数
        if tmp_vm_info is None:  # 不传入参数，自动生成临时信息
            self.tmp_vm_info = TempVMInfo(node)
        elif type(tmp_vm_info) is dict:  # 传入字典
            self.tmp_vm_info = TempVMInfo.from_dict(node, tmp_vm_info)
        else:  # 传入对象
            self.tmp_vm_info = tmp_vm_info

        # 拷贝生成临时xml、镜像文件
        system.mkdir(node, self.tmp_vm_info.tmp_folder_xml)
        system.mkdir(node, self.tmp_vm_info.tmp_folder_img)
        system.cp(node, self.tmp_vm_info.template_xml, self.tmp_vm_info.tmp_fn_xml)
        system.cp(node, self.tmp_vm_info.template_img, self.tmp_vm_info.tmp_fn_img)
        # 复制基础镜像到镜像同目录
        if self.tmp_vm_info.template_base_img:
            system.cp(node, self.tmp_vm_info.template_base_img, self.tmp_vm_info.tmp_base_img)

        basic.logger.info(
            f'创建临时虚拟机文件：配置文件：{self.tmp_vm_info.tmp_fn_xml} 镜像文件：{self.tmp_vm_info.tmp_fn_img}'
        )

        # 修改xml文件 虚拟机名称
        basic.run(
            node,
            f"sed -i 's/<name>.*<\\/name>/<name>{self.tmp_vm_info.vm_name}<\\/name>/g' {self.tmp_vm_info.tmp_fn_xml}"
        )
        # 修改xml文件 虚拟机镜像路径
        replace_fn_img = self.tmp_vm_info.tmp_fn_img.replace('/', r'\/')  # 路径加上反斜杠，以支持sed语法
        basic.run(
            node,
            f"sed -i \"s/<source file=.*\\/>/<source file='{replace_fn_img}' \\/>/g\" {self.tmp_vm_info.tmp_fn_xml}"
        )
        # 修改xml文件 虚拟机物理地址
        self.mac = lv_api.xml_set_random_mac(node, self.tmp_vm_info.tmp_fn_xml, self.macs)
        # 修改xml文件 修改uuid（如果有）
        if not basic.run(node, f'grep \'<uuid>\' {self.tmp_vm_info.tmp_fn_xml}').rc:
            self.uuid = lv_api.xml_set_random_uuid(node, self.tmp_vm_info.tmp_fn_xml, self.uuids)

        basic.logger.info(f'macs: {self.macs}')

        super().__init__(node, *args, fn=self.tmp_vm_info.tmp_fn_xml, **kwargs)

    def destroy(self):
        super().destroy()
        self.macs.remove(self.mac)
        if 'uuid' in self.__dict__:
            self.uuids.remove(self.uuid)
        if self.delete:  # 删除虚拟机对应文件
            system.rm(self.node, self.tmp_vm_info.tmp_fn_xml)
            system.rm(self.node, self.tmp_vm_info.tmp_fn_img)
            basic.logger.info(
                f'删除虚拟机临时文件：配置文件：{self.tmp_vm_info.tmp_fn_xml} 镜像文件：{self.tmp_vm_info.tmp_fn_img}'
            )

    @classmethod
    def clear_all(cls, node):
        lv_api.delete_all_vms(node)
        basic.logger.info('删除临时目录')
        system.rm(node, DEFAULT_TMP_VMFILES_DIR)


def vm_add_pressure(vm, node, amount: int, unit: str = 'G', init_used_huge_pages: int = None):
    """
    虚拟机内存加压，确保加压完成
    :param vm: 虚拟机对象
    :param node: 节点对象
    :param amount: 加压量
    :param unit: 单位，默认G
    :param init_used_huge_pages: 初始已使用大页数
    :return:
    """
    units = {'G': 1024, 'M': 1, 'K': 1 / 1024}
    init_used_huge_pages = init_used_huge_pages or virtualization.get_huge_pages(node, return_used=True)[0]
    vm.execute_without_login(f'nohup memtester {amount}{unit} 1 1>/dev/null 2>&1 &')
    # 适配多类型环境等待时间
    timeout = {
            env.UB_simulation: 5 * 60,
        }.get(vm.env_type, 2 * 60)
    check_sep = {
            env.UB_simulation: 30,
        }.get(vm.env_type, 10)

    virtualization.wait_until_mem_stable(
        node,
        init_used_huge_pages + int(amount * units[unit] / 2),
        check_sep=check_sep,
        timeout=timeout,
        used_abs_sep=True
    )


