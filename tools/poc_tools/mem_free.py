# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2025-2025. All rights reserved.
import asyncio
from typing import Callable, Dict, Any

from ubse.ubs_virt_agent_fragmentation import (
    ubs_mem_borrow,
    ubs_mem_return,
    ubs_task_result_query
)
from ubse.ubs_engine_log import ubs_engine_log_callback_register
from ubse.ubs_virt_agent_log import ubs_virt_agent_log_callback_register

from poc_tools.common.constant import AsyncTaskStatus
from poc_tools.common.log import LOG
from poc_tools.common.config import CONF

DEFAULT_MAX_RETRY = 360
DEFAULT_RETRY_INTERVAL = 10
MAX_TASK_ID_LENGTH = 32

ubs_engine_log_callback_register(lambda level, msg: None)
ubs_virt_agent_log_callback_register(lambda level, msg: None)


class AsyncTaskManager:

    @staticmethod
    async def async_retry_query_task(task_id: str, **kwargs):
        # Get configuration from CONF, use module-level constants as default
        conf_max_retry = CONF.get("default", {}).get("async_max_retry", DEFAULT_MAX_RETRY)
        conf_retry_interval = CONF.get("default", {}).get("async_retry_interval", DEFAULT_RETRY_INTERVAL)

        max_retry = kwargs.get("async_max_retry", conf_max_retry)
        retry_interval = kwargs.get("async_retry_interval", conf_retry_interval)
        retry_time = 0

        while retry_time <= max_retry:
            retry_time += 1
            # Asynchronize synchronous interface to avoid event loop blocking
            _, interface_result = await asyncio.to_thread(ubs_task_result_query, task_id)
            # Status judgment (corresponding to AsyncTaskStatus enumeration)
            interface_status = interface_result.status

            match interface_status:
                case AsyncTaskStatus.RUNNING:
                    await asyncio.sleep(retry_interval)
                    continue
                case AsyncTaskStatus.SUCCESS:
                    LOG.info(f"Task {task_id} execute successfully.")
                    return interface_result
                case AsyncTaskStatus.FAILED:
                    raise Exception(
                        f"Task {task_id} execute failed (retry {retry_time}/{max_retry}), result: {interface_result}.")
                case _:  # else
                    raise Exception(
                        f"Task {task_id} got unknown status {interface_status} (retry {retry_time}/{max_retry}).")

            # Increment retry count and sleep before next polling if task not completed
        # Throw exception when maximum retry count is reached
        raise Exception(f"Max retry exceeded, task: {task_id} execute failed!")

    # execute_async_task
    async def execute_async_task(self, async_task: Callable, params: Dict[str, Any] = None) -> None:
        params_dict = {"is_async": True}
        if params:
            params_dict.update({"param": params})
        _, task_id = await asyncio.to_thread(async_task, **params_dict)
        if len(task_id) > MAX_TASK_ID_LENGTH:
            raise Exception(f"Illegal task_id: {task_id}.")
        return await self.async_retry_query_task(task_id)


async_task_manager = AsyncTaskManager()


async def mem_free():
    LOG.info("Execute mem free (async only).")

    # Submit task and start polling
    try:
        await async_task_manager.execute_async_task(ubs_mem_return)
        LOG.info(f"Async mem free task completed successfully.")

    # Catch exceptions
    except Exception as e:
        LOG.error(f"Failed to execute mem free (async only), error: {e}.")
        raise