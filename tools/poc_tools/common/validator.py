# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2025-2025. All rights reserved.
import os
from typing import List
from ubse.ubs_virt_agent_case_conf import ubs_case_conf_info

from poc_tools.common.config import CONF
from poc_tools.common.log import LOG

FRAGMENTED_SCENE_RATIO = 1


async def validate_config() -> None:
    try:
        await check_case_conf()
        image_base_path = CONF["default"]["image_base_path"]
        if not isinstance(image_base_path, str) or not image_base_path.strip():
            raise TypeError(f"Image base path must be a string, got {type(image_base_path)}.")
        if not os.path.exists(image_base_path):
            raise FileNotFoundError(f"Error path: image_base_path='{image_base_path}' not exist.")
        if not os.path.isdir(image_base_path):
            raise TypeError(f"Error dir: image_base_path='{image_base_path}' is not a dir.")
        if not os.access(image_base_path, os.X_OK):
            raise PermissionError(f"Permission error：no permission to read image_base_path: '{image_base_path}.")

        xml_path = CONF["default"]["xml_path"]
        if not isinstance(xml_path, str) or not xml_path.strip():
            raise TypeError(f"Xml path must be a string, got {type(xml_path)}.")
        dir_path = os.path.dirname(xml_path)
        if not os.path.exists(dir_path):
            raise FileNotFoundError(f"Error path: xml dir='{dir_path}' not exist.")
    except KeyError as e:
        raise Exception(f"Cant get config by key: {e}.") from e


async def check_case_conf() -> None:
    result = ubs_case_conf_info()
    if not result:
        raise EnvironmentError("CaseConf is None, terminate operation!")
    if float(result.over_commitment) != FRAGMENTED_SCENE_RATIO:
        raise EnvironmentError(
            f"Mem allocation ratio is {result.over_commitment}, not fragmented scene ratio, terminate operation!")


async def validate_params(size: int, image_name: str) -> (float, str):
    if size <= 0:
        raise ValueError(f"Invalid parameter: 'size' must be a positive number, got {size}.")

    if not isinstance(image_name, str):
        raise TypeError("Image name must be a string.")

    if not image_name.strip():
        raise ValueError("Invalid parameter: 'image_name' cannot be an empty string.")


async def validate_echo_line_format(parts: List[str]):
    if len(parts) >= 3:
        return parts[1]
    raise Exception(f"Invalid echo line format: {parts}")


async def validate_vm_num_and_name(vm_num: int, vm_name: str):
    LOG.info("Start verifying the number and name of vm.")
    if vm_num != 1 or not vm_name:
        raise Exception(f"VM num: {vm_num} instead of 1 or vm is not exist")
    LOG.info(f"Successfully verified the number and name of vm, vm name: {vm_name} and the number of vm: {vm_num}.")
