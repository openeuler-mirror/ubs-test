from typing import List, Optional


class WrapperNode:

    def __init__(self, hostname, ssh_connect):
        self.hostname = hostname
        self.ssh_connect = ssh_connect
        self.tags = []

    def add_tag(self, tag: str):
        if tag not in self.tags:
            self.tags.append(tag)


class ResourceTopo:

    def __init__(self, nodes, vms):
        self.nodes = nodes
        self.vms = vms

    @classmethod
    def from_dict(cls, data):
        nodes = []
        _nodes = data['nodes']
        for node in _nodes:
            nodes.append(NodeResource.from_dict(node))

        vms = []
        _vms = data['vms']
        for vm in _vms:
            vms.append(VMResource.from_dict(vm))
        return cls(nodes, vms)


class NodeResource:

    def __init__(self, name, role, huge_page, numa):
        self.name = name
        self.role = role
        self.hugePage = huge_page
        self.numa = numa
        self.host = None
        self.ssh_node = None

    @classmethod
    def from_dict(cls, data):
        if 'numa' in data.keys():
            numa = data['numa']
        else:
            numa = 0
        return cls(data['name'], data['role'], data['hugePage'], numa)


class VMResource:
    instance = None
    ssh_node = None

    def __init__(self, name, image, ram, node, removable, cpu=16, ub_instance=False, enable_remote_memory='False',
                 max_remote_memory_ratio=0, enable_remote_create='False', remote_create_memory_ratio=0, dpu=False, ip='0.0.0.0', core_binding=True):
        self.name = name
        self.image = image
        self.ram = ram
        self.node = node
        self.removable = removable
        self.cpu = cpu
        self.ub_instance = ub_instance
        self.enable_remote_memory = enable_remote_memory
        self.max_remote_memory_ratio = max_remote_memory_ratio
        self.enable_remote_create = enable_remote_create
        self.remote_create_memory_ratio = remote_create_memory_ratio
        self.dpu = dpu
        self.ip = ip
        self.core_binding = core_binding

    @classmethod
    def from_dict(cls, data):
        params = {'node': data.get('node', None),
                  'cpu': data.get('cpu', 16),
                  'ub_instance': data.get('ub_instance', False),
                  'enable_remote_memory': data.get('enable_remote_memory', ''),
                  'max_remote_memory_ratio': data.get('max_remote_memory_ratio', 25),
                  'enable_remote_create': data.get('enable_remote_create', ''),
                  'remote_create_memory_ratio': data.get('remote_create_memory_ratio', 0),
                  'dpu': data.get('dpu', False),
                  'ip': data.get('ip', '0.0.0.0'),
                  'core_binding': data.get('core_binding', True)}
        return cls(
            name=data['name'],
            image=data['image'],
            ram=data['ram'],
            removable=data['removable'],
            **params  # 解包参数
        )


class ResourceItem:
    properties = {}

    def __init__(self, resType, resId, name, properties):
        self.type = resType
        self.id = resId
        self.name = name
        self.properties = properties


class Volume(ResourceItem):
    image = None
    status = None

    def __init__(self, resType, resId, name, properties, status):
        super().__init__(resType, resId, name, properties)
        self.status = status
