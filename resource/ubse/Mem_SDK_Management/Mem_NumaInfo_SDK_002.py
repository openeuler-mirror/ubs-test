#!/usr/bin/python3
# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2024-2025. All rights reserved.
import os
import sys
from ubse.matrix_mem_python_models import PyMatrixMemMemoryUnit, PyMatrixMemNumaInfoArray, PyMatrixMemNumaMemInfo, \
    PyMatrixMemNumaPair, PyMatrixMemBorrowedAndLentInfo, PyMatrixMemNodeMemoryInfo, PyMatrixMemNodeMemoryInfoArray, \
    PyMatrixMemBorrowedAndLentInfoArray, PyMatrixMemNumaInfo, PyMatrixMemBorrowAccount, PyMatrixMemBorrowAccountArray, \
    PyMatrixMemShareAccount, PyMatrixMemShareAccountArray
from ubse.matrix_mem import MatrixMem


def print_py_matrix_mem_numa_mem_info(info: PyMatrixMemNumaMemInfo):
    os.system(f"echo NUMA ID: {info.numa_id}")
    os.system(f"echo Total Memory: {info.mem_total}")
    os.system(f"echo Free Memory: {info.mem_free}")
    os.system(f"echo Used Memory: {info.mem_used}")
    os.system(f"echo Memory Usage Rate: {info.mem_usage_rate}")
    os.system(f"echo VM Total Memory: {info.vm_mem_total}")
    os.system(f"echo VM Free Memory: {info.vm_mem_free}")
    os.system(f"echo VM Used Memory: {info.vm_mem_used}")
    os.system(f"echo VM Memory Usage Rate: {info.vm_mem_usage_rate}")


def print_py_matrix_mem_numa_pair(pair: PyMatrixMemNumaPair):
    os.system(f"echo Node ID: {pair.node_id}")
    os.system(f"echo NUMA ID: {pair.numa_id}")
    os.system(f"echo Memory: {pair.memory}")


def print_py_matrix_mem_borrowed_and_lent_info(info: PyMatrixMemBorrowedAndLentInfo):
    os.system(f"echo Borrowed Items Size: {info.borrowed_item_size}")
    if info.borrowed_item:
        for item in info.borrowed_item:
            print_py_matrix_mem_numa_pair(item)

    os.system(f"echo Lent Items Size: {info.lent_item_size}")
    if info.lent_item:
        for item in info.lent_item:
            print_py_matrix_mem_numa_pair(item)


def print_py_matrix_mem_node_memory_info(info: PyMatrixMemNodeMemoryInfo):
    os.system(f"echo Node ID: {info.node_id}")
    os.system(f"echo Total Memory: {info.total_memory}")
    os.system(f"echo Used Memory: {info.used_memory}")
    os.system(f"echo Free Memory: {info.free_memory}")
    os.system(f"echo Borrowed Memory: {info.borrowed_memory}")
    os.system(f"echo Lent Memory: {info.lent_memory}")
    os.system(f"echo NUMA Memory Info Size: {info.numa_mem_info_size}")
    if info.numa_mem_info:
        for numa_mem in info.numa_mem_info:
            print_py_matrix_mem_numa_mem_info(numa_mem)
    print_py_matrix_mem_borrowed_and_lent_info(info.borrowed_and_lent_info)


def print_py_matrix_mem_node_memory_info_array(array: PyMatrixMemNodeMemoryInfoArray):
    os.system(f"echo Node Memory Info Size: {array.node_memory_info_size}")
    if array.node_memory_info:
        for node_info in array.node_memory_info:
            print_py_matrix_mem_node_memory_info(node_info)


def print_py_matrix_mem_borrowed_and_lent_info_array(array: PyMatrixMemBorrowedAndLentInfoArray):
    os.system(f"echo Borrowed and Lent Info Size: {array.borrowed_and_lent_info_size}")
    if array.borrowed_and_lent_info:
        for info in array.borrowed_and_lent_info:
            print_py_matrix_mem_borrowed_and_lent_info(info)


def print_py_matrix_mem_numa_info(info: PyMatrixMemNumaInfo):
    os.system(f"echo Timestamp: {info.m_timestamp}")
    os.system(f"echo Memory Total: {info.m_mem_total}")
    os.system(f"echo Memory Used: {info.m_mem_used}")
    os.system(f"echo Memory Free: {info.m_mem_free}")
    os.system(f"echo CPU List: {info.m_cpu_list}")
    os.system(f"echo Memory Borrowed: {info.m_mem_borrowed}")
    os.system(f"echo Memory Lent: {info.m_mem_lent}")
    os.system(f"echo Memory Shared: {info.m_mem_shared}")
    os.system(f"echo Percent: {info.m_percent}")
    os.system(f"echo NUMA Location: {info.numa_loc}")


def print_py_matrix_mem_numa_info_array(array: PyMatrixMemNumaInfoArray):
    os.system(f"echo NUMA Info Size: {array.mem_numa_info_size}")
    if array.mem_numa_info:
        for numa_info in array.mem_numa_info:
            print_py_matrix_mem_numa_info(numa_info)


def print_py_matrix_mem_borrow_account(account: PyMatrixMemBorrowAccount):
    os.system(f"echo Import Node: {account.import_node}")
    os.system(f"echo Import Mem ID: {account.import_mem_id}")
    os.system(f"echo Export Node: {account.export_node}")
    os.system(f"echo Export Mem ID: {account.export_mem_id}")
    os.system(f"echo Size: {account.size}")


def print_py_matrix_mem_borrow_account_array(array: PyMatrixMemBorrowAccountArray):
    os.system(f"echo Borrow Account Size: {array.borrow_account_size}")
    if array.borrow_account:
        for account in array.borrow_account:
            print_py_matrix_mem_borrow_account(account)


def print_py_matrix_mem_share_account(account: PyMatrixMemShareAccount):
    os.system(f"echo Import Map: {account.import_map}")
    os.system(f"echo Export Node: {account.export_node}")
    os.system(f"echo Export Mem ID: {account.export_mem_id}")
    os.system(f"echo Size: {account.size}")


def print_py_matrix_mem_share_account_array(array: PyMatrixMemShareAccountArray):
    os.system(f"echo Share Account Size: {array.share_account_size}")
    if array.share_account:
        for account in array.share_account:
            print_py_matrix_mem_share_account(account)


if __name__ == '__main__':
    matrix_mem = MatrixMem()
    matrix_mem.matrix_connect()
    py_mem_numa_info_array = matrix_mem.matrix_mem_get_all_numa_memory_info()
    print_py_matrix_mem_numa_info_array(py_mem_numa_info_array)
    

    matrix_mem.matrix_disconnect()
    os.system(f"echo disconnect to server success")