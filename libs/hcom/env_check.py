"""Env check AW migrated from legency/testcase/ubscomm/hcom/lib/common/env_check_aw.py"""

import os
import re
import logging

from libs.hcom.node_run import node_run

logger = logging.getLogger(__name__)


def check_network_between_nodes(nodes):
    """Check network connectivity between nodes."""
    if len(nodes) < 2:
        return True
    for idx in range(len(nodes) - 1):
        node2_ip = nodes[idx + 1].localIP
        res = nodes[idx].run({'command': [f"ping {node2_ip} -c 5 -W 5"], 'waitstr': '#'})
        if res.get('rc') != 0:
            logger.error(f"{res.get('stderr')}")
            return False
    logger.info(f"All {len(nodes)} nodes can ping, network OK")
    return True


def get_rdma_ip(server, client):
    """Get RDMA IP from server and verify connectivity to client."""
    res = server.run({
        'command': [f"for nic in $(rdma link|grep ACTIVE |awk '{{print $NF}}'); do ifconfig $nic|grep "
                    f"-w inet|awk {{'print  $2'}} |grep -oP '(\d+\.){{3}}\d+'||true;done"],
        'waitstr': '@#>'
    })
    output = res.get('stdout')
    rdma_ip = []
    if output is None:
        logger.error(f'{res} no RDMA IP found!')
        return None
    li = output.split("\r\n")
    logger.info(f'rdma ip: {li}')
    for out in li:
        match = re.match(r'(\d+\.){3}\d+', out)
        if match is not None:
            logger.info(f'Got RDMA IP: {match.group()}')
            rdma_ip.append(match.group())
    if len(rdma_ip) == 0:
        logger.error(f'{res} no RDMA IP found!')
        return None
    for ip in rdma_ip:
        res = client.run({'command': [f"ping {ip} -c 5 -W 5"], 'waitstr': '@#>'})
        if res.get('rc') == 0:
            logger.info(f"{ip} can ping, network OK")
            return ip
    return None


def get_rdma_ip_list(node1, node2):
    """Get all RDMA IPs from both nodes and verify connectivity."""
    cmd = [f"for nic in $(rdma link|grep ACTIVE|awk '{{print $NF}}'); do ifconfig $nic|grep -w inet|awk '{{print $2}}'|"
           f"grep -oP '(\d+\.){{3}}\d+'||true;done"]
    res1 = node_run(node=node1, command=cmd).get('stdout')
    res2 = node_run(node=node2, command=cmd).get('stdout')
    if res1 is None:
        logger.error(f'Node {node1.localIP} no RDMA IP found!')
        return None
    if res2 is None:
        logger.error(f'Node {node2.localIP} no RDMA IP found!')
        return None
    str_list1, str_list2 = res1.split("\r\n"), res2.split("\r\n")
    logger.info(f"{node1.localIP} ip list: {str_list1}, {node2.localIP} ip list: {str_list2}")

    rdma_ip1, rdma_ip2 = [], []
    [rdma_ip1.append(match.group()) for s in str_list1 if (match := re.match(r'(\d+\.){3}\d+', s)) is not None]
    if len(rdma_ip1) == 0:
        logger.error(f'Node {node1.localIP} no RDMA IP found!')
        return None
    [rdma_ip2.append(match.group()) for s in str_list2 if (match := re.match(r'(\d+\.){3}\d+', s)) is not None]
    if len(rdma_ip2) == 0:
        logger.error(f'Node {node2.localIP} no RDMA IP found!')
        return None
    logger.info(f'{node1.localIP} RDMA IPs: {rdma_ip1}')
    logger.info(f'{node2.localIP} RDMA IPs: {rdma_ip2}')

    rdma_ip = [[], []]
    for ip1 in rdma_ip1:
        for ip2 in rdma_ip2:
            res = node2.run({'command': [f"ping -I {ip2} {ip1} -c 5 -W 5"], 'waitstr': '@#>'})
            if res.get('rc') == 0:
                logger.info(f"{ip1} {ip2} can ping, network OK")
                rdma_ip[0].append(ip1)
                rdma_ip[1].append(ip2)
    if len(rdma_ip[0]) == 0 or len(rdma_ip[1]) == 0:
        return None
    else:
        logger.info(f'RDMA IP list: {rdma_ip}')
        return rdma_ip


def get_ub_ip(node1, node2):
    """Get UB IP from node1 and verify connectivity to node2."""
    res = node1.run({
        'command': [f"for nic in $(urma_admin show|grep -P 'eid\d+'|awk '{{print $NF}}'); do ifconfig $nic|grep -w "
                    f"inet|awk '{{print $2}}'|grep -oP '(\d+\.){{3}}\d+'||true; done"],
        'waitstr': '@#>'
    })
    output = res.get('stdout')
    ub_ip = []
    if output is None:
        logger.error(f'{res} no UB IP found!')
        return None
    li = output.split("\r\n")
    logger.info(f'ub ip: {li}')
    for out in li:
        match = re.match(r'(\d+\.){3}\d+', out)
        if match is not None:
            logger.info(f'Got UB IP: {match.group()}')
            ub_ip.append(match.group())
    if len(ub_ip) == 0:
        logger.error(f'{res} no UB IP found!')
        return None
    for ip in ub_ip:
        res = node2.run({'command': [f"ping {ip} -c 5 -W 5"], 'waitstr': '@#>'})
        if res.get('rc') == 0:
            logger.info(f"{ip} can ping, network OK")
            return ip
    return None


def check_python_fixed_version(nodes, major_version, minor_version):
    """Check Python version on all nodes."""
    expected_version = f"{major_version}.{minor_version}"
    for node in nodes:
        res = node.run({'command': [f"python -V"], 'waitstr': '@#>'})
        if res.get('rc') != 0:
            logger.error(f"{res.get('stderr')}")
            return False
        python_version = res.get('stdout')
        if re.match(r'Python {}\.'.format(expected_version), python_version) is None:
            logger.error("Python version mismatch")
            return False
        logger.info(f"{node.localIP} Python version: {python_version}")
    return True


def env_check_between_hccs_nodes(nodes, check_urma=True):
    """Check HCCS environment between nodes."""
    node1IP = nodes[0].localIP
    node2IP = nodes[1].localIP
    logger.debug(f"node1 {node1IP} node2 {node2IP}")

    res = nodes[0].run({'command': [f"ping {node2IP} -c 5 -W 5"], 'waitstr': '#'})
    if res.get('rc') == 0:
        logger.info(f"{node1IP} {node2IP} can ping, network OK")
    else:
        logger.error(f"{res.get('stderr')}")
        return False

    for node in nodes:
        res = node.run({'command': ["lsmod | grep ub"], 'waitstr': '#'})
        if res.get('rc') != 0 or res.get('stdout').find('uboib') == -1 \
                or res.get('stdout').find('uburma') == -1 \
                or res.get('stdout').find('ubcore') == -1:
            logger.error(f"{node.localIP} : uboib/uburma/ubcore modules not loaded")
            return False
    logger.info("All nodes loaded uboib/uburma/ubcore modules")

    for node in nodes:
        res = node.run({'command': ["ll /dev/ | grep obmm"], 'waitstr': '#'})
        if res.get('rc') != 0:
            logger.error(f"{node.localIP} : obmm memory not allocated")
            return False
        if check_urma is True:
            for i in range(1, 17):
                if res.get('stdout').find(f'shmdev{i}') == -1:
                    logger.error(f"{node.localIP} : obmm memory not allocated")
                    return False
    logger.info("All nodes allocated obmm memory")
    return True


def prepare_hccs_testing_tools(nodes):
    """Upload and compile testing tools to nodes."""
    remote_dir = "/home/TurboComm/automation"
    expect = "All test tools have been compiled successfully!"
    res = nodes[0].run({'command': [f"cat {remote_dir}/done"]})
    if res.get("rc") == 0 and res.get("stdout").find(expect) != -1:
        logger.info("Testing tools already uploaded")
        return

    tmp_dir = os.path.abspath(__file__).split('lib')[0]
    local_dir = os.path.join(tmp_dir, "resource")
    os.chdir(local_dir)
    logger.info(f"Compressing testing tools for upload")
    tmp_file_name = 'testing_tools.tar.gz'
    os.system('rm -f {}'.format(tmp_file_name))
    os.system('tar -zcf {} testing_tools/'.format(tmp_file_name))
    for node in nodes:
        logger.info(f"Uploading tools to {node.localIP}")
        node.run({'command': [f"mkdir -p {remote_dir}"]})
        node.putFile({
            "source_file": os.path.join(local_dir, tmp_file_name),
            "destination_file": "{}/{}".format(remote_dir, tmp_file_name)
        })
        logger.info("Compiling tools")
        cmds = [
            f"tar -zxvf {tmp_file_name} > log.log 2>&1;",
            f"mv {remote_dir}/testing_tools/* {remote_dir};",
            f"rm -rf {remote_dir}/testing_tools*;",
            'find ./ -name "*.sh"|xargs dos2unix &>> log.log;',
            "sh build_all.sh;",
            "cat done"
        ]
        res = node.run({'command': cmds, 'directory': remote_dir})
        assert int(res.get("rc")) == 0
        assert res.get("stdout").find(expect) != -1


def create_consolidated_device(nodes):
    """Create consolidated bonding device if not exists."""
    eid = 0
    for node in nodes:
        eid = eid + 1
        logger.info(f"Checking {node.localIP} for bonding device")
        res = node.run({'command': ["urma_admin show"]})
        expect = "bond_dev"
        if res.get("rc") == 0 and res.get("stdout").find(expect) != -1:
            logger.info(f"{node.localIP} has bonding device")
            continue

        logger.info(f"{node.localIP} creating bonding device")
        cmds = [f"ubagg_cli -t add_dev -m bond_dev -s udma0 -e 0000:0000:0000:0000:0000:ffff:0303:030{eid}"]
        node.run({'command': cmds})


def check_pip(nodes, ip):
    """Check URMA pathway with urma_perftest_ubc."""
    nodes[0].run({'command': ["chmod +x /ko/ub_pkg/tool/urma_perftest_ubc"]})
    nodes[1].run({'command': ["chmod +x /ko/ub_pkg/tool/urma_perftest_ubc"]})

    cmds_0 = [f"/ko/ub_pkg/tool/urma_perftest_ubc write_bw -d bond_dev -z -Q1 -n 10"]
    res_s = nodes[0].run({'command': cmds_0})
    cmds_1 = [f"/ko/ub_pkg/tool/urma_perftest_ubc write_bw -d bond_dev -z -Q1 -S {ip} -n 10"]
    res_c = nodes[1].run({'command': cmds_1})

    expect = "65536"
    if res_c.get("rc") == 0 and res_c.get("stdout").find(expect) != -1:
        logger.info("Pathway OK")
        return True

    logger.error("URMA pathway not OK")
    return False


def get_eid(server, client, ubep_dev):
    """Get URMA endpoint EID from server and client."""
    res_s = server.run({
        'command': [f"urma_admin show|grep {ubep_dev}|awk '{{print $5}}'"],
        'waitstr': '@#>'
    })
    server_ip = res_s.get('stdout')
    if server_ip is None:
        logger.error(f'server:{res_s} no EID found!')
        return None
    res_c = client.run({
        'command': [f"urma_admin show|grep {ubep_dev}|awk '{{print $5}}'"],
        'waitstr': '@#>'
    })
    client_ip = res_c.get('stdout')
    if client_ip is None:
        logger.error(f'client:{res_c} no EID found!')
        return None
    return server_ip.split("\r\n")[0], client_ip.split("\r\n")[0]