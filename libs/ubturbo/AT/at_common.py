# xx特性 自动化公共方法
import time

# 公共方法日志打印定义
from libs.utils.logger_compat import Log
import os
import re

logger = Log.getLogger("AT_Common")


def welcome(node, name):
    """
    函数说明: hello world
    参数说明:
        name (str): 打招呼对象名称
    函数返回: True/False
    """
    logger.info("这是一条info级别的信息")
    res = node.run({'command': [f"hostname -f"], 'waitstr': '#'})
    server = res.get("stdout")
    return f"Welcome, {name}, your testbed is {server}"

def pre_config_lingquos_yum(node):
    config_flag_file = 'config_lingquos_yum_flag'
    path_file = "/root/{}".format(config_flag_file)
    res = node.run({'command': ["ls -d  {}".format(path_file)], 'waitstr': '#'})
    if res['stdout'] is not None and "No such file or directory" not in res['stdout']:
        logger.info("config_lingquos_yum_flag already ")
        res = node.run({'command': [f"mount /root/LingquOS-V1.0-aarch64-dvd.iso /root/mountiso/ "], 'waitstr': '#'})
        return
    # 配置yum.conf
    res = node.run({'command': [f"echo sslverify=false >> /etc/yum.conf"], 'waitstr': '#'})
    # # 配置ISO本地yum源
    # file_name = 'iso.repo'
    # res = node.run({'command': ["\cp  /home/mirror/LingquOS-V1.0-aarch64-dvd.iso  /root/LingquOS-V1.0-aarch64-dvd.iso"], 'waitstr': '#'})
    # res = node.run({'command': ["mkdir mountiso"], 'waitstr': '#'})
    # res = node.run({'command': [f"mount /root/LingquOS-V1.0-aarch64-dvd.iso /root/mountiso/ "], 'waitstr': '#'})
    # yum_file = ['[isorepo]',
    #             'name=isorepo',
    #             'baseurl=file:///root/mountiso',
    #             'enabled=1',
    #             'gpgcheck=0']
    # res = node.run(
    #     {'command': ["mv -f /etc/yum.repos.d/{0} /etc/yum.repos.d/{0}.bak".format(file_name)], 'waitstr': '#'})
    # for i in yum_file:
    #     res = node.run({'command': ["echo {} >> /etc/yum.repos.d/{}".format(i, file_name)], 'waitstr': '#'})
    # res = node.run({'command': ["cat /etc/yum.repos.d/{}".format(file_name)], 'waitstr': '#'})
    # # 配置openeuler在线yum源
    # '''
    # yum_file = ['[osrepo]',
    #             'name=osrepo',
    #             'baseurl=https://mirrors.tools.huawei.com/openeuler/openEuler-22.03-LTS-SP3/OS/aarch64/',
    #             'enabled=1',
    #             'gpgcheck=0',
    #             'gpgkey=https://mirrors.tools.huawei.com/openeuler/openEuler-22.03-LTS-SP3/OS/aarch64/RPM-GPG-KEY-openEuler']
    # res = node.run(
    #     {'command': [f"mv -f /etc/yum.repos.d/op_mirror_huawei.repo /etc/yum.repos.d/op_mirror_huawei.repo.bak"],
    #      'waitstr': '#'})
    # for i in yum_file:
    #     res = node.run({'command': ["echo {} > /etc/yum.repos.d/op_mirror_huawei.repo".format(i)], 'waitstr': '#'})
    # res = node.run({'command': [f"cat /etc/yum.repos.d/op_mirror_huawei.repo"], 'waitstr': '#'})
    # '''
    # # yum源生效
    # res = node.run({'command': ["source ~/.install-openrc"], 'waitstr': '#'})
    # res = node.run({'command': [f"yum clean all"], 'waitstr': '#'})
    # res = node.run({'command': [f"yum makecache > log.log 2>&1"], 'waitstr': '#'})
    # # 配置devel_tools的yum源
    # res = node.run({'command': ["yum install createrepo -y"], 'waitstr': '#'})
    # file_name = 'devel_tools.repo'
    # res = node.run({'command': ["\cp  /home/mirror/devel_tools.tar.gz  /root/devel_tools.tar.gz"], 'waitstr': '#'})
    # res = node.run({'command': ["tar zxvf devel_tools.tar.gz"], 'waitstr': '#'})
    # res = node.run({'command': ["createrepo devel_tools"], 'waitstr': '#'})
    # yum_file = ['[devel_tools_repo]',
    #             'name=devel_tools_repo',
    #             'baseurl=file:///root/devel_tools',
    #             'enabled=1',
    #             'gpgcheck=0']
    # res = node.run(
    #     {'command': ["mv -f /etc/yum.repos.d/{0} /etc/yum.repos.d/{0}.bak".format(file_name)], 'waitstr': '#'})
    # for i in yum_file:
    #     res = node.run({'command': ["echo {} >> /etc/yum.repos.d/{}".format(i, file_name)], 'waitstr': '#'})
    # res = node.run({'command': ["cat /etc/yum.repos.d/{}".format(file_name)], 'waitstr': '#'})
    # yum源生效
    res = node.run({'command': [f"yum clean all"], 'waitstr': '#'})
    res = node.run({'command': [f"yum makecache > log.log 2>&1"], 'waitstr': '#'})
    # 安装基本包
    res = node.run({'command': [f"yum install httpd -y"], 'waitstr': '#'})
    res = node.run({'command': [f"systemctl start httpd"], 'waitstr': '#'})
    res = node.run({'command': [f"systemctl enable httpd"], 'waitstr': '#'})
    res = node.run({'command': [f"systemctl stop firewalld"], 'waitstr': '#'})
    res = node.run({'command': [f"systemctl disable firewalld"], 'waitstr': '#'})
    res = node.run({'command': ["touch {}".format(path_file)], 'waitstr': '#'})

def complile_kernel_test(node, testsuite_dict, output_path='/opt', compile_env_path='/root'):
    """
    函数说明: 编译内核测试代码
    参数说明:
        node (str): 执行节点
        testsuite_list (list): 测试套名称
        output_path (str): 编译后存放路径
    函数返回: 编译后测试套路径
    """
    testsuite_list = list(testsuite_dict.keys())
    testsuite_file_list = list(testsuite_dict.values())[0]
    complile_package_exit_flag_file = 'complile_package_exit_flag'
    remote_dir = "/root"
    result_list = []
    for testsuite in testsuite_list:
        path = "{}/Euler_compile_env/{}/{}".format(compile_env_path, output_path, testsuite)
        res = node.run({'command': ["ls -d  {}".format(path)], 'waitstr': '#'})
        if res['stdout'] is not None and "No such file or directory" not in res['stdout']:
            logger.info("testsuite  already complile")
            local_dir = os.path.join(os.path.abspath(__file__).split('lib')[0], 'components', 'kernel-test', 'runkerneltest', 'tests')
            for testsuite_file in testsuite_file_list:
                source_file = os.path.join(local_dir, testsuite_file)
                #destination_file = os.path.join(remote_dir, 'Euler_compile_env', output_path.split('/'), testsuite, 'tests', testsuite_file)
                destination_file = "{}/Euler_compile_env/{}/{}/tests/{}".format(remote_dir, output_path, testsuite,testsuite_file)
                node.putFile({"source_file": source_file, "destination_file": destination_file})
            result_list.append(path)
        else:
            #compile_env_package_url = "https://cmc-nkg-artifactory.cmc.tools.huawei.com/artifactory/cmc-software-release/EulerX-A/EulerX-A2.0.0ARM-5.10/2024.08.22.061009/Software/aarch64/CompileTools/Euler_compile_env.tar.gz"
            res = node.run({'command': ["cd {}".format(compile_env_path)], 'waitstr': '#'})
            res = node.run({'command': ["ls -d  {}".format(complile_package_exit_flag_file)], 'waitstr': '#'})
            if res['stdout'] is not None and "No such file or directory" not in res['stdout']:
                logger.info("compile package already exist")
                local_dir = os.path.join(os.path.abspath(__file__).split('lib')[0], 'components', 'kernel-test', 'runkerneltest', 'tests')
                for testsuite_file in testsuite_file_list:
                    source_file = os.path.join(local_dir, testsuite_file)
                    #destination_file = os.path.join(remote_dir, 'Euler_compile_env', remote_dir, 'kernel-test', 'runkerneltest', 'tests', testsuite_file)
                    destination_file = "{}/Euler_compile_env/{}/kernel-test/runkerneltest/tests/{}".format(remote_dir, remote_dir, testsuite_file)
                    node.putFile({"source_file": source_file, "destination_file": destination_file})
            else:
                tmp_file_name = 'kernel-test-tmp.tar.gz'
                local_dir = os.path.join(os.path.abspath(__file__).split('lib')[0], 'components')
                remote_dir = "/root"
                os.chdir(local_dir)
                os.system('rm -rf {}'.format(tmp_file_name))
                os.system('tar zcvf {} kernel-test/*'.format(tmp_file_name))
                node.putFile({"source_file": os.path.join(local_dir, tmp_file_name),
                                   "destination_file": "{}/{}".format(remote_dir, tmp_file_name)})
                node.run({'command': ["cd {}".format(remote_dir)]})
                node.run({'command': ["tar zxvf {}  > log.log 2>&1".format(tmp_file_name)]})
                node.run({'command': ["find kernel-test/ -type f -exec dos2unix {} \; > log.log 2>&1".format(tmp_file_name)]})
                node.run({'command': ["rm -rf {}".format(tmp_file_name)]})
                #res = node.run({'command': ["wget --no-check-certificate {}".format(compile_env_package_url)], 'waitstr': '#'})
                res = node.run({'command': ["\cp  /home/mirror/Euler_compile_env.tar.gz  /root/Euler_compile_env.tar.gz"], 'waitstr': '#'})
                res = node.run({'command': [f"tar zxvf Euler_compile_env.tar.gz > log.log 2>&1 "], 'waitstr': '#'})
                #res = node.run({'command': ["\cp kernel-test.tar {}/Euler_compile_env/root/".format(compile_env_path)], 'waitstr': '#'})
                res = node.run({'command': ["\cp -rf kernel-test/  Euler_compile_env/root/"], 'waitstr': '#'})
                res = node.run({'command': ["touch {}".format(complile_package_exit_flag_file)], 'waitstr': '#'})
            res = node.run({'command': ["cd {}/Euler_compile_env/".format(compile_env_path)], 'waitstr': '#'})
            node.run({'command': [f"sh chroot.sh"], 'waitstr': '#', 'returnCode': False})
            node.run({'command': [f"PS1='\\u@'"], 'waitstr': '@', 'returnCode': False})
            node.run({'command': [f"PS1+='#>'"], 'returnCode': False})
            res = node.run({'command': [f"cd /root/"], 'waitstr': '#'})
            #res = node.run({'command': [f"tar xvf kernel-test.tar > log.log 2>&1 "], 'waitstr': '#'})
            res = node.run({'command': [f"chmod -R 777 kernel-test"], 'waitstr': '#'})
            res = node.run({'command': [f"cd kernel-test"], 'waitstr': '#'})
            res = node.run({'command': [f"cd runkerneltest/"], 'waitstr': '#'})
            if (testsuite == 'baseos_kernel_regress_t') or (testsuite == 'baseos_syscall_t'):
                res = node.run({'command': ["sh runtest compile -t {0} -a arm64 -k /usr/src/kernels/*eulerx_a2.aarch64 -o {1}/{0}".format(testsuite, output_path)], 'waitstr': '#'})
            else:
                res = node.run({'command': ["sh runtest compile -t {0} -o {1}/{0}".format(testsuite, output_path)], 'waitstr': '#'})
            result_list.append("{}/Euler_compile_env/{}/{}".format(compile_env_path, output_path, testsuite))
            if testsuite == 'memory_hugetlb_t':
                res = node.run({'command': ["chmod +x {0}/Euler_compile_env/{1}/memory_hugetlb_t/bin/memory_hugetlb_t/testcases/bin/unsetup.sh".format(compile_env_path, output_path)], 'waitstr': '#'})
            res = node.run({'command': [f"pwd"], 'waitstr': '#'})
            node.command.restoreConnectInfo()
            res = node.run({'command': [f"pwd"], 'waitstr': '#'})
        return result_list


def pre_config_for_kernel_test(node):
    config_flag_file = 'config_kernel_test_flag'
    path_file = "/root/{}".format(config_flag_file)
    res = node.run({'command': ["ls -d  {}".format(path_file)], 'waitstr': '#'})
    if res['stdout'] is not None and "No such file or directory" not in res['stdout']:
        logger.info("config  already ")
        return
    pre_config_lingquos_yum(node)
    pkg_list = ["unzip", "bc", "btrfs-progs", "ltrace", "glibc-common", "glibc-locale-source", "libaio-devel", "tpm-tools", "gdb",  "binutils", "gcc", "bc"]
    for pkg_name in pkg_list:
        res = node.run({'command': ["yum install {} -y".format(pkg_name)], 'waitstr': '#'})
    zone_list = ["ar_AE", "ar_QA", "ar_SA", "be_BY", "en_US", "ru_RU", "zh_CN", "zh_HK", "zh_TW"]
    for zone_name in zone_list:
        res = node.run({'command': ["locale -a | grep -i -q {0}.UTF8 || localedef -i ar_AE -f UTF-8 {0}.UTF8".format(zone_name)], 'waitstr': '#'})
    res = node.run({'command': ["touch {}".format(path_file)], 'waitstr': '#'})


def compile_mugen_test(node, compile_env_path='/root'):
    """
    函数说明: 编译内核测试代码
    参数说明:
        node (str): 执行节点
        testsuite_list (list): 测试套名称
        output_path (str): 编译后存放路径
    函数返回: 编译后测试套路径
    """
    compile_package_exit_flag_file = 'compile_package_exit_flag_mugen'
    remote_dir = "/root"
    path = "{}/mugen".format(compile_env_path)
    res = node.run({'command': ["ls -d  {}".format(path)], 'waitstr': '#'})
    if res['stdout'] is not None and "No such file or directory" not in res['stdout']:
        logger.info("testsuite  already complile")
    else:
        node.run({'command': ["cd {}".format(compile_env_path)], 'waitstr': '#'})
        res = node.run({'command': ["ls -d  {}".format(compile_package_exit_flag_file)], 'waitstr': '#'})
        if res['stdout'] is not None and "No such file or directory" not in res['stdout']:
            logger.info("compile package already exist")
        else:
            tmp_file_name = 'mugen-tmp.tar.gz'
            local_dir = os.path.join(os.path.abspath(__file__).split('lib')[0], 'components')
            remote_dir = "/root"
            os.chdir(local_dir)
            os.system('rm -rf {}'.format(tmp_file_name))
            # 临时注释
            os.system('tar zcvf {} mugen/*'.format(tmp_file_name))
            node.putFile({"source_file": os.path.join(local_dir, tmp_file_name),
                          "destination_file": "{}/{}".format(remote_dir, tmp_file_name)})
            node.run({'command': ["cd {}".format(remote_dir)]})
            node.run({'command': ["tar zxvf {}  > log.log 2>&1".format(tmp_file_name)]})
            node.run({'command': ["find mugen/ -type f -exec dos2unix {} \; > log.log 2>&1"]})
            node.run({'command': ["rm -rf {}".format(tmp_file_name)]})
            node.run({'command': ["cd {}".format(path)]})
        node.run({'command': ["bash dep_install.sh"], 'waitstr': '#'})
        gen_mugen_envinfo(node, path)
        node.run({'command': ["touch {}/{}".format(remote_dir, compile_package_exit_flag_file)], 'waitstr': '#'})
    return path


def gen_mugen_envinfo(node, mugen_path):
    node.run({'command': ["cd {}".format(mugen_path)]})
    node.run({'command': ["mkdir conf"]})
    env_file = "http://10.174.216.227/env_info/{}_env.json".format(node.localIP)
    res = node.run({'command': ["curl  {} -o conf/env.json".format(env_file)], 'waitstr': '#'})
    res = node.run({'command': ["bash mugen.sh -c --ip {} --password {} --user {} --port {}".format(node.localIP, node.password, node.username, node.port)], 'waitstr': '#'})


def pre_config_for_mugen(node):
    config_flag_file = 'config_mugen_test_flag'
    path_file = "/root/{}".format(config_flag_file)
    res = node.run({'command': ["cd /root"], 'waitstr': '#'})
    res = node.run({'command': ["ls -d  {}".format(path_file)], 'waitstr': '#'})
    if res['stdout'] is not None and "No such file or directory" not in res['stdout']:
        logger.info("config  already ")
        return
    pre_config_lingquos_yum(node)
    #安装yum包
    res = node.run({'command': [f"yum install wget -y"], 'waitstr': '#'})
    res = node.run({'command': [f"yum install diffutils -y"], 'waitstr': '#'})
    res = node.run(
        {'command': ["mv -f /etc/yum.repos.d/op_mirror_huawei.repo /etc/yum.repos.d/op_mirror_huawei.repo.bak"],
         'waitstr': '#'})
    #临时配置openeuler在线yum源，安装lshw等
    yum_file = ['[osrepo]',
                'name=osrepo',
                'baseurl=https://mirrors.tools.huawei.com/openeuler/openEuler-22.03-LTS-SP3/OS/aarch64/',
                'enabled=1',
                'gpgcheck=0',
                'gpgkey=https://mirrors.tools.huawei.com/openeuler/openEuler-22.03-LTS-SP3/OS/aarch64/RPM-GPG-KEY-openEuler']
    for i in yum_file:
        res = node.run({'command': ["echo {} >> /etc/yum.repos.d/op_mirror_huawei.repo".format(i)], 'waitstr': '#'})
    res = node.run({'command': ["cat /etc/yum.repos.d/op_mirror_huawei.repo"], 'waitstr': '#'})
    res = node.run({'command': ["source ~/.install-openrc"], 'waitstr': '#'})
    res = node.run({'command': ["yum clean all"], 'waitstr': '#'})
    res = node.run({'command': ["yum makecache > log.log 2>&1"], 'waitstr': '#'})
    pkg_list = ["lshw", "pcre-devel", "pcre-help", "gcc", "traceroute", "zenity", "diffstat", "gdb", "numad"]
    for pkg_name in pkg_list:
        res = node.run({'command': ["yum install {} -y".format(pkg_name)], 'waitstr': '#'})
    res = node.run(
        {'command': [f"mv -f /etc/yum.repos.d/op_mirror_huawei.repo /etc/yum.repos.d/op_mirror_huawei.repo.bak"],
         'waitstr': '#'})
    res = node.run({'command': ["yum clean all"], 'waitstr': '#'})
    res = node.run({'command': ["yum makecache > log.log 2>&1"], 'waitstr': '#'})
    res = node.run({'command': ["touch {}".format(path_file)], 'waitstr': '#'})
