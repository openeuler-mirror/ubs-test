"""DFC global variables.

"""

# BIO相关路径
BIO_PATH = "/opt/boostio/"
BIO_BIN_PATH = f"{BIO_PATH}/bin"
BIO_CONF_PATH = f"{BIO_PATH}/bin/conf/bio.conf"
BIO_LIB_PATH = f"{BIO_PATH}/lib"

# 容器名称
DOCKER_NAME = "falcon_new2"
# dfc进程名字
DFC_NAME = "dfc_server"
# KV部署形式
KV_DEPLOY = "converged"
disk_dict = {"192.168.41.123":"nvme2n1"}

# 容器外映射路径
DOCKER_OUTSIDE_MAP_PATH = '/home/ubsio_dfc/'
MAP_HOST_PATH = f'{DOCKER_OUTSIDE_MAP_PATH}/scripts'
# 容器内映射路径
DOCKER_INSIDE_MAP_PATH = '/home/ubsio_dfc/'
MAP_DOCKER_PATH = f'{DOCKER_INSIDE_MAP_PATH}/scripts'

# 容器中BIO拉起后日志路径
DAEMON_LOGPATH = f'/opt/boostio/bin/daemon.log'
BIO_LOGPATH = f'/var/log/boostio/bio.log'

# 容器中dfc拉起后日志路径
DFC_LOGPATH = f'{DOCKER_INSIDE_MAP_PATH}/dfc_log/dfc.log'

# put数据写入文件中
put_file_name = 'put_value.txt'

# get数据写入文件中
get_file_name = 'get_value.txt'

# 容器内挂载路径
FUSE_PATH = '/opt'
FUSE_NAME = 'mount_dir'
DOCKER_MOUNT_PATH = f'{FUSE_PATH}/{FUSE_NAME}/'

# shell并发脚本名
concurrent_shell = "parallel_run.sh"
concurrent_log_path = f'{DOCKER_INSIDE_MAP_PATH}/concurrent_task.log'