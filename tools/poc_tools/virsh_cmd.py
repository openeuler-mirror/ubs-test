import asyncio
import subprocess

from poc_tools.common.config import CONF
from poc_tools.common.log import LOG
from poc_tools.common.utils import send_pipe_scripts

TIMEOUT = 3600


async def start_vm(vm_name: str):
    timeout = CONF.get("task", {}).get("virsh_start_timeout", TIMEOUT)
    await send_pipe_scripts([["virsh", "start", vm_name]], timeout=timeout)


async def define_vm_through_xml(xml_file_path: str, uuid: str):
    timeout = CONF.get("task", {}).get("virsh_define_timeout", TIMEOUT)
    scripts = ["virsh", "define", xml_file_path]
    try:
        result = await asyncio.to_thread(
            subprocess.run, scripts,
            shell=False, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=timeout, text=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        LOG.error(f"Create vm failed, the vm uuid is {uuid}, error: {e.stderr}")
        raise


async def virsh_undefine_vm(vm_name: str):
    LOG.info(f"Start to undefined vm {vm_name}.")
    await send_pipe_scripts([["virsh", "undefine", vm_name, "--nvram"]])


async def virsh_destroy_vm(vm_name: str):
    LOG.info(f"Start to destroy vm {vm_name}.")
    await send_pipe_scripts([["virsh", "destroy", vm_name]])
