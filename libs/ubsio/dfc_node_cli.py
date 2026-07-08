"""DFC Node CLI wrapper.

Provides node-level operations for DFC testing.
"""

import os
import random
import re
import string
import logging
from typing import Any, Dict, List, Optional, Union

from libs.ubsio import dfc_global_var as Var
from libs.host.linux import Linux

logger = logging.getLogger(__name__)


class DFCNodeCLI:
    """DFC Node CLI wrapper for node-level operations.
    
    Provides methods for:
    - Environment checking (DFC process, mount path)
    - File operations (touch, mkdir, delete, stat)
    - Process management (clear, kill)
    - Docker operations (exec, mount)
    - Data operations (dd, pwrite, pread)
    """
    
    def __init__(self, node: Linux):
        """Initialize DFCNodeCLI with a Linux node.
        
        Args:
            node: Linux node object with run() method
        """
        self._node = node
        self.localIP = node.ip if hasattr(node, 'ip') else getattr(node, 'localIP', None)
        self.logger = logging.getLogger(f"{self.__class__.__name__}.{self.localIP}")
    
    def run_input(self, cmd: str, timeout: int = 60, returnCode: bool = True, waitstr: str = "]#") -> Dict[str, Any]:
        """Execute command and return result.
        
        Args:
            cmd: Command to execute
            timeout: Timeout in seconds
            returnCode: Whether to return exit code
            waitstr: Wait string for command completion
            
        Returns:
            Dict with 'rc', 'stdout', 'stderr' keys
        """
        result = self._node.run({
            "command": [cmd],
            "timeout": timeout,
            "waitstr": waitstr,
        })
        
        # Normalize result keys
        ret = {
            "rc": result.get("returnCode", result.get("rc", -1)),
            "stdout": result.get("stdout", ""),
            "stderr": result.get("stderr", ""),
        }
        return ret
    
    def Check_Env(self, docker_name: str = Var.DOCKER_NAME) -> str:
        """Check environment is ready (DFC process started, mount path mounted).
        
        Args:
            docker_name: Docker container name
            
        Returns:
            Status string
        """
        check_dfc_ret = self.Check_dfc_Process(docker_name)
        if check_dfc_ret != "DFC进程已启动":
            return "dfc进程未启动"
        check_mount_ret = self.check_mountpath()
        if check_mount_ret != "文件系统目录已挂载":
            return "文件系统目录未挂载"
        return "环境已就绪"
    
    def Check_dfc_Process(self, docker_name: str = Var.DOCKER_NAME) -> str:
        """Check DFC process is started.
        
        Args:
            docker_name: Docker container name
            
        Returns:
            Status string
        """
        cmd = f"ps -ef | grep {Var.DFC_NAME} | grep -v grep"
        docker_cmd = f"docker exec {docker_name} bash -c '{cmd}'"
        check_ret = self.run_input(docker_cmd)
        if check_ret.get('stdout'):
            return "DFC进程已启动"
        else:
            return "DFC进程未启动"
    
    def check_mountpath(self, mountpath: str = Var.DOCKER_MOUNT_PATH, docker_name: str = Var.DOCKER_NAME) -> str:
        """Check mount path is mounted.
        
        Args:
            mountpath: Mount path to check
            docker_name: Docker container name
            
        Returns:
            Status string
        """
        cmd = f"ls -l {mountpath}"
        docker_cmd = f"docker exec {docker_name} bash -c '{cmd}'"
        check_ret = self.run_input(docker_cmd)
        if check_ret.get('rc') != 0:
            if "Transport endpoint is not connected" in check_ret.get("stderr", ""):
                return "文件系统目录未挂载"
            else:
                return f"查看文件系统挂载目录存在如下错误: {check_ret}"
        else:
            return "文件系统目录已挂载"
    
    def clear_process(self, process_name: str = 'python3', docker_name: Optional[str] = None) -> None:
        """Clear process on node.
        
        Args:
            process_name: Process name to clear
            docker_name: Docker container name (optional)
        """
        if not docker_name:
            cmd= "ps -ef | grep python3 | grep -v -E 'pytest|firewalld|tuned|grep'"
        else:
            pkill_cmd = f"pkill -9 -f {process_name}"
            cmd = f"docker exec {docker_name} bash -c '{pkill_cmd}'"
        self.run_input(cmd)
    
    def umount_dir(self, docker_name: str = Var.DOCKER_NAME) -> None:
        """Unmount directory.
        
        Args:
            docker_name: Docker container name
        """
        cmd = f"cd {Var.FUSE_PATH};fusermount -u -z {Var.FUSE_NAME}"
        docker_cmd = f"docker exec {docker_name} bash -c '{cmd}'"
        self.run_input(docker_cmd)
    
    def delete_for_kvfile(self, put_file: str = Var.put_file_name, get_file: str = Var.get_file_name,
                          work_dir: str = Var.MAP_DOCKER_PATH) -> None:
        """Delete KV operation files.
        
        Args:
            put_file: Put file name
            get_file: Get file name
            work_dir: Working directory
        """
        for file in (put_file, get_file):
            filePath = f'{work_dir}/{file}'
            self.del_file(filePath)
    
    def del_file(self, file_path: str, docker_name: str = Var.DOCKER_NAME, work_dir: Optional[str] = None,
                 Force_delete: bool = False, timeout: int = 60) -> str:
        """Delete file.
        
        Args:
            file_path: File path to delete
            docker_name: Docker container name
            work_dir: Working directory
            Force_delete: Force delete flag
            timeout: Timeout in seconds
            
        Returns:
            Status string
        """
        rm_cmd = 'rm'
        if Force_delete:
            rm_cmd = 'rm -f'
        
        cmd = f'{rm_cmd} {file_path}'
        if docker_name:
            if not work_dir:
                excute_cmd = f"docker exec {docker_name} bash -c '{cmd}'"
            else:
                excute_cmd = f"docker exec -w {work_dir} {docker_name} bash -c '{cmd}'"
        else:
            if not work_dir:
                excute_cmd = cmd
            else:
                excute_cmd = f"cd {work_dir};{cmd}"
        
        rm_ret = self.run_input(excute_cmd, timeout=timeout)
        if rm_ret.get("rc") != 0:
            if rm_ret.get("stderr"):
                if "No such file or directory" in rm_ret.get("stderr"):
                    return "需要删除的文件并不存在，删除失败"
                else:
                    return f"删除失败: {rm_ret.get('stderr')}"
            else:
                return f"删除失败,rc != 0,但不存在stderr"
        else:
            return "删除成功"
    
    def delete_file(self, file: str, work_dir: str = Var.MAP_DOCKER_PATH) -> None:
        """Delete file from node.
        
        Args:
            file: File name to delete
            work_dir: Working directory
        """
        filePath = f'{work_dir}/{file}'
        # Use node's deleteFile method if available
        if hasattr(self._node, 'deleteFile'):
            self._node.deleteFile(filePath)
        else:
            self.del_file(filePath)
    
    def send_scripts(self, script_name: str, script_path: str = "pykvc_script",
                     map_host_path: str = Var.MAP_HOST_PATH) -> None:
        """Send script to test environment.
        
        Args:
            script_name: Script name
            script_path: Script path in resources
            map_host_path: Host mapping path
        """
        sep ='/'
        path_list = os.path.abspath(__file__).split(os.sep)
        lib_path = path_list.index('libs')
        dfc_script_resource_path = f"{os.sep}".join(path_list[:lib_path] + ["resource"] + ["ubsio"] + [script_path])
        script_path = dfc_script_resource_path + os.sep + script_name
        Enviroment_Path = map_host_path + sep + script_name
        if hasattr(self._node, 'putFile'):
            self._node.putFile(script_path, Enviroment_Path)
        else:
            self.run_input(f"scp {script_path} {Enviroment_Path}")
    
    def Compare_md5sum_file(self, put_file: str = Var.put_file_name, get_file: str = Var.get_file_name,
                            work_dir: str = Var.MAP_DOCKER_PATH, docker_name: str = Var.DOCKER_NAME, 
                            timeout: int = 60) -> bool:
        """Compare MD5sum of put and get files.
        
        Args:
            put_file: Put file name
            get_file: Get file name
            work_dir: Working directory
            docker_name: Docker container name
            timeout: Timeout in seconds
            
        Returns:
            True if MD5 matches, False otherwise
        """
        if work_dir:
            cmd = f"cd {work_dir};md5sum {put_file} {get_file}"
        else:
            cmd = f"md5sum {put_file} {get_file}"
        docker_cmd = f"docker exec {docker_name} bash -c '{cmd}'"
        ret = self.run_input(docker_cmd, timeout=timeout)
        if ret.get('rc', -1) != 0:
            return False
        result = ret.get('stdout', '')
        put_md5sum_ret = re.search(f'(.*?)\s+{put_file}', result)
        put_md5sum = put_md5sum_ret.group().split(' ')[0] if put_md5sum_ret else None
        get_md5sum_ret = re.search(f'(.*?)\s+{get_file}', result)
        get_md5sum = get_md5sum_ret.group().split(' ')[0] if get_md5sum_ret else None
        if put_md5sum != get_md5sum:
            return False
        return True
    
    def docker_exec(self, cmd: str, docker_name: str = Var.DOCKER_NAME, work_dir: Optional[str] = None,
                    time_out: int = 360) -> Dict[str, Any]:
        """Execute command in Docker container.
        
        Args:
            cmd: Command to execute
            docker_name: Docker container name
            work_dir: Working directory
            time_out: Timeout in seconds
            
        Returns:
            Dict with 'rc', 'stdout', 'stderr' keys
        """
        if not work_dir:
            docker_cmd = f"docker exec {docker_name} bash -c '{cmd}'"
        else:
            docker_cmd = f"docker exec -w {work_dir} {docker_name} bash -c '{cmd}'"
        try:
            result = self.run_input(docker_cmd, timeout=time_out)
            return result
        except Exception as e:
            return {
                "rc": -1,
                "stdout": "",
                "stderr": f"Docker命令执行发生异常: {str(e)}"
            }
    
    def stat_file_size(self, file_path: str, docker_name: str = Var.DOCKER_NAME, time_out: int = 60) -> Dict[str, Any]:
        """Get file stat info.
        
        Args:
            file_path: File path
            docker_name: Docker container name
            time_out: Timeout in seconds
            
        Returns:
            Dict with file stat info
        """
        file_dict = {"type": None, "access": None, "size": None, "Access": None, "Modify": None, 
                     "Change": None, "Birth": None}
        cmd = f"stat {file_path}"
        if docker_name:
            extuce_cmd = f"docker exec {docker_name} bash -c '{cmd}'"
        else:
            extuce_cmd = cmd
        check_dir_ret = self.run_input(extuce_cmd, timeout=time_out)
        if check_dir_ret.get("stderr"):
            return file_dict
        else:
            stdout = check_dir_ret.get("stdout", "")
            try:
                file_dict["type"] = re.findall(r"IO Block:\s+\d+\s+(.*?)\n", stdout)[0]
                file_dict["access"] = re.findall(r"Access: \((\d+)/.*?\)\s+Uid:", stdout)[0]
                file_dict["size"] = re.findall(r"Size:\s+(\d+)\s+Blocks:", stdout)[0]
                file_dict["Access"] = re.findall(r"Access:\s+(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+ [+-]\d{4})", stdout)[0]
                file_dict["Modify"] = re.findall(r"Modify:\s+(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+ [+-]\d{4})", stdout)[0]
                file_dict["Change"] = re.findall(r"Change:\s+(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+ [+-]\d{4})", stdout)[0]
            except (IndexError, AttributeError):
                pass
            return file_dict
    
    def ls_file(self, file_name: Optional[str] = None, work_dir: Optional[str] = None, 
                args_l: bool = False, args_h: bool = False, args_a: bool = False,
                docker_name: str = Var.DOCKER_NAME, time_out: int = 60) -> str:
        """List files.
        
        Args:
            file_name: File name pattern
            work_dir: Working directory
            args_l: Use -l flag
            args_h: Use -h flag
            args_a: Use -a flag
            docker_name: Docker container name
            time_out: Timeout in seconds
            
        Returns:
            ls output string
        """
        if file_name is None:
            file_name = ""
        ls_cmd = "ls"
        if args_l:
            ls_cmd += " -l"
        if args_h:
            ls_cmd += " -h"
        if args_a:
            ls_cmd += " -a"
        cmd = f"{ls_cmd} {file_name}"
        if not work_dir:
            docker_cmd = f"docker exec {docker_name} bash -c '{cmd}'"
        else:
            docker_cmd = f"docker exec -w {work_dir} {docker_name} bash -c '{cmd}'"
        ls_ret = self.run_input(docker_cmd, timeout=time_out)
        if ls_ret.get("rc") != 0:
            return ls_ret.get("stderr", "")
        else:
            return ls_ret.get("stdout", "")
    
    def dd_file(self, out_file: str, bs: Union[int, str], count: int = 1, 
                input_file: str = '/dev/urandom', skip: Optional[int] = None, seek: Optional[int] = None,
                docker_name: str = Var.DOCKER_NAME, timeout: int = 300) -> Dict[str, Any]:
        """Execute dd command.
        
        Args:
            out_file: Output file path
            bs: Block size
            count: Block count
            input_file: Input file
            skip: Skip blocks from input
            seek: Seek blocks in output
            docker_name: Docker container name
            timeout: Timeout in seconds
            
        Returns:
            Command result dict
        """
        cmd = f"dd if={input_file} of={out_file} bs={bs} count={count} conv=fdatasync"
        if skip:
            cmd = cmd + f' skip={skip}'
        if seek:
            cmd = cmd + f' seek={seek}'
        kill_cmd = cmd
        if docker_name:
            cmd = f"docker exec {docker_name} bash -c '{cmd}'"
        ret = self.run_input(cmd, timeout=timeout)
        if ret.get("rc"):
            self.kill_cmd_process(kill_cmd, docker_name)
        return ret
    
    def kill_cmd_process(self, cmd: str, docker_name: str = Var.DOCKER_NAME) -> None:
        """Kill process by command.
        
        Args:
            cmd: Command to match
            docker_name: Docker container name
        """
        grep_cmd = f"ps -ef |grep '{cmd}' |grep -v grep |awk '{{print $2}}'"
        if docker_name:
            grep_cmd = f"docker exec {docker_name} bash -c 'ps -ef' |grep '{cmd}' |grep -v grep |awk '{{print $2}}'"
        ret = self.run_input(grep_cmd)
        stdout = ret.get("stdout", "").strip()
        if stdout and stdout != "root@#>":
            process_id = " ".join(stdout.replace("\r", "").split("\n")[:-1])
            kill_cmd = f"kill -9 {process_id}"
            if docker_name:
                kill_cmd = f"docker exec {docker_name} bash -c '{kill_cmd}'"
            self.run_input(kill_cmd)
    
    def cp_file(self, src_path: str, trg_path: str, force: bool = True, 
                docker_name: str = Var.DOCKER_NAME, timeout: int = 300) -> Dict[str, Any]:
        """Copy file.
        
        Args:
            src_path: Source file path
            trg_path: Target file path
            force: Force copy flag
            docker_name: Docker container name
            timeout: Timeout in seconds
            
        Returns:
            Command result dict
        """
        if force:
            cmd = f"/bin/cp -f {src_path} {trg_path}"
        else:
            cmd = f"/bin/cp {src_path} {trg_path}"
        if docker_name:
            cmd = f"docker exec {docker_name} bash -c '{cmd}'"
        return self.run_input(cmd, timeout=timeout)
    
    def pwrite_file(self, file: str, compare_file: Optional[str] = None, data: Optional[bytes] = None,
                    data_len: int = 1024, offset: int = 0, docker_name: str = Var.DOCKER_NAME, 
                    timeout: int = 300, data_code: Optional[str] = None) -> Dict[str, Any]:
        """Execute pwrite command.
        
        Args:
            file: File path
            compare_file: Compare file path
            data: Data to write
            data_len: Data length
            offset: Offset
            docker_name: Docker container name
            timeout: Timeout in seconds
            data_code: Data code
            
        Returns:
            Command result dict
        """
        base_len = 2147479552
        compare_written = ""
        if data:
            data_str = f"data = bytes.fromhex('{data.hex()}')"
        elif data_code:
            data_str = data_code
        else:
            data_str = f"data = os.urandom({data_len})"
        if compare_file:
            compare_written = f"""
        if fd1:
            write_len1 = os.pwrite(fd1, chunk, {offset} + i)
    if fd1:
        os.close(fd1)
    """
        cmd = f"""python3 <<'EOF'
import os, sys, time, traceback, random, string

try:
    fd = os.open('{file}', os.O_RDWR)
    fd1 = os.open('{compare_file}', os.O_RDWR) if {bool(compare_file)} else None
    {data_str}
    for i in range(0, len(data), {base_len}):
        chunk = data[i:i+{base_len}]
        write_len = os.pwrite(fd, chunk, {offset} + i)
        assert write_len == len(chunk), f'write_len: {{write_len}} != data_len: {{len(chunk)}}' 
    {compare_written}
    os.close(fd)
except Exception as e:
    line_info = traceback.extract_tb(e.__traceback__)[-1]
    print(f'❌ 错误: {{e}}')
    print(f'📍 行号: {{line_info.lineno}}')
    print(f'📄 代码: {{line_info.line.strip()}}')
    if fd is not None:
       os.close(fd)
    if fd1 is not None:
       os.close(fd1)
    sys.exit(1)
EOF
"""
        if docker_name:
            cmd = f'''docker exec {docker_name} bash -c "{cmd}"'''
        else:
            cmd = f'''python3 -c "{cmd}"'''
        ret = self.run_input(cmd, timeout=timeout)
        if ret.get("rc"):
            self.clear_process('python3', docker_name)
        return ret
    
    def pread_file(self, file: str, read_len: int, offset: int = 0, compare_file: Optional[str] = None,
                   docker_name: str = Var.DOCKER_NAME, timeout: int = 300) -> Dict[str, Any]:
        """Execute pread command.
        
        Args:
            file: File path
            read_len: Read length
            offset: Offset
            compare_file: Compare file path
            docker_name: Docker container name
            timeout: Timeout in seconds
            
        Returns:
            Command result dict
        """
        compare_written = ""
        if compare_file:
            compare_written = f"""
    fd1 = os.open('{compare_file}', os.O_RDONLY)
    read_data1 = os.pread(fd1, {read_len}, {offset})
    assert read_data == read_data1, 'pread return != data'
    os.close(fd1)
                """
        cmd = f"""python3 <<'EOF'
import os, sys, traceback
try:
    fd = os.open('{file}', os.O_RDWR)
    fd1 = None
    read_data = os.pread(fd, {read_len}, {offset})
    {compare_written}
    os.close(fd)
except Exception as e:
    line_info = traceback.extract_tb(e.__traceback__)[-1]
    print(f'❌ 错误: {{e}}')
    print(f'📍 行号: {{line_info.lineno}}')
    print(f'📄 代码: {{line_info.line.strip()}}')
    if fd is not None:
       os.close(fd)
    if fd1 is not None:
       os.close(fd1)
    sys.exit(1)
EOF
"""
        if docker_name:
            cmd = f'''docker exec {docker_name} bash -c "{cmd}"'''
        else:
            cmd = f'''python3 -c "{cmd}"'''
        ret = self.run_input(cmd, timeout=timeout)
        if ret.get("rc"):
            self.clear_process('python3', docker_name)
        return ret
    
    def pread_file_to_file(self, file: str, read_len: int, target_file: str, offset: int = 0,
                           docker_name: str = Var.DOCKER_NAME, timeout: int = 300) -> Dict[str, Any]:
        """Execute pread and write to file.
        
        Args:
            file: Source file path
            read_len: Read length
            target_file: Target file path
            offset: Offset
            docker_name: Docker container name
            timeout: Timeout in seconds
            
        Returns:
            Command result dict
        """
        cmd = f"""python3 <<'EOF'
import os, sys, traceback
try:
    fd = os.open('{file}', os.O_RDWR)
    fd1 = os.open('{target_file}', os.O_RDWR | os.O_CREAT)
    read_data = os.pread(fd, {read_len}, {offset})
    write_len = os.pwrite(fd1, read_data, 0)
    assert write_len == {read_len}, '写入长度与读取长度不一致'
    os.close(fd)
    os.close(fd1)
except Exception as e:
    line_info = traceback.extract_tb(e.__traceback__)[-1]
    print(f'❌ 错误: {{e}}')
    print(f'📍 行号: {{line_info.lineno}}')
    print(f'📄 代码: {{line_info.line.strip()}}')
    if fd is not None:
       os.close(fd)
    if fd1 is not None:
       os.close(fd1)
    sys.exit(1)
EOF
"""
        if docker_name:
            cmd = f'''docker exec {docker_name} bash -c "{cmd}"'''
        else:
            cmd = f'''python3 -c "{cmd}"'''
        ret = self.run_input(cmd, timeout=timeout)
        if ret.get("rc"):
            self.clear_process('python3', docker_name)
        return ret
    
    def get_file_md5(self, file_path: str, docker_name: str = Var.DOCKER_NAME, work_dir: Optional[str] = None,
                     offset: int = 0, length: Optional[int] = None, time_out: int = 360) -> Dict[str, Any]:
        """Get file MD5 hash.
        
        Args:
            file_path: File path
            docker_name: Docker container name
            work_dir: Working directory
            offset: Offset
            length: Length to read
            time_out: Timeout in seconds
            
        Returns:
            Dict with 'rc', 'md5', 'stderr' keys
        """
        dd_part = f"dd if={file_path} bs=1 skip={offset}"
        if length is not None:
            dd_part += f" count={length}"
        full_cmd = f"{dd_part} 2>/dev/null | md5sum"
        exec_ret = self.docker_exec(cmd=full_cmd, docker_name=docker_name, work_dir=work_dir, time_out=time_out)
        
        rc = exec_ret.get('rc', -1)
        stdout = exec_ret.get('stdout', '').strip()
        stderr = exec_ret.get('stderr', '').strip()
        
        if rc == 0:
            try:
                md5_val = stdout.split()[0]
                if len(md5_val) == 32:
                    return {"rc": 0, "md5": md5_val, "stderr": ""}
                else:
                    return {"rc": -1, "md5": "", "stderr": f"MD5 格式异常: {stdout}"}
            except Exception as e:
                return {"rc": -1, "md5": "", "stderr": f"解析 MD5 异常: {str(e)}"}
        else:
            return {"rc": rc, "md5": "", "stderr": stderr}
    
    def random_name(self, min_lenth: int = 1, max_lenth: int = 255) -> str:
        """Generate random name.
        
        Args:
            min_lenth: Minimum length
            max_lenth: Maximum length
            
        Returns:
            Random name string
        """
        allowed_chars = string.ascii_letters + string.digits + "@" + "?" + "_" + "-" + ":"
        file_name_length = random.randint(min_lenth, max_lenth)
        if file_name_length <= 0:
            return f"无法生成长度为{file_name_length}的名称"
        first_char = random.choice(string.ascii_letters + string.digits)
        remaining_chars = ''.join(random.choices(allowed_chars, k=file_name_length - 1))
        random_dir_name = first_char + remaining_chars
        return random_dir_name