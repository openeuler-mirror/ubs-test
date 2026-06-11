"""Linux host class inheriting from NodeAdapter.

Provides Linux-specific operations: file/directory, disk/partition, iSCSI, service management.
Supports creating new SSH connections from existing ones via copy() method.

Usage:
    from libs.host import Linux

    linux = Linux({
        "ip": "192.168.1.100",
        "port": 22,
        "user": "root",
        "password": "password",
        "nodeId": "Node0"
    })

    # Execute commands
    result = linux.run({"command": ["ls -la"], "timeout": 30})

    # Copy - create new SSH connection
    linux_copy = linux.copy()
"""

import copy
import logging
import re
import threading
from typing import Any, Optional

from libs.host.node_adapter import NodeAdapter

logger = logging.getLogger(__name__)


class Linux(NodeAdapter):
    """Linux host class with SSH execution and Linux operations.

    Inherits NodeAdapter for SSH connection and command execution.
    Adds Linux-specific methods for file, disk, iSCSI, and service operations.

    Attributes:
        os: Operating system type ('Linux')
        openIscsi: Whether open-iscsi is installed
        logger: Logger instance for compatibility
        networkInfo: Cached network information
        systemInfo: Cached system information
        glock: Thread lock for concurrent operations

    Example:
        linux = Linux({"ip": "192.168.1.100", "user": "root", "password": "..."})
        linux.login()

        # File operations
        linux.createDirectory("/mnt/test")
        linux.createFile("/mnt/test/file.txt")

        # Disk operations
        disk_info = linux.getDisk("/dev/sdb")

        # Copy for parallel execution
        linux2 = linux.copy()
    """

    os: str
    openIscsi: bool
    networkInfo: dict[str, Any]
    systemInfo: dict[str, Any]
    glock: threading.Lock

    def __init__(self, node_info: dict[str, Any]) -> None:
        """Initialize Linux host from node info.

        Args:
            node_info: Node configuration dict with ip, port, user, password, nodeId
        """
        super().__init__(node_info)
        self.os = "Linux"
        self.openIscsi = False
        self.networkInfo: dict[str, Any] = {}
        self.systemInfo: dict[str, Any] = {}
        self.glock = threading.Lock()

    def copy(self) -> "Linux":
        """Create a new Linux instance with new SSH connection.

        Returns:
            New Linux instance with same connection parameters but new SSH connection.

        Example:
            original = Linux({"ip": "192.168.1.100", ...})
            original.login()

            # Create copy for parallel work
            copy_instance = original.copy()
            copy_instance.login()  # Establishes new SSH connection

            # Both can execute commands independently
            original.run({"command": ["ls"]})
            copy_instance.run({"command": ["ls"]})
        """
        node_info = {
            "ip": self.ip,
            "port": self.port,
            "user": self.username,
            "password": self.password,
            "nodeId": self.nodeId,
            "localIP": self.localIP,
            "params": copy.deepcopy(self.detail)
        }
        new_linux = Linux(node_info)
        return new_linux

    # ==================== File/Directory Operations ====================

    def doesPathExist(self, path: str, timeout: int = 30) -> bool:
        """Check if path exists on the host.

        Args:
            path: File or directory path
            timeout: Command timeout

        Returns:
            True if path exists, False otherwise
        """
        result = self.run({
            "command": ["sh", "-c", f"stat {path}"],
            "timeout": timeout,
            "returnCode": True
        })
        return result["rc"] == 0

    def createDirectory(
        self,
        path: str,
        timeout: int = 20,
        check_exist: bool = True,
        option: str = "p"
    ) -> None:
        """Create directory on the host.

        Args:
            path: Directory path to create
            timeout: Command timeout
            check_exist: Check if directory exists before creating
            option: mkdir option (default 'p' for parent directories)

        Raises:
            Exception: If directory creation fails
        """
        if check_exist and self.doesPathExist(path, timeout):
            return

        cmd = ["sh", "-c", "mkdir"]
        if option:
            cmd.append("-" + option)
        cmd.append(path)

        result = self.run({"command": cmd, "timeout": timeout})
        if result["rc"] != 0:
            raise Exception(f"Failed to create directory {path}: {result['stderr']}")

    def deleteDirectory(self, path: str, timeout: int = 60) -> None:
        """Delete directory on the host.

        Args:
            path: Directory path to delete
            timeout: Command timeout

        Raises:
            Exception: If deletion fails
        """
        if not self.doesPathExist(path):
            return

        if path == "/":
            raise Exception("Cannot delete root directory")

        result = self.run({
            "command": ["sh", "-c", f"rm -rf {path}"],
            "timeout": timeout
        })
        if result["rc"] != 0:
            raise Exception(f"Failed to delete directory {path}: {result['stderr']}")

    def createFile(
        self,
        file_path: str,
        content: Optional[str] = None,
        timeout: int = 30
    ) -> None:
        """Create file on the host.

        Args:
            file_path: File path to create
            content: Optional content to write
            timeout: Command timeout

        Raises:
            Exception: If file creation fails
        """
        if content:
            result = self.run({
                "command": ["sh", "-c", f"echo '{content}' > {file_path}"],
                "timeout": timeout
            })
        else:
            result = self.run({
                "command": ["sh", "-c", f"touch {file_path}"],
                "timeout": timeout
            })

        if result["rc"] != 0:
            raise Exception(f"Failed to create file {file_path}: {result['stderr']}")

    def deleteFile(self, file_path: str, timeout: int = 60) -> None:
        """Delete file on the host.

        Args:
            file_path: File path to delete
            timeout: Command timeout

        Raises:
            Exception: If deletion fails
        """
        if not self.doesPathExist(file_path):
            return

        if file_path == "/":
            raise Exception("Cannot delete root")

        result = self.run({
            "command": ["sh", "-c", f"rm -rf {file_path}"],
            "timeout": timeout
        })
        if result["rc"] != 0:
            raise Exception(f"Failed to delete file {file_path}: {result['stderr']}")

    def readFile(self, file_path: str, timeout: int = 600) -> list[str]:
        """Read file content from host.

        Args:
            file_path: File path to read
            timeout: Command timeout

        Returns:
            List of file content lines

        Raises:
            Exception: If read fails
        """
        result = self.run({
            "command": ["sh", "-c", f"cat {file_path}"],
            "timeout": timeout
        })
        if result["rc"] != 0:
            raise Exception(f"Failed to read file {file_path}")

        lines = self._split_output(result["stdout"])
        # Filter out cat command echo
        lines = [line for line in lines if "cat" not in line or file_path not in line]
        return lines

    def writeToFile(
        self,
        file_path: str,
        content: str,
        append: bool = True,
        timeout: int = 30
    ) -> int:
        """Write content to file.

        Args:
            file_path: File path to write
            content: Content to write
            append: Append to file (True) or overwrite (False)
            timeout: Command timeout

        Returns:
            Command return code

        Raises:
            Exception: If write fails
        """
        op = ">>" if append else ">"
        result = self.run({
            "command": ["sh", "-c", f"echo '{content}' {op} {file_path}"],
            "timeout": timeout
        })
        if result["rc"] != 0:
            raise Exception(f"Failed to write to file {file_path}: {result['stderr']}")
        return result["rc"]

    def copyFile(
        self,
        source: str,
        destination: str,
        timeout: int = 120
    ) -> None:
        """Copy file on the host.

        Args:
            source: Source file path
            destination: Destination file path
            timeout: Command timeout

        Raises:
            Exception: If copy fails
        """
        if source == destination:
            return

        result = self.run({
            "command": ["sh", "-c", f"cp -f {source} {destination}"],
            "timeout": timeout
        })
        if result["rc"] != 0:
            raise Exception(f"Failed to copy {source} to {destination}: {result['stderr']}")

    def listFile(
        self,
        path: str,
        list_hidden: bool = True,
        timeout: int = 30
    ) -> dict[str, dict[str, Any]]:
        """List files in directory.

        Args:
            path: Directory path
            list_hidden: Include hidden files
            timeout: Command timeout

        Returns:
            Dict of file info: {filename: {is_dir, size, permission, ...}}

        Raises:
            Exception: If listing fails
        """
        option = "-l" + ("A" if list_hidden else "")
        result = self.run({
            "command": ["sh", "-c", f"ls {option} {path} --color=never"],
            "timeout": timeout
        })
        if result["rc"] != 0:
            raise Exception(f"Failed to list files in {path}")

        lines = self._split_output(result["stdout"])
        file_info: dict[str, dict[str, Any]] = {}

        for line in lines:
            match = re.search(
                r'(\S)'                           # File type
                r'(\S{9})\S?\s+'                  # Permission
                r'(\d+)\s+'                       # Links
                r'(\S+)\s+'                       # Owner
                r'(\S+)\s+'                       # Group
                r'(\d+)\s+'                       # Size
                r'(\S+)\s+'                       # Date
                r'(\S+)\s+'                       # Time
                r'(.+)',                          # Filename
                line
            )
            if match:
                directory = match.group(1)
                permission = match.group(2)
                size = match.group(6)
                filename = match.group(9).strip()

                if filename and not filename.startswith("ls"):
                    other_perm = permission[-3:]
                    file_info[filename] = {
                        "is_dir": directory == "d",
                        "size": size + "Bytes",
                        "permission": permission,
                        "readable": other_perm[0] == "r",
                        "writeable": other_perm[1] == "w",
                        "executable": other_perm[2] in ("x", "s", "t")
                    }

        return file_info

    # ==================== Disk/Partition Operations ====================

    def getDisk(self, disk_label: str, timeout: int = 30) -> dict[str, Any]:
        """Get disk information.

        Args:
            disk_label: Disk device path (e.g., '/dev/sdb')
            timeout: Command timeout

        Returns:
            Dict with size, size_byte, partitions

        Raises:
            Exception: If disk not found
        """
        result = self.run({
            "command": ["sh", "-c", f"fdisk {disk_label} -l"],
            "timeout": timeout
        })

        if result["rc"] != 0:
            raise Exception(f"Could not find disk {disk_label}")

        stdout = result["stdout"] or ""

        # Parse size
        size_match = re.search(r"((\d+(\.\d*)?)|0\.\d+) ([GKMTP]?B)", stdout)
        size = size_match.group() if size_match else ""

        size_byte_match = re.search(r",\s*(\d+)\s*bytes", stdout)
        size_byte = int(size_byte_match.group(1)) if size_byte_match else -1

        # Check for partitions
        has_partition = bool(re.search(r"doesn't contain a valid partition table", stdout))
        if not has_partition:
            has_partition = bool(re.search(r'' + str(disk_label) + r'\d+', stdout))

        partitions = []
        if has_partition:
            partitions = self.getPartitions(disk=disk_label, timeout=timeout)

        disk_info = {
            "size": size.replace(" ", ""),
            "size_byte": size_byte,
            "partitions": partitions
        }

        return disk_info

    def getDisks(self, timeout: int = 30) -> dict[str, str]:
        """Get all disks information.

        Args:
            timeout: Command timeout

        Returns:
            Dict of {disk_path: size}

        Raises:
            Exception: If command fails
        """
        result = self.run({
            "command": ["sh", "-c", "fdisk -l"],
            "timeout": timeout
        })

        if result["rc"] != 0:
            raise Exception("Could not find disks")

        disk_info: dict[str, str] = {}
        regex = re.compile(r'^Disk\s*(/dev/\S*):\s*(\d+\.{,1}\d{,2}\s+\w+),')

        lines = self._split_output(result["stdout"])
        for line in lines:
            match = regex.match(line)
            if match:
                disk = match.groups()[0]
                size = match.groups()[1]
                disk_info[disk] = size

        return disk_info

    def getPartitions(
        self,
        disk: Optional[str] = None,
        timeout: int = 30
    ) -> list[dict[str, Any]]:
        """Get partition information.

        Args:
            disk: Optional disk device path
            timeout: Command timeout

        Returns:
            List of partition info dicts

        Raises:
            Exception: If command fails
        """
        if disk:
            result = self.run({
                "command": ["sh", "-c", f"parted {disk} -s p"],
                "timeout": timeout
            })
        else:
            result = self.run({
                "command": ["sh", "-c", "parted -l"],
                "timeout": timeout
            })

        if result["rc"] != 0:
            stdout = result["stdout"] or ""
            if re.search(r'unrecognised disk label', stdout):
                raise Exception(f"There are no partitions on disk {disk}")
            raise Exception("Unable to find any partitions")

        mounts = self.getMountPoints(timeout=timeout)

        lines = self._split_output(result["stdout"])
        partitions: list[dict[str, Any]] = []
        current_disk = ""
        current_label = ""

        for line in lines:
            # Match disk device
            disk_match = re.search(r'/dev((/eui\.\w+|/\w+)*)', line)
            if disk_match:
                current_disk = "/dev" + disk_match.group(1)
                continue

            # Match partition table label
            label_match = re.search(r'Partition Table: (\w+)', line)
            if label_match:
                current_label = label_match.group(1)
                continue

            # Match partition line
            partition_match = re.search(r'\d+\s+\d+', line)
            if partition_match:
                vols = re.split(r'\s+', self._trim(line))
                partition = current_disk + vols[0]

                fs = vols[5] if len(vols) > 5 and re.match(r'\w+\d*', vols[5]) else None

                mnt = []
                if partition in mounts and "mount_points" in mounts[partition]:
                    mnt = mounts[partition]["mount_points"]

                partition_info = {
                    "partition": partition,
                    "mounts": mnt,
                    "label": current_label,
                    "fs": fs,
                    "type": vols[4] if len(vols) > 4 else "",
                    "size": vols[3] if len(vols) > 3 else "",
                    "start": vols[1] if len(vols) > 1 else "",
                    "end": vols[2] if len(vols) > 2 else "",
                    "status": None,
                    "info": "linux"
                }
                partitions.append(partition_info)

        return partitions

    def getMountPoints(self, timeout: int = 30) -> dict[str, dict[str, Any]]:
        """Get mount points.

        Args:
            timeout: Command timeout

        Returns:
            Dict of {device: {partition, type, mount_points}}
        """
        result = self.run({
            "command": ["sh", "-c", "mount -v"],
            "timeout": timeout
        })

        device_dict: dict[str, dict[str, Any]] = {}
        if result["rc"] != 0:
            return device_dict

        lines = self._split_output(result["stdout"])
        for line in lines:
            line = self._trim(line)
            match = re.match(r'^(\S+) on (.+?) type (\S+)\s{,}(.*)', line)
            if match:
                device = match.group(1)
                mount_point = match.group(2)
                fs_type = match.group(3)

                if device not in device_dict:
                    device_dict[device] = {
                        "partition": device,
                        "type": fs_type,
                        "mount_points": [mount_point]
                    }
                else:
                    device_dict[device]["mount_points"].append(mount_point)

        return device_dict

    def createPartition(
        self,
        disk: str,
        size: Optional[str] = None,
        filesystem: Optional[str] = None,
        mount: Optional[str] = None,
        timeout: int = 120
    ) -> str:
        """Create partition on disk.

        Args:
            disk: Disk device path
            size: Partition size (e.g., '1GB')
            filesystem: Filesystem type (ext2, ext3, ext4)
            mount: Mount point
            timeout: Command timeout

        Returns:
            New partition path

        Raises:
            Exception: If creation fails
        """
        disk_info = self.getDisk(disk, timeout)

        script = ""
        start = 0

        if not disk_info.get("partitions"):
            script = "mklabel msdos "
            end = size or disk_info["size"]
        else:
            # Find free space
            partitions = disk_info["partitions"]
            if len(partitions) >= 4:
                raise Exception(f"No more free space on disk {disk} (max 4 partitions)")

            # Use end of last partition
            last_end = partitions[-1].get("end", "0") if partitions else "0"
            start = last_end
            end = size if size else "100%"

        script += f"mkpart primary {start} {end} p"

        result = self.run({
            "command": ["sh", "-c", f"parted {disk} -s {script}"],
            "timeout": timeout
        })

        if result["rc"] != 0:
            raise Exception(f"Failed to create partition on {disk}")

        # Get new partition
        new_partitions = self.getPartitions(disk=disk, timeout=timeout)
        existing = {p["partition"] for p in disk_info.get("partitions", [])}

        new_partition = None
        for p in new_partitions:
            if p["partition"] not in existing:
                new_partition = p["partition"]
                break

        if not new_partition:
            raise Exception(f"Could not find new partition on {disk}")

        # Create filesystem if specified
        if filesystem:
            self.createFilesystem(partition=new_partition, filesystem=filesystem, timeout=timeout)

        # Mount if specified
        if mount:
            self.createMount(device=new_partition, mount_point=mount, timeout=timeout)

        return new_partition

    def createFilesystem(
        self,
        partition: str,
        filesystem: Optional[str] = None,
        timeout: int = 120
    ) -> None:
        """Create filesystem on partition.

        Args:
            partition: Partition device path
            filesystem: Filesystem type (ext2, ext3, ext4)
            timeout: Command timeout

        Raises:
            Exception: If creation fails
        """
        if filesystem:
            cmd = ["sh", "-c", f"mkfs -t {filesystem} {partition}"]
        else:
            cmd = ["sh", "-c", f"mkfs {partition}"]

        result = self.run({"command": cmd, "timeout": timeout})
        if result["rc"] != 0:
            raise Exception(f"Failed to create filesystem on {partition}: {result['stderr']}")

    def createMount(
        self,
        device: str,
        mount_point: str,
        timeout: int = 30
    ) -> None:
        """Mount device to mount point.

        Args:
            device: Device path to mount
            mount_point: Mount point path
            timeout: Command timeout

        Raises:
            Exception: If mount fails
        """
        if not self.doesPathExist(mount_point):
            self.createDirectory(mount_point, timeout)

        result = self.run({
            "command": ["sh", "-c", f"mount {device} {mount_point}"],
            "timeout": timeout
        })
        if result["rc"] != 0:
            raise Exception(f"Failed to mount {device} to {mount_point}: {result['stderr']}")

    def umount(self, mount: str, force: bool = False, timeout: int = 120) -> None:
        """Unmount device or mount point.

        Args:
            mount: Mount point or device path
            force: Force unmount with -l option
            timeout: Command timeout

        Raises:
            Exception: If unmount fails
        """
        cmd = "umount" + (" -l" if force else "")
        result = self.run({
            "command": ["sh", "-c", f"{cmd} {mount}"],
            "timeout": timeout
        })

        if result["rc"] != 0:
            stderr = result["stderr"] or ""
            if "not mounted" in stderr:
                return
            raise Exception(f"Could not umount {mount}: {stderr}")

    # ==================== Service Operations ====================

    def startService(self, name: str, timeout: int = 30) -> None:
        """Start service.

        Args:
            name: Service name
            timeout: Command timeout

        Raises:
            Exception: If start fails
        """
        result = self.run({
            "command": ["sh", "-c", f"service {name} start"],
            "timeout": timeout
        })
        if result["rc"] != 0:
            raise Exception(f"Failed to start service {name}: {result['stderr']}")

    def stopService(self, name: str, timeout: int = 30) -> None:
        """Stop service.

        Args:
            name: Service name
            timeout: Command timeout

        Raises:
            Exception: If stop fails
        """
        result = self.run({
            "command": ["sh", "-c", f"service {name} stop"],
            "timeout": timeout
        })
        if result["rc"] != 0:
            raise Exception(f"Failed to stop service {name}: {result['stderr']}")

    def getServiceStatus(self, name: str, timeout: int = 30) -> str:
        """Get service status.

        Args:
            name: Service name
            timeout: Command timeout

        Returns:
            'running' or 'stopped'
        """
        result = self.run({
            "command": ["sh", "-c", f"service {name} status"],
            "timeout": timeout
        })

        stdout = result["stdout"] or ""
        if "running" in stdout:
            return "running"
        elif "stopped" in stdout or "unused" in stdout:
            return "stopped"
        return "unknown"

    # ==================== iSCSI Operations ====================

    def checkOpenIscsi(self, timeout: int = 10) -> bool:
        """Check if open-iscsi is installed.

        Args:
            timeout: Command timeout

        Returns:
            True if installed

        Raises:
            Exception: If not installed
        """
        result = self.run({
            "command": ["sh", "-c", "which iscsiadm"],
            "timeout": timeout,
            "returnCode": True
        })

        if result["rc"] != 0:
            raise Exception("Open iSCSI is not installed on this host")

        self.openIscsi = True
        return True

    def getIqn(self, timeout: int = 30) -> str:
        """Get host IQN.

        Args:
            timeout: Command timeout

        Returns:
            IQN string

        Raises:
            Exception: If IQN not found
        """
        self.checkOpenIscsi()

        result = self.run({
            "command": ["sh", "-c", "cat /etc/iscsi/initiatorname.iscsi"],
            "timeout": timeout
        })

        if result["rc"] != 0:
            raise Exception("Could not find iSCSI initiatorname file")

        lines = self._split_output(result["stdout"])
        for line in lines:
            match = re.search(r'InitiatorName=(\S+)', line)
            if match:
                return match.group(1)

        raise Exception("Could not parse IQN")

    def addTargetPortal(
        self,
        ip: str,
        chap_user: Optional[str] = None,
        chap_password: Optional[str] = None,
        ip_type: str = "ipv4",
        timeout: int = 30
    ) -> None:
        """Add target portal.

        Args:
            ip: Portal IP address
            chap_user: CHAP username (optional)
            chap_password: CHAP password (optional)
            ip_type: 'ipv4' or 'ipv6'
            timeout: Command timeout
        """
        self.checkOpenIscsi()

        if ip_type.lower() == "ipv6":
            base_cmd = ["sh", "-c", f"iscsiadm -m discovery -p {ip} -t st"]
        else:
            base_cmd = ["sh", "-c", f"iscsiadm -m discovery -p {ip}:3260 -t st"]

        self.run({"command": base_cmd, "timeout": timeout})

    def targetLogin(
        self,
        target_iqn: str,
        target_portal: Optional[str] = None,
        timeout: int = 60
    ) -> dict[str, list[str]]:
        """Login to iSCSI target.

        Args:
            target_iqn: Target IQN
            target_portal: Portal IP (optional)
            timeout: Command timeout

        Returns:
            Dict with session_ids list
        """
        self.checkOpenIscsi()

        cmd = ["sh", "-c", "iscsiadm", "-m", "node", "--target", target_iqn]
        if target_portal:
            cmd.extend(["--portal", f"{target_portal}:3260"])
        cmd.append("--login")

        self.run({"command": cmd, "timeout": timeout})

        # Get session IDs
        sessions = self.getSessionMappings(timeout=timeout)
        session_ids = []

        for session_id, info in sessions.items():
            if target_portal:
                if info.get("portal") == target_portal:
                    session_ids.append(session_id)
            else:
                session_ids.append(session_id)

        return {"session_ids": session_ids}

    def sessionLogout(self, session_id: str, timeout: int = 30) -> None:
        """Logout from iSCSI session.

        Args:
            session_id: Session ID to logout
            timeout: Command timeout

        Raises:
            Exception: If session not found
        """
        self.checkOpenIscsi()

        sessions = self.getSessionMappings(timeout=timeout)
        if session_id not in sessions:
            raise Exception(f"Session {session_id} was not found")

        portal = sessions[session_id]["portal"]
        target = sessions[session_id]["target"]

        self.run({
            "command": ["sh", "-c", f"iscsiadm -m node -u -T {target} -p {portal}:3260"],
            "timeout": timeout
        })

    def getSessionMappings(self, timeout: int = 60) -> dict[str, dict[str, Any]]:
        """Get iSCSI session mappings.

        Args:
            timeout: Command timeout

        Returns:
            Dict of {session_id: {target, portal, scsi_device, luns}}
        """
        self.checkOpenIscsi()

        result = self.run({
            "command": ["sh", "-c", "iscsiadm -m session -P 3"],
            "timeout": timeout
        })

        if result["rc"] != 0:
            stdout = result["stdout"] or ""
            if "No active sessions" in stdout:
                return {}
            return {}

        lines = self._split_output(result["stdout"])
        map_info: dict[str, dict[str, Any]] = {}
        cur_session = None
        cur_target = None
        cur_portal = None
        lun_cnt = 1

        for line in lines:
            # Match target
            target_match = re.search(r'Target:\s+(\S+)', line)
            if target_match:
                cur_target = target_match.group(1)
                continue

            # Match portal
            portal_match = re.search(r'Current Portal:\s+(\S+):', line)
            if portal_match:
                cur_portal = portal_match.group(1)
                continue

            # Match session ID
            session_match = re.search(r'SID:\s+(\d+)', line)
            if session_match:
                cur_session = session_match.group(1)
                map_info[cur_session] = {
                    "target": cur_target,
                    "portal": cur_portal
                }
                lun_cnt = 1
                continue

            # Match LUN
            lun_match = re.search(r'scsi\d+\s+Channel\s+\d+\s+Id\s+\d+\s+Lun:\s+(\d+)$', line)
            if lun_match and cur_session and cur_session in map_info:
                if "luns" not in map_info[cur_session]:
                    map_info[cur_session]["luns"] = {lun_cnt: lun_match.group(1)}
                else:
                    map_info[cur_session]["luns"][lun_cnt] = lun_match.group(1)
                lun_cnt += 1

        return map_info

    def rescanIscsiTarget(self, timeout: int = 60) -> None:
        """Rescan iSCSI targets.

        Args:
            timeout: Command timeout
        """
        self.checkOpenIscsi()
        self.run({
            "command": ["sh", "-c", "iscsiadm -m session -R"],
            "timeout": timeout
        })

    # ==================== Process Operations ====================

    def getProcessId(self, process_name: str, timeout: int = 30) -> list[str]:
        """Get process IDs by name.

        Args:
            process_name: Process name
            timeout: Command timeout

        Returns:
            List of process IDs

        Raises:
            Exception: If no process found
        """
        result = self.run({
            "command": ["sh", "-c", f"ps -C {process_name} -o pid"],
            "timeout": timeout
        })

        if result["rc"] != 0:
            raise Exception(f"Unable to find process {process_name}")

        ids = []
        lines = self._split_output(result["stdout"])
        for line in lines:
            match = re.match(r'^\d+$', self._trim(line))
            if match:
                ids.append(match.group())

        return ids

    def getProcessList(self, timeout: int = 30) -> dict[str, dict[str, str]]:
        """Get all processes.

        Args:
            timeout: Command timeout

        Returns:
            Dict of {pid: {priority, pid, ppid, name, cmdline}}
        """
        result = self.run({
            "command": ["sh", "-c", "ps -Awwo nice,pid,ppid,comm,args"],
            "timeout": timeout
        })

        process_info: dict[str, dict[str, str]] = {}
        lines = self._split_output(result["stdout"])

        for line in lines:
            match = re.match(
                r'^\s*(\-?\d*)\s+(\d+)\s+(\d+)\s+(\S+)\s+(.+?)\s*$',
                line
            )
            if match:
                process_info[match.group(2)] = {
                    "priority": match.group(1),
                    "pid": match.group(2),
                    "ppid": match.group(3),
                    "name": match.group(4),
                    "cmdline": match.group(5)
                }

        return process_info

    def getProcessInfo(self, pid: str, timeout: int = 30) -> dict[str, str]:
        """Get process info by PID.

        Args:
            pid: Process ID
            timeout: Command timeout

        Returns:
            Dict with priority, pid, ppid, name, cmdline

        Raises:
            Exception: If process not found
        """
        result = self.run({
            "command": ["sh", "-c", f"ps -p {pid} -wwo nice,pid,ppid,comm,args"],
            "timeout": timeout
        })

        if result["rc"] != 0:
            raise Exception(f"Unable to find process with pid {pid}")

        lines = self._split_output(result["stdout"])
        for line in lines:
            match = re.match(
                r'^\s*(\-?\d*)\s+(\d+)\s+(\d+)\s+(\S+)\s+(.+?)\s*$',
                line
            )
            if match:
                return {
                    "priority": match.group(1),
                    "pid": match.group(2),
                    "ppid": match.group(3),
                    "name": match.group(4),
                    "cmdline": match.group(5)
                }

        raise Exception(f"Could not parse process info for {pid}")

    # ==================== Network Operations ====================

    def getNetworkInfo(self, timeout: int = 30) -> dict[str, Any]:
        """Get network information.

        Args:
            timeout: Command timeout

        Returns:
            Dict with hostname, gateway, interface info
        """
        if self.networkInfo:
            return self.networkInfo

        network_info: dict[str, Any] = {}

        # Get hostname
        result = self.run({
            "command": ["sh", "-c", "uname -n"],
            "timeout": timeout
        })
        lines = self._split_output(result["stdout"])
        for line in lines:
            if "uname" not in line:
                match = re.match(r'^\S+$', line)
                if match:
                    network_info["hostname"] = match.group()
                    break

        # Get interfaces
        result = self.run({
            "command": ["sh", "-c", "ifconfig"],
            "timeout": timeout
        })

        network_info["interface"] = {}
        current_interface = None
        lines = self._split_output(result["stdout"])

        for line in lines:
            # SUSE format
            net_match = re.match(r'^(\S+)\s+Link\s+encap', line)
            # RedHat format
            net_match_rh = re.match(r'^(\S+):\s+flags=', line)

            if net_match:
                current_interface = net_match.group(1)
                network_info["interface"][current_interface] = {}
            elif net_match_rh:
                current_interface = net_match_rh.group(1)
                network_info["interface"][current_interface] = {}

            # IPv4 SUSE
            ipv4_match = re.search(r'inet\s+addr:\s*(\S+)\s+', line)
            # IPv4 RedHat
            ipv4_match_rh = re.search(r'inet\s+(\S+)\s+', line)

            if ipv4_match and current_interface:
                network_info["interface"][current_interface]["ipv4_address"] = ipv4_match.group(1)
                netmask_match = re.search(r'Mask:\s*(\S+)\s*$', line)
                if netmask_match:
                    network_info["interface"][current_interface]["netmask"] = netmask_match.group(1)
            elif ipv4_match_rh and current_interface:
                network_info["interface"][current_interface]["ipv4_address"] = ipv4_match_rh.group(1)
                netmask_match = re.search(r'netmask\s+(\S+)\s+broadcast', line)
                if netmask_match:
                    network_info["interface"][current_interface]["netmask"] = netmask_match.group(1)

        # Get gateway
        result = self.run({
            "command": ["sh", "-c", "netstat -rn"],
            "timeout": timeout
        })
        lines = self._split_output(result["stdout"])
        for line in lines:
            gateway_match = re.match(r'^0\.0\.0\.0\s+(\S+)', line)
            if gateway_match:
                network_info["gateway"] = gateway_match.group(1)

        self.networkInfo = network_info
        return network_info

    def getIpAddress(
        self,
        interface: Optional[str] = None,
        ip_type: Optional[str] = None
    ) -> str:
        """Get IP address.

        Args:
            interface: Interface name (optional)
            ip_type: 'ipv4' or 'ipv6' (optional)

        Returns:
            IP address

        Raises:
            Exception: If interface or address not found
        """
        address_type = (ip_type + "_address") if ip_type else "ipv4_address"

        # Return configured IP if no interface specified
        if not interface and not ip_type and self.localIP:
            return self.localIP

        net_info = self.getNetworkInfo()

        # Get first IP if no interface specified but ip_type is
        if not interface and ip_type:
            for inet in sorted(net_info["interface"]):
                iface_data = net_info["interface"][inet]
                if isinstance(iface_data, dict) and address_type in iface_data:
                    return iface_data[address_type]

        if interface not in net_info["interface"]:
            raise Exception(f"Interface {interface} does not exist on this host")

        if address_type not in net_info["interface"][interface]:
            raise Exception(f"Interface {interface} does not have {ip_type} address")

        return net_info["interface"][interface][address_type]

    def getHostname(self, timeout: int = 30) -> str:
        """Get hostname.

        Args:
            timeout: Command timeout

        Returns:
            Hostname string
        """
        net_info = self.getNetworkInfo(timeout)
        return net_info.get("hostname", "")

    # ==================== System Operations ====================

    def getSystemInfo(self, timeout: int = 30) -> dict[str, str]:
        """Get system information.

        Args:
            timeout: Command timeout

        Returns:
            Dict with kernel_name, kernel_release, host_name, os_type, etc.
        """
        if self.systemInfo:
            return self.systemInfo

        result = self.run({
            "command": ["sh", "-c", "uname -a"],
            "timeout": timeout
        })

        if result["rc"] != 0:
            raise Exception("Cannot get system information")

        lines = self._split_output(self._trim(result["stdout"]))

        for line in lines:
            if "uname" in line or "@#>" in line:
                continue

            info = line.split()
            if len(info) < 3:
                continue

            self.systemInfo = {
                "kernel_name": info[0],
                "host_name": info[1],
                "kernel_release": info[2],
                "os_type": info[-1] if info else "",
                "hardware_platform": info[-2] if len(info) > 2 else "",
                "processor_type": info[-3] if len(info) > 3 else "",
                "hardware_name": info[-4] if len(info) > 4 else "",
                "kernel_version": " ".join(info[3:-4]) if len(info) > 7 else ""
            }
            break

        return self.systemInfo

    def getVersion(self, timeout: int = 30) -> str:
        """Get kernel version.

        Args:
            timeout: Command timeout

        Returns:
            Kernel version string
        """
        result = self.run({
            "command": ["sh", "-c", "uname -r"],
            "timeout": timeout
        })

        if result["rc"] != 0:
            raise Exception("Get OS version failed")

        lines = self._split_output(self._trim(result["stdout"]))
        for line in lines:
            if "uname" in line:
                continue
            match = re.match(r'(\S+)', line)
            if match:
                return match.group(1)

        return ""

    def getArchitecture(self, timeout: int = 30) -> str:
        """Get system architecture.

        Args:
            timeout: Command timeout

        Returns:
            Architecture string (e.g., 'x86_64')
        """
        result = self.run({
            "command": ["sh", "-c", "uname -m"],
            "timeout": timeout
        })

        lines = self._split_output(result["stdout"] or "")
        for line in lines:
            if "uname" in line or "root" in line:
                continue
            match = re.search(r'(\S+)', line)
            if match:
                return match.group(1)

        return ""

    # ==================== HBA Operations ====================

    def getHbaInfo(self, timeout: int = 60) -> dict[str, dict[str, str]]:
        """Get HBA card information.

        Args:
            timeout: Command timeout

        Returns:
            Dict of {port_wwn: {port, node}}
        """
        result = self.run({
            "command": ["sh", "-c", "ls -l '/sys/class/fc_host/'"],
            "timeout": timeout
        })

        stderr = result["stderr"] or ""
        if result["rc"] != 0:
            if "No such file" in stderr:
                logger.warning(f"No HBA card found on host {self.ip}")
                return {}
            raise Exception(f"Failed to get HBA info: {stderr}")

        hba_adapter = []
        lines = self._split_output(result["stdout"])
        for line in lines:
            match = re.search(r'host[0-9]+', line)
            if match:
                hba_adapter.append(match.group())

        hba_dict: dict[str, dict[str, str]] = {}
        for adapter in hba_adapter:
            result = self.run({
                "command": ["sh", "-c", "cat port_name node_name"],
                "timeout": timeout,
                "directory": f"/sys/class/fc_host/{adapter}"
            })

            lines = self._split_output(result["stdout"])
            port = None

            for line in lines:
                if "cat" in line:
                    continue
                if re.match(r'^0x', line):
                    port = self._normalize_wwn(line)
                if port and len(lines) > lines.index(line) + 1:
                    next_line = lines[lines.index(line) + 1]
                    if re.match(r'^0x', next_line):
                        hba_dict[port] = {
                            "port": port,
                            "node": self._normalize_wwn(next_line)
                        }
                        break

        return hba_dict

    # ==================== Utility Methods ====================

    def which(self, program: str, timeout: int = 30) -> str:
        """Check if program exists and return path.

        Args:
            program: Program name
            timeout: Command timeout

        Returns:
            Program path

        Raises:
            Exception: If program not found
        """
        result = self.run({
            "command": ["sh", "-c", f"which {program}"],
            "timeout": timeout
        })

        stdout = result["stdout"] or ""
        pattern = f"no {program} in|{program} not found"

        if not stdout or re.search(pattern, stdout, re.IGNORECASE):
            raise Exception(f"{program} was not found on {self.ip}")

        lines = self._split_output(self._trim(stdout))
        for line in lines:
            if "which" in line:
                continue
            if program in line:
                return line

        raise Exception(f"{program} was not found")

    def getMd5Checksum(self, path: str, timeout: int = 60) -> str:
        """Get MD5 checksum of file.

        Args:
            path: File path
            timeout: Command timeout

        Returns:
            MD5 checksum string

        Raises:
            Exception: If file not found or command fails
        """
        if not self.doesPathExist(path):
            raise Exception(f"{path} was not found")

        result = self.run({
            "command": ["sh", "-c", f"md5sum {path}"],
            "timeout": timeout
        })

        lines = self._split_output(result["stdout"])
        for line in lines:
            if "md5sum" in line:
                continue
            match = re.match(r'^(\w+)(\s+)' + str(path) + '', line)
            if match:
                return match.group(1)

        raise Exception(f"Could not get MD5 checksum for {path}")

    def du(self, path: str, option: str = "sh", timeout: int = 60) -> dict[str, str]:
        """Get directory usage.

        Args:
            path: Directory path
            option: du command option
            timeout: Command timeout

        Returns:
            Dict with size and path

        Raises:
            Exception: If path not found or command fails
        """
        if not self.doesPathExist(path):
            raise Exception(f"Path {path} not exist")

        if path == "/":
            raise Exception("Cannot du root directory")

        cmd = ["sh", "-c", "du", f"-{option}", path]
        result = self.run({"command": cmd, "timeout": timeout})

        if result["rc"] != 0:
            raise Exception(f"du {path} failed: {result['stderr']}")

        return {"stdout": result["stdout"], "stderr": result["stderr"]}

    def _split_output(self, content: Optional[str]) -> list[str]:
        """Split output by line separators.

        Args:
            content: Output string

        Returns:
            List of lines
        """
        if not content:
            return []
        return re.split(r'\x0d?\x0a|\x0d', content)

    def _trim(self, content: str) -> str:
        """Trim whitespace from string.

        Args:
            content: String to trim

        Returns:
            Trimmed string
        """
        return content.strip()

    def _normalize_wwn(self, wwn: str) -> str:
        """Normalize WWN format.

        Args:
            wwn: WWN string (with 0x prefix)

        Returns:
            Normalized WWN
        """
        if wwn.startswith("0x"):
            wwn = wwn[2:]
        return wwn.lower().strip()

    def __repr__(self) -> str:
        return f"Linux(nodeId={self.nodeId}, ip={self.ip}:{self.port})"
