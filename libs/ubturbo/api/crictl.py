from libs.ubturbo.common import basic


def get_all_containers(node):
    """
    获取所有容器id，返回列表
    """
    res = basic.run(node, 'crictl ps -aq')
    if res.rc != 0:
        raise RuntimeError(f"执行crictl ps失败：{res.stdout}")
    container_ids = res.stdout.strip().splitlines()
    return container_ids


def get_all_pods(node):
    """
    获取所有pod id，返回列表
    """
    res = basic.run(node, 'crictl pods -q')
    if res.rc != 0:
        raise RuntimeError(f"执行crictl pods失败：{res.stdout}")
    pod_ids = res.stdout.strip().splitlines()
    return pod_ids


def remove_container(node, container_id):
    res = basic.run(node, f'crictl rm -f {container_id}')
    if res.rc != 0:
        raise RuntimeError(f"容器删除失败：{res.stdout}")


def remove_pod(node, pod_id):
    res = basic.run(node, f'crictl rmp -f {pod_id}')
    if res.rc != 0:
        raise RuntimeError(f"POD删除失败：{res.stdout}")


def remove_all_containers(node):
    container_ids = get_all_containers(node)
    for container_id in container_ids:
        remove_container(node, container_id)


def remove_all_pods(node):
    pod_ids = get_all_pods(node)
    for pod_id in pod_ids:
        remove_pod(node, pod_id)
