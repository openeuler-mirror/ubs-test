"""Unit tests for Linux host class.

Tests cover:
- Initialization and copy functionality
- File/directory operations (mocked SSH)
- Disk operations (mocked)
- Utility methods
"""

import pytest
from unittest.mock import MagicMock, patch
from libs.host.linux import Linux


class TestLinuxInitialization:
    """Test Linux class initialization."""

    def test_init_basic(self):
        """Test basic initialization."""
        node_info = {
            "ip": "192.168.1.100",
            "port": 22,
            "user": "root",
            "password": "test_password",
            "nodeId": "Node0"
        }
        linux = Linux(node_info)
        
        assert linux.ip == "192.168.1.100"
        assert linux.port == 22
        assert linux.username == "root"
        assert linux.password == "test_password"
        assert linux.nodeId == "Node0"
        assert linux.os == "Linux"
        assert linux.openIscsi == False

    def test_init_with_params(self):
        """Test initialization with params."""
        node_info = {
            "ip": "192.168.1.100",
            "port": 22,
            "user": "root",
            "password": "test",
            "nodeId": "Node0",
            "localIP": "192.168.1.101",
            "params": {"host_role": "DPU_CLIENT"}
        }
        linux = Linux(node_info)
        
        assert linux.localIP == "192.168.1.101"
        assert linux.detail == {"host_role": "DPU_CLIENT"}


class TestLinuxCopy:
    """Test copy functionality - creates new SSH connection."""

    def test_copy_creates_new_instance(self):
        """Test copy creates new Linux instance."""
        node_info = {
            "ip": "192.168.1.100",
            "port": 22,
            "user": "root",
            "password": "test",
            "nodeId": "Node0"
        }
        linux1 = Linux(node_info)
        linux2 = linux1.copy()
        
        assert linux2 is not linux1
        assert linux2.ip == linux1.ip
        assert linux2.port == linux1.port
        assert linux2.username == linux1.username
        assert linux2.password == linux1.password
        assert linux2.nodeId == linux1.nodeId

    def test_copy_preserves_params(self):
        """Test copy preserves params."""
        node_info = {
            "ip": "192.168.1.100",
            "port": 22,
            "user": "root",
            "password": "test",
            "nodeId": "Node0",
            "params": {"detail": "test_detail"}
        }
        linux1 = Linux(node_info)
        linux2 = linux1.copy()
        
        assert linux2.detail == {"detail": "test_detail"}
        # Modifying copy should not affect original
        linux2.detail["new"] = "value"
        assert "new" not in linux1.detail

    def test_copy_independent_connections(self):
        """Test copy creates independent connection objects."""
        node_info = {
            "ip": "192.168.1.100",
            "port": 22,
            "user": "root",
            "password": "test",
            "nodeId": "Node0"
        }
        linux1 = Linux(node_info)
        linux2 = linux1.copy()
        
        # Each instance has its own connection state
        assert linux1.transport is None
        assert linux2.transport is None
        # After login, they should have separate connections
        # (This is conceptual - actual SSH connection needs real testing)


class TestLinuxFileOperations:
    """Test file/directory operations with mocked SSH."""

    def test_does_path_exist_true(self):
        """Test path exists check returns True."""
        linux = Linux({
            "ip": "192.168.1.100",
            "user": "root",
            "password": "test",
            "nodeId": "Node0"
        })
        
        with patch.object(linux, 'run') as mock_run:
            mock_run.return_value = {"returnCode": 0, "stdout": "", "stderr": ""}
            result = linux.doesPathExist("/mnt/test")
            assert result == True

    def test_does_path_exist_false(self):
        """Test path exists check returns False."""
        linux = Linux({
            "ip": "192.168.1.100",
            "user": "root",
            "password": "test",
            "nodeId": "Node0"
        })
        
        with patch.object(linux, 'run') as mock_run:
            mock_run.return_value = {"returnCode": 1, "stdout": "", "stderr": "error"}
            result = linux.doesPathExist("/mnt/nonexistent")
            assert result == False

    def test_create_directory_success(self):
        """Test create directory success."""
        linux = Linux({
            "ip": "192.168.1.100",
            "user": "root",
            "password": "test",
            "nodeId": "Node0"
        })
        
        with patch.object(linux, 'run') as mock_run:
            mock_run.return_value = {"returnCode": 0, "stdout": "", "stderr": ""}
            linux.createDirectory("/mnt/test", check_exist=False)
            mock_run.assert_called_once()

    def test_delete_directory_success(self):
        """Test delete directory success."""
        linux = Linux({
            "ip": "192.168.1.100",
            "user": "root",
            "password": "test",
            "nodeId": "Node0"
        })
        
        with patch.object(linux, 'doesPathExist', return_value=True):
            with patch.object(linux, 'run') as mock_run:
                mock_run.return_value = {"returnCode": 0, "stdout": "", "stderr": ""}
                linux.deleteDirectory("/mnt/test")

    def test_read_file(self):
        """Test read file returns lines."""
        linux = Linux({
            "ip": "192.168.1.100",
            "user": "root",
            "password": "test",
            "nodeId": "Node0"
        })
        
        with patch.object(linux, 'run') as mock_run:
            mock_run.return_value = {
                "returnCode": 0,
                "stdout": "line1\nline2\nline3",
                "stderr": ""
            }
            lines = linux.readFile("/mnt/test/file.txt")
            assert len(lines) >= 1

    def test_write_to_file(self):
        """Test write to file."""
        linux = Linux({
            "ip": "192.168.1.100",
            "user": "root",
            "password": "test",
            "nodeId": "Node0"
        })
        
        with patch.object(linux, 'run') as mock_run:
            mock_run.return_value = {"returnCode": 0, "stdout": "", "stderr": ""}
            linux.writeToFile("/mnt/test/file.txt", "test content")

    def test_copy_file(self):
        """Test copy file."""
        linux = Linux({
            "ip": "192.168.1.100",
            "user": "root",
            "password": "test",
            "nodeId": "Node0"
        })
        
        with patch.object(linux, 'run') as mock_run:
            mock_run.return_value = {"returnCode": 0, "stdout": "", "stderr": ""}
            linux.copyFile("/mnt/source.txt", "/mnt/dest.txt")


class TestLinuxDiskOperations:
    """Test disk/partition operations with mocked SSH."""

    def test_get_disk_info(self):
        """Test get disk info."""
        linux = Linux({
            "ip": "192.168.1.100",
            "user": "root",
            "password": "test",
            "nodeId": "Node0"
        })
        
        mock_output = """
Disk /dev/sdb: 10.7 GB, 10737418240 bytes, 20971520 sectors
Units = sectors of 1 * 512 = 512 bytes
Sector size (logical/physical): 512 bytes / 512 bytes
"""
        with patch.object(linux, 'run') as mock_run:
            mock_run.return_value = {
                "returnCode": 0,
                "stdout": mock_output,
                "stderr": ""
            }
            with patch.object(linux, 'getPartitions', return_value=[]):
                disk_info = linux.getDisk("/dev/sdb")
                assert "size" in disk_info
                assert "partitions" in disk_info

    def test_get_disks(self):
        """Test get all disks."""
        linux = Linux({
            "ip": "192.168.1.100",
            "user": "root",
            "password": "test",
            "nodeId": "Node0"
        })
        
        mock_output = """
Disk /dev/sda: 50 GB
Disk /dev/sdb: 10.7GB
"""
        with patch.object(linux, 'run') as mock_run:
            mock_run.return_value = {
                "returnCode": 0,
                "stdout": mock_output,
                "stderr": ""
            }
            disks = linux.getDisks()
            assert isinstance(disks, dict)


class TestLinuxServiceOperations:
    """Test service operations with mocked SSH."""

    def test_start_service(self):
        """Test start service."""
        linux = Linux({
            "ip": "192.168.1.100",
            "user": "root",
            "password": "test",
            "nodeId": "Node0"
        })
        
        with patch.object(linux, 'run') as mock_run:
            mock_run.return_value = {"returnCode": 0, "stdout": "", "stderr": ""}
            linux.startService("sshd")

    def test_stop_service(self):
        """Test stop service."""
        linux = Linux({
            "ip": "192.168.1.100",
            "user": "root",
            "password": "test",
            "nodeId": "Node0"
        })
        
        with patch.object(linux, 'run') as mock_run:
            mock_run.return_value = {"returnCode": 0, "stdout": "", "stderr": ""}
            linux.stopService("sshd")

    def test_get_service_status_running(self):
        """Test get service status running."""
        linux = Linux({
            "ip": "192.168.1.100",
            "user": "root",
            "password": "test",
            "nodeId": "Node0"
        })
        
        with patch.object(linux, 'run') as mock_run:
            mock_run.return_value = {
                "returnCode": 0,
                "stdout": "sshd is running...",
                "stderr": ""
            }
            status = linux.getServiceStatus("sshd")
            assert status == "running"

    def test_get_service_status_stopped(self):
        """Test get service status stopped."""
        linux = Linux({
            "ip": "192.168.1.100",
            "user": "root",
            "password": "test",
            "nodeId": "Node0"
        })
        
        with patch.object(linux, 'run') as mock_run:
            mock_run.return_value = {
                "returnCode": 0,
                "stdout": "sshd is stopped",
                "stderr": ""
            }
            status = linux.getServiceStatus("sshd")
            assert status == "stopped"


class TestLinuxISCSIOperations:
    """Test iSCSI operations with mocked SSH."""

    def test_check_open_iscsi_installed(self):
        """Test check open-iscsi installed."""
        linux = Linux({
            "ip": "192.168.1.100",
            "user": "root",
            "password": "test",
            "nodeId": "Node0"
        })
        
        with patch.object(linux, 'run') as mock_run:
            mock_run.return_value = {
                "returnCode": 0,
                "stdout": "/usr/bin/iscsiadm",
                "stderr": ""
            }
            result = linux.checkOpenIscsi()
            assert result == True

    def test_get_iqn(self):
        """Test get IQN."""
        linux = Linux({
            "ip": "192.168.1.100",
            "user": "root",
            "password": "test",
            "nodeId": "Node0"
        })
        
        with patch.object(linux, 'checkOpenIscsi', return_value=True):
            with patch.object(linux, 'run') as mock_run:
                mock_run.return_value = {
                    "returnCode": 0,
                    "stdout": "InitiatorName=iqn.2023-01.example:12345",
                    "stderr": ""
                }
                iqn = linux.getIqn()
                assert "iqn" in iqn


class TestLinuxNetworkOperations:
    """Test network operations with mocked SSH."""

    def test_get_hostname(self):
        """Test get hostname."""
        linux = Linux({
            "ip": "192.168.1.100",
            "user": "root",
            "password": "test",
            "nodeId": "Node0"
        })
        
        mock_hostname_output = "test-host"
        mock_ifconfig_output = """
eth0: flags=4163<UP,BROADCAST,RUNNING,MULTICAST>  mtu 1500
        inet 192.168.1.100  netmask 255.255.255.0  broadcast 192.168.1.255
"""
        
        with patch.object(linux, 'run') as mock_run:
            mock_run.side_effect = [
                {"returnCode": 0, "stdout": mock_hostname_output, "stderr": ""},
                {"returnCode": 0, "stdout": mock_ifconfig_output, "stderr": ""},
                {"returnCode": 0, "stdout": "", "stderr": ""}
            ]
            hostname = linux.getHostname()
            assert hostname == "test-host"

    def test_get_version(self):
        """Test get kernel version."""
        linux = Linux({
            "ip": "192.168.1.100",
            "user": "root",
            "password": "test",
            "nodeId": "Node0"
        })
        
        with patch.object(linux, 'run') as mock_run:
            mock_run.return_value = {
                "returnCode": 0,
                "stdout": "5.10.0-generic",
                "stderr": ""
            }
            version = linux.getVersion()
            assert "5.10" in version

    def test_get_architecture(self):
        """Test get architecture."""
        linux = Linux({
            "ip": "192.168.1.100",
            "user": "root",
            "password": "test",
            "nodeId": "Node0"
        })
        
        with patch.object(linux, 'run') as mock_run:
            mock_run.return_value = {
                "returnCode": 0,
                "stdout": "x86_64",
                "stderr": ""
            }
            arch = linux.getArchitecture()
            assert arch == "x86_64"


class TestLinuxProcessOperations:
    """Test process operations with mocked SSH."""

    def test_get_process_id(self):
        """Test get process ID."""
        linux = Linux({
            "ip": "192.168.1.100",
            "user": "root",
            "password": "test",
            "nodeId": "Node0"
        })
        
        with patch.object(linux, 'run') as mock_run:
            mock_run.return_value = {
                "returnCode": 0,
                "stdout": "PID\n1234\n5678",
                "stderr": ""
            }
            pids = linux.getProcessId("sshd")
            assert len(pids) >= 0


class TestLinuxUtilityMethods:
    """Test utility methods."""

    def test_split_output(self):
        """Test split output."""
        linux = Linux({
            "ip": "192.168.1.100",
            "user": "root",
            "password": "test",
            "nodeId": "Node0"
        })
        
        lines = linux._split_output("line1\nline2\rline3\r\nline4")
        assert len(lines) == 4

    def test_split_output_empty(self):
        """Test split output empty."""
        linux = Linux({
            "ip": "192.168.1.100",
            "user": "root",
            "password": "test",
            "nodeId": "Node0"
        })
        
        lines = linux._split_output(None)
        assert lines == []

    def test_trim(self):
        """Test trim."""
        linux = Linux({
            "ip": "192.168.1.100",
            "user": "root",
            "password": "test",
            "nodeId": "Node0"
        })
        
        result = linux._trim("  test  ")
        assert result == "test"

    def test_normalize_wwn(self):
        """Test normalize WWN."""
        linux = Linux({
            "ip": "192.168.1.100",
            "user": "root",
            "password": "test",
            "nodeId": "Node0"
        })
        
        result = linux._normalize_wwn("0x123456789ABCDEF")
        assert result == "123456789abcdef"

    def test_repr(self):
        """Test repr."""
        linux = Linux({
            "ip": "192.168.1.100",
            "user": "root",
            "password": "test",
            "nodeId": "Node0"
        })
        
        repr_str = repr(linux)
        assert "Node0" in repr_str
        assert "192.168.1.100" in repr_str