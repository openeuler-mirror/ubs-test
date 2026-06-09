"""K8s API utilities migrated from legency/testcase/ubscomm/ubsocket/lib/api/k8s_api.py"""

import logging

logger = logging.getLogger(__name__)


def get_exec_cmd(container_name, cmd):
    """Get kubectl exec command string."""
    return f"kubectl exec -it -n default {container_name} -- bash -c '{cmd}'"


def exec_cmd_with_concole(node, containerID, cmd):
    """Execute command in container console."""
    pass


def get_pods_wide(node, grep="default"):
    """Get pods info with wide output."""
    grep_cmd = ""
    if '|' in grep:
        pods = grep.split("|")
        for pod in pods:
            grep_cmd = grep_cmd + "|| $2==\"" + pod + "\""
    else:
        grep_cmd = grep
    ret = node.run({'command': [f"kubectl get pods -A -o wide |awk 'NR==1 {grep_cmd}'"], "timeout": 10})
    return ret.get("stdout").split("\r\nroot@#>")[0]


def create_container(node, yaml_name):
    """Create container from yaml file."""
    ret = node.run({'command': [f"kubectl apply -f {yaml_name}"], "timeout": 10})
    return ret.get("stdout")


def delete_container(node, container_name):
    """Delete container by name."""
    ret = node.run({'command': [f"kubectl delete pod {container_name}"], "timeout": 10})
    return ret.get("stdout")


def delete_all_pods(node, pod="default"):
    """Delete all pods in namespace."""
    ret = node.run({'command': [f"kubectl delete pods --all --grace-period=0 --force -n {pod}"], "timeout": 10})
    return ret.get("stdout")


def get_container_id(node, container_name):
    """Get container ID from pod description."""
    ret = node.run({'command': [f"kubectl describe pod {container_name} | awk '/Container ID:/{{print $3}}' | cut -d'/' -f3"], "timeout": 10})
    return ret.get("stdout").split("\r\n")[0]


def install_numactl(node, container_name):
    """Install numactl in container."""
    node.run({'command': [f"kubectl exec -it -n default {container_name} -- bash -c 'yum install numactl -y'"], "timeout": 10})