import os
from libs.utils.logger_compat import Log
logger = Log.getLogger("AT_Common")



def complile_ets_test(node, compile_env_path='/root'):
    """
    函数说明: 编译内核测试代码
    参数说明:
        node (str): 执行节点
        testsuite_list (list): 测试套名称
        output_path (str): 编译后存放路径
    函数返回: 编译后测试套路径
    """
    # 把shell文件传输到节点
    compile_package_exit_flag_file = 'compile_package_exit_flag_ets'
    remote_dir = "/root"
    path = "{}/ets/".format(compile_env_path) # /root/ets
    res = node.run({'command': ["ls -d  {}".format(path)], 'waitstr': '#'})
    if res['stdout'] is not None and "No such file or directory" not in res['stdout']: # 是指命令的提示结果，即ets的路径的是对的，可以找到下面的目录
        logger.info("testsuite  already complile")
    else:
        node.run({'command': ["cd {}".format(compile_env_path)], 'waitstr': '#'}) # cd /root
        res = node.run({'command': ["ls -d  {}".format(compile_package_exit_flag_file)], 'waitstr': '#'}) # ls -d {compile_package_exit_flag_ets} 在终端上会显示这个文件的名称。res也会包含命令提示结果，如果文件不存在
        if res['stdout'] is not None and "No such file or directory" not in res['stdout']:
            logger.info("compile package already exist")
        else:
            tmp_file_name = 'ets.tar.gz'
            local_dir = os.path.abspath(__file__).split('lib')[0] # 获取当前执行脚本的绝对路径，回到上一级lib目录，再到ets
            remote_dir = "/root"
            os.chdir(local_dir) # 改变当前工作目录到指定的路径
            # os.system('rm -rf {}'.format(tmp_file_name)) # 允许运行存储在字符串中的操作系统命令, 强制删除这个文件或者目录
            # 临时注释
            os.system('tar zcvf {} ets/*'.format(tmp_file_name)) # 当前ets目录下的所有内容（包括子目录和文件）都会被添加到 ets.tar.gz 文件中
            node.putFile({"source_file": os.path.join(local_dir, tmp_file_name),
                          "destination_file": os.path.join(remote_dir, tmp_file_name)}) # 将执行机中的ets压缩包传递到节点
            node.run({'command': ["cd {}".format(remote_dir)]}) # cd /root
            node.run({'command': ["tar zxvf {} > log.log 2>&1".format(tmp_file_name)]})
            # 解压ets压缩包，并将输出（包括标准输出和标准错误）重定向到 log.log 文件中，通过简单的日志记录解压过程中的文件名和可能出现的错误,这里后期要改！
            # node.run({'command': ["rm -rf {}".format(tmp_file_name1)]}) # 删除ets压缩包
            node.run({'command': [f"chmod -R 777 ets"], 'waitstr': '#'}) # 给ets文件赋予最高权限，包括可读可写可执行
            node.run({'command': ["cd {}".format(path)]}) # cd /root/ets
        gen_ets_envinfo(node, path)
        node.run({'command': ["touch {}/{}".format(remote_dir, compile_package_exit_flag_file)], 'waitstr': '#'}) # 创建一个名为“compile_package_exit_flag_ets”的文件在/root目录下,用作判断条件
    return path

def gen_ets_envinfo(node, ets_path):
    node.run({'command': ["cd {}".format(ets_path)]}) # cd /root/ets
    node.run({'command': ["mkdir conf"]}) # 创建conf文件
    env_file = "http://7.218.78.238/env_info/{}_env.json".format(node.localIP) # node自身的参数
    res = node.run({'command': ["curl  {} -o conf/env.json".format(env_file)], 'waitstr': '#'}) # 从env_file链接中下载json文件，存储在conf并命名为env.json
    # res = node.run({'command': ["bash runtest.sh -c --ip {} --password {} --user {} --port {}".format(node.localIP, node.password, node.username, node.port)], 'waitstr': '#'}) # 运行配置文件？
