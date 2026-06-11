"""Environment configuration management for legacy test framework compatibility.

This module provides functions for reading environment parameters and 
test resource configurations, compatible with legacy Common_AW.get_env_params().
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)

# Default configuration path (relative to project root)
DEFAULT_CONFIG_DIR = "conf"
DEFAULT_CONFIG_FILE = "env.json"


def get_default_config_path() -> Path:
    """Get default resource configuration path.
    
    Returns the path to {PROJECT_ROOT}/conf/env.json.
    
    Returns:
        Path object pointing to default config file
    """
    # Find project root by looking for pyproject.toml or setup.py
    current = Path.cwd()
    
    for parent in [current] + list(current.parents):
        if (parent / "pyproject.toml").exists() or (parent / "setup.py").exists():
            return parent / DEFAULT_CONFIG_DIR / DEFAULT_CONFIG_FILE
    
    # Fallback: use current directory
    return current / DEFAULT_CONFIG_DIR / DEFAULT_CONFIG_FILE


def get_env_params(node: Any, param_name: Optional[str] = None) -> Any:
    """Get environment parameter value from node's env.ini file.
    
    Legacy method: Common_AW.get_env_params(node, "param_name")
    
    Args:
        node: Node object with run() method
        param_name: Parameter name to retrieve (optional, returns all if None)
        
    Returns:
        Parameter value string, or dict of all parameters if param_name is None
        
    Example:
        rack_path = get_env_params(node, "rack_path")
        # Returns: "/usr/local/softbus/ctrlbus"
        
        all_params = get_env_params(node)
        # Returns: {"rack_path": "...", "log_path": "...", ...}
    """
    env_file = "/home/autotest/env.ini"
    
    if not hasattr(node, "run"):
        logger.warning(f"Node does not have run method")
        return "" if param_name else {}
    
    result = node.run({"command": [f"cat {env_file}"], "timeout": 10})
    env_content = result.get("stdout", "")
    
    if not env_content:
        logger.error(f"Failed to read {env_file}")
        return "" if param_name else {}
    
    env_params = {}
    lines = env_content.split("\n")
    
    for line in lines:
        if line.startswith("#") or not line.strip():
            continue
        if "=" in line:
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            if "root@#>" in value:
                value = value.split("root@#>")[0]
            env_params[key] = value
    
    if param_name:
        return env_params.get(param_name, "")
    return env_params


def load_resource_config(config_path: str) -> Dict[str, Any]:
    """Load test resource configuration from JSON or XML file.
    
    Legacy pattern: resource = Resource.load(test_bed.xml)
    
    Supports:
    - JSON format (.json)
    - XML format (test_bed.xml, similar to legacy format)
    
    Args:
        config_path: Path to configuration file
        
    Returns:
        Resource dictionary with hosts, devices, global sections
        
    Example JSON format:
        {
            "hosts": {
                "1": {
                    "ip": "192.168.1.1",
                    "port": 22,
                    "user": "root",
                    "password": "...",
                    "params": {"key1": "value1", "key2": "value2"}
                },
                "2": {"ip": "192.168.1.2", "port": 22, "user": "root", "password": "..."}
            },
            "devices": {},
            "global": {"testbed_name": "testbed1"}
        }
        
    Example XML format (legacy test_bed.xml):
        <testbed>
            <host id="1" ip="192.168.1.1" port="22" user="root" password="...">
                <params>
                    <key1>value1</key1>
                    <key2>value2</key2>
                </params>
            </host>
            <host id="2" ip="192.168.1.2" port="22" user="root" password="..."/>
        </testbed>
    """
    config_file = Path(config_path)
    
    if not config_file.exists():
        logger.error(f"Config file not found: {config_path}")
        return {"hosts": {}, "devices": {}, "global": {}}
    
    if config_file.suffix == ".json":
        return _load_json_config(config_file)
    elif config_file.suffix == ".xml":
        return _load_xml_config(config_file)
    else:
        logger.warning(f"Unknown config format: {config_file.suffix}, trying JSON")
        try:
            return _load_json_config(config_file)
        except:
            return {"hosts": {}, "devices": {}, "global": {}}


def _load_json_config(config_file: Path) -> Dict[str, Any]:
    """Load JSON format resource configuration."""
    try:
        with open(config_file) as f:
            config = json.load(f)
        logger.info(f"Loaded JSON config from {config_file}")
        return config
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON config: {e}")
        return {"hosts": {}, "devices": {}, "global": {}}


def _load_xml_config(config_file: Path) -> Dict[str, Any]:
    """Load XML format resource configuration (legacy test_bed.xml)."""
    try:
        tree = ET.parse(config_file)
        root = tree.getroot()
        
        config = {"hosts": {}, "devices": {}, "global": {}}
        
        for host_elem in root.findall(".//host") + root.findall(".//Host"):
            host_id = host_elem.get("id", host_elem.get("ID", ""))
            port_str = host_elem.get("port", host_elem.get("PORT", "22"))
            try:
                port = int(port_str)
            except ValueError:
                port = 22
            host_info = {
                "ip": host_elem.get("ip", host_elem.get("IP", "")),
                "port": port,
                "user": host_elem.get("user", host_elem.get("USER", "root")),
                "password": host_elem.get("password", host_elem.get("PASSWORD", "")),
                "localIP": host_elem.get("localIP", ""),
                "nodeId": host_id,
            }
            
            # Parse params sub-element if present
            params_elem = host_elem.find("params") or host_elem.find("Params")
            if params_elem is not None:
                params = {}
                for child in params_elem:
                    # Handle nested elements as key-value pairs
                    key = child.tag
                    value = child.text or ""
                    params[key] = value
                host_info["params"] = params
            
            config["hosts"][host_id] = host_info
        
        for device_elem in root.findall(".//device") + root.findall(".//Device"):
            device_id = device_elem.get("id", device_elem.get("ID", ""))
            device_info = {
                "type": device_elem.get("type", ""),
                "name": device_elem.get("name", ""),
            }
            config["devices"][device_id] = device_info
        
        global_elem = root.find(".//global") or root.find(".//Global")
        if global_elem:
            for child in global_elem:
                config["global"][child.tag] = child.text
        
        logger.info(f"Loaded XML config from {config_file}, hosts: {len(config['hosts'])}")
        return config
        
    except ET.ParseError as e:
        logger.error(f"Failed to parse XML config: {e}")
        return {"hosts": {}, "devices": {}, "global": {}}


def get_path_common() -> Dict[str, str]:
    """Get common path configuration.
    
    Legacy pattern: Path_Common from lib.Common.RackControl.Path_Common
    
    Returns:
        Dictionary of common paths used in test cases
        
    Example:
        paths = get_path_common()
        test_file_path = paths["test_file_path"]
        # Returns: "/home/autotest"
    """
    return {
        "test_file_path": "/home/autotest",
        "conf_path": "/usr/local/softbus/ctrlbus/conf",
        "packages_path": "/home/autotest/packages",
        "sdk_path": "/home/autotest/sdk",
        "log_path": "/var/log/scbus",
        "rpm_path": "/usr/local/softbus/ctrlbus",
        "cli_path": "/usr/local/softbus/ctrlbus-cli",
        "run_path": "/run/ubm",
        "cert_lib_path": "/usr/local/softbus/ctrlbus/lib",
        "service_conf_path": "/etc/ubse",
        "ubse_path": "/opt/install/package",
        "dcat_path": "/usr/local/dcat",
    }


def check_autotest_mkdir(node: Any) -> bool:
    """Check and create /home/autotest directory on node.
    
    Legacy method: Common_AW.check_autotest_mkdir(node)
    
    Args:
        node: Node object with run() method
        
    Returns:
        True if directory exists or created successfully
    """
    if not hasattr(node, "run"):
        return False
    
    result = node.run({"command": ["ls -la /home | grep autotest"]})
    stdout = ""
    if result:
        stdout = result.get("stdout") or ""
    
    if "autotest" not in stdout:
        node.run({"command": ["mkdir -p /home/autotest"]})
        logger.info("Created /home/autotest directory")
    
    return True


def upload_env_file(node: Any, source_env_file: Optional[str] = None) -> bool:
    """Upload env.ini file to node.
    
    Legacy method: Common_AW.upload_env_file(node)
    
    Args:
        node: Node object with run() and putFile() methods
        source_env_file: Source env.ini path (optional)
        
    Returns:
        True if upload successful
    """
    if not hasattr(node, "run") or not hasattr(node, "putFile"):
        logger.warning("Node does not have required methods")
        return False
    
    env_file_path = "/home/autotest/env.ini"
    
    result = node.run({"command": [f"ls /home/autotest | grep env"]})
    stdout = ""
    if result:
        stdout = result.get("stdout") or ""

    
    if "env.ini" not in stdout:
        if source_env_file:
            file_dict = {
                "source_file": source_env_file,
                "destination_file": env_file_path
            }
        else:
            return True
        
        if hasattr(node, "putFile"):
            node.putFile(file_dict)
            logger.info(f"Uploaded env.ini to {env_file_path}")
    
    return True