#! /bin/python3
# -*- coding: utf-8 -*-
# 版权所有 (c) 华为技术有限公司 2012-2025

import os
import tarfile
import tempfile
import time
import zipfile

from libs.ubturbo.common import basic, string_utils, env


# 获取本项目根目录绝对路径：THIS_PROJECT_PATH
dirname = os.path.dirname
THIS_PROJECT_PATH = __file__
for _ in range(4):
    THIS_PROJECT_PATH = dirname(THIS_PROJECT_PATH)


def send2remote(node, src: str, dst: str, format_: str = "zip", max_retry=3):
    """
    传输本地文件到远程主机，远程系统仅支持Linux
    :param node:
    :param src: 待传输目录/文件绝对路径 包含中文可能会乱码 如果是目录，该目录将作为压缩包顶层目录（目录末尾不要放路径分隔符）
    :param dst: 传输目标目录父路径 确保是目录
    :param format_: 传输格式（某些系统不支持unzip命令，增加tar.gz上传方式）
    :param max_retry: 失败重试次数
    """
    sep = '/'
    suffix = f'.{format_}'

    src_parent, src_fn = os.path.split(src)  # 分割源路径 方便构建zip文件内部结构，使其包含顶层目录

    # 生成本地压缩后文件路径
    tmp_folder = os.path.join(THIS_PROJECT_PATH, 'tmp_files')
    os.makedirs(tmp_folder, exist_ok=True)
    # 生成随机压缩包名
    fn_src_pack = ''
    while (not fn_src_pack) or os.path.isfile(fn_src_pack):
        fn_src_pack = os.path.join(tmp_folder, string_utils.generate_random_string(10) + f'{suffix}')

    fn_dst_pack = f'{dst}{sep}{src_fn}{suffix}'  # 远程主机压缩文件预存放路径
    fn_dst = f'{dst}{sep}{src_fn}'

    if format_ == "zip":
        # 创建zip压缩包
        basic.logger.info(f'压缩本地文件 {src} -> {fn_src_pack}')
        fw = zipfile.ZipFile(fn_src_pack, 'w', zipfile.ZIP_DEFLATED)
        if os.path.isdir(src):
            for root, dirs, files in os.walk(src):
                for file in files:
                    file_path = os.path.join(root, file)
                    zip_path = os.path.relpath(file_path, src_parent)
                    fw.write(file_path, zip_path)
        elif os.path.isfile(src):
            fw.write(src, os.path.basename(src))
        else:
            basic.logger.warn(f'无法传输，执行机不存在该文件/目录：{src}')
        fw.close()
    elif format_ == "tar.gz":
        # 创建tar压缩包
        basic.logger.info(f'压缩本地文件 {src} -> {fn_src_pack}')
        try:
            with tarfile.open(fn_src_pack, "w:gz") as tar:  # 使用gzip压缩
                tar.add(src, arcname=src_fn)  # 自动处理文件和目录结构
        except Exception as e:
            basic.logger.error(f'压缩失败：{e}')
            raise

    basic.logger.info('传输压缩文件')
    import libs.ubturbo.api.system as system  # 延迟导入，避免循环依赖
    system.mkdir(node, dst)

    node.putFile(fn_src_pack, fn_dst_pack)

    basic.logger.info(f'删除{fn_dst}(如果有)，解压文件')
    system.rm(node, fn_dst)

    return_code_unzip = 1  # 记录解压命令是否成功
    if format_ == "zip":
        return_code_unzip = basic.run(node, f'unzip {fn_dst_pack} -d {dst}', timeout=30).rc
    elif format_ == "tar.gz":
        return_code_unzip = basic.run(node, f'tar xzf {fn_dst_pack} -C {dst}', timeout=30).rc  # 使用tar解压并指定目录

    basic.logger.info('删除压缩文件')
    basic.run(node, f'rm -f {fn_dst_pack}')
    os.remove(fn_src_pack)

    if max_retry and return_code_unzip:  # 解压失败，说明上传过程可能出现问题，重试
        send2remote(node=node, src=src, dst=dst, format_=format_, max_retry=max_retry-1)


def dump_text(node, text: str, fn: str, append: bool = False) -> None:
    """将文本写入文件中"""
    # 预处理文本中的单引号   ' -> '\''
    text = text.replace("'", "'\\''")
    # 默认使用终端提示符
    wait_str = f"]#|{node.username}{string_utils.DEFAULT_WAIT_STRING}"
    while wait_str in text:  # 如果文本内包含终端提示符，则切换为随机字符串并设置超时来规避
        wait_str = string_utils.generate_random_string(20)

    sign = '>>' if append else '>'

    basic.run(node, f"echo '{text}' {sign} {fn}", waitstr=wait_str)


def download_file(node, src: str, dst: str, ip_: str = None, timeout: int = 5 * 60):
    """
    下载文件
    非特殊情况，ip无需在代码中指定，会自动从CIDA参数或测试床配置中获取（需手动配置，见函数get_file_server_ip）
    如果有新文件要添加:
        1. 上传至对应服务器的 /var/www/html/ostest 目录
        2. 使用chmod 777 命令修改权限（否则下载下来的文件为403的html）

    示例：
        1. 首先上传了压缩文件至 文件服务器该路径：/var/www/html/ostest/test_1/test.tar.gz
        2. 通过接口下载文件：file_transport.download_file(self.node, 'ostest/test_1/test.tar.gz', '/home/test2.tar.gz')
            文件会被下载为/home/test_2.tar.gz

    :param node:
    :param src: 文件服务器/var/www/html/下的路径，不包含开头的/var/www/html/
    :param dst: 下载文件存放位置（路径包含文件名）
    :param ip_: 服务器ip
    :param timeout: 超时时长
    """
    ip_ = ip_ or env.get_file_server_ip(node)
    res = basic.run(node, f"curl -o {dst} http://{ip_}/{src}", timeout=timeout)
    if res.rc:
        raise Exception(f"下载文件失败: {res.stderr}")

    basic.logger.info(f"{src} 文件已成功下载到: {dst}")


