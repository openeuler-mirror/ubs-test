import asyncio
import subprocess
from typing import Callable, List

from poc_tools.common.config import CONF
from poc_tools.common.log import LOG

BASH_TIMEOUT = 10


async def retry(func: Callable, *args, **kwargs):
    max_retry = kwargs.get("max_retry", CONF.get("default", {}).get("max_retry", 3))
    retry_interval = kwargs.get("retry_interval", CONF.get("default", {}).get("retry_interval", 10))
    retry_time = 1
    kwargs.pop("max_retry", None)
    kwargs.pop("retry_interval", None)
    while retry_time <= max_retry:
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            LOG.warning(f"Execute {func}: {e}, retry: no.{retry_time}.")
            retry_time += 1
            await asyncio.sleep(retry_interval)
    raise Exception(f"Max retry exceeded, execute {func.__name__} failed!")


async def send_pipe_scripts(scripts_list: List[List[str]], timeout: int = None, check=True):
    try:
        if timeout is None:
            timeout = CONF.get("default", {}).get("timeout", BASH_TIMEOUT)

        result = ""
        for scripts in scripts_list:
            result = subprocess.run(scripts, input=result, shell=False, check=check, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, timeout=timeout, text=True).stdout.strip()
        return result
    except subprocess.CalledProcessError as e:
        LOG.error(f"Execute script failed, error: {e.stderr}.")
        raise
    except subprocess.TimeoutExpired as e:
        LOG.error(f"Execute script failed, error: {e.stderr}.")
        raise
