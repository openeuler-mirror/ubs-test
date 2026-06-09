#! /bin/python3
# -*- coding: utf-8 -*-
# 版权所有 (c) 华为技术有限公司 2012-2025
import json
from collections import namedtuple
from typing import Dict, List

import libs.ubturbo.api.system as system
from libs.ubturbo.common import basic, file_transport
from libs.ubturbo.model.borrow.ledger_entry import LedgerEntry

# 定义具名元组类型，增强使用体验及可靠性
UpdatedEntryListTuple = namedtuple("UpdatedEntryListTuple", ["return_list", "borrow_list", "changed_list"])

OS_REMOTE_TEST_PATH = '/home/autotest/os'  # 执行环境父目录
TEST_STUB_REMOTE_FILE_PATH = f'{OS_REMOTE_TEST_PATH}/test_stub/Tools'
GET_BORROW_SDK_PATH = f'{TEST_STUB_REMOTE_FILE_PATH}/getAllBorrowInfo'
GET_BORROW_CNA_PATH = f'{TEST_STUB_REMOTE_FILE_PATH}/getCna.sh'


class Ledger:
    def __init__(self):
        self.entries: Dict[str, LedgerEntry] = {}

    @classmethod
    def upload_compile_cpp(cls, node):
        """
        将 sdk 获取借入方账本信息的脚本(getAllBorrowInfo.c)和根据 numaid 获取借用 socket 信息(getCna.sh)
        上传至环境并编译
        """
        try:
            sdk_exists = system.is_path_exist(node, GET_BORROW_SDK_PATH)
            cna_exists = system.is_path_exist(node, GET_BORROW_CNA_PATH)
            if not (sdk_exists and cna_exists):
                system.mkdir(node, TEST_STUB_REMOTE_FILE_PATH)
                file_transport.send2remote(
                    node, f"{file_transport.THIS_PROJECT_PATH}/resource/ubsrmrs/TestStub/Tools/getAllBorrowInfo.c",
                    TEST_STUB_REMOTE_FILE_PATH)
                file_transport.send2remote(
                    node, f"{file_transport.THIS_PROJECT_PATH}/resource/ubsrmrs/TestStub/Tools/getCna.sh",
                    TEST_STUB_REMOTE_FILE_PATH)
                basic.run(node, f"sed -i 's/\\r$//' {GET_BORROW_CNA_PATH}")
                rc = basic.run(
                    node, f"gcc {GET_BORROW_SDK_PATH}.c -o {GET_BORROW_SDK_PATH} -I /usr/include/ubse -lubse-client").rc
                if rc != 0:
                    raise Exception("脚本编译报错，无法执行对账")
        except Exception as e:
            basic.logger.error(f"上传/编译脚本失败: {e}")
            raise

    @classmethod
    def query_borrow_ledger(cls, node) -> List[dict]:
        """
        查询环境账本，返回包含所有账目的账本列表
        :param node: 执行命令的节点
        :return: 包含所有账目的账本列表 = [{entry_dict0}, {entry_dict1}, ....]
        """
        query_curl = GET_BORROW_SDK_PATH
        try:
            res = json.loads(basic.run(node, query_curl).stdout)
            return res["borrows"]
        except json.JSONDecodeError:
            return []

    @classmethod
    def update_ledger(cls, node_list, local_ledger: "Ledger") -> UpdatedEntryListTuple:
        """
        查询环境账本，更新维护的ledger，并返回变动的账目信息，列表中多个账目时，不保证借用/归还/更新的顺序
        :param node: 执行命令的节点
        :param local_ledger: 上一次维护的账本
        :return: 返回变更账目列表组成的具名元组UpdatedEntryListTuple = [[return_entry_list],[borrow_entry_list],[changed_entry_list]]
        set_A = [1,2,3,4] set_B = [2,3,4,5]
        set_A - set_B = [1], set_B - set_A = [5], set_A & set_B = [2,3,4]
        """
        basic.logger.debug("========准备账本查询脚本========")
        for node in node_list:
            # if not node.isReachable():
            #     basic.logger.warn("===当前节点不可达，跳过上传===")
            #     continue
            cls.upload_compile_cpp(node)
        basic.logger.debug("========开始对账，同步代码维护账本和环境实际账本========")
        borrow_ledger = []
        for node in node_list:
            # if not node.isReachable():
            #     basic.logger.warn("===当前节点不可达，跳过对账===")
            #     continue
            basic.logger.info(f"========开始获取{node.localIP}:{node.port}的借入信息========")
            borrow_ledger += cls.query_borrow_ledger(node)
        new_ledger = Ledger()
        new_ledger.load_from_list(borrow_ledger)

        # 通过对账，获取归还账目和新借用账目的borrow_id
        return_ids = set(local_ledger.entries) - set(new_ledger.entries)
        borrow_ids = set(new_ledger.entries) - set(local_ledger.entries)
        update_ids = set([])

        # 列表存储具体的归还、新借用及有变动的账目信息
        return_entry_list = []
        borrow_entry_list = []
        changed_entry_list = []
        # 存放本次对账结果中被归还的账目列表，已归还账目从local_ledger移除
        for entry_id in return_ids:
            return_entry_list.append(local_ledger.entries[entry_id])
            local_ledger.remove_entry(entry_id)

        # 存放本次对账结果中新借用的账目列表，新借用账目添加至local_ledger
        for entry_id in borrow_ids:
            borrow_entry_list.append(new_ledger.entries[entry_id])
            local_ledger.add_entry(new_ledger.entries[entry_id])

        # 存放本次对账结果中有变动的账目列表，变动账目更新至local_ledger
        for entry_id in (set(local_ledger.entries) & set(new_ledger.entries)):
            if local_ledger.entries[entry_id] != new_ledger.entries[entry_id]:
                update_ids.add(entry_id)
                basic.logger.debug(f"========{entry_id}账目有变更========")
                basic.logger.debug(f"变更前：{local_ledger.entries[entry_id]}")
                basic.logger.debug(f"变更后：{new_ledger.entries[entry_id]}")
                local_ledger.add_entry(new_ledger.entries[entry_id])
                changed_entry_list.append(new_ledger.entries[entry_id])

        basic.logger.debug("========对账完成========")
        basic.logger.debug(f"归还账目：{return_ids}")
        basic.logger.debug(f"借用账目：{borrow_ids}")
        basic.logger.debug(f"更新账目：{update_ids}")

        return UpdatedEntryListTuple(return_entry_list, borrow_entry_list, changed_entry_list)

    def add_entry(self, entry: LedgerEntry):
        # 更新或新增
        self.entries[entry.name] = entry

    def remove_entry(self, entry_name: str):
        self.entries.pop(entry_name, None)

    def load_from_list(self, entry_dict_list: List[dict]):
        """
        传入转换后的curl查询账本结果 res["borrows"],即[{detail_info_dict0},{detail_info_dict1}]
        :param entry_dict_list:
        :return:
        """
        for entry_dict in entry_dict_list:
            entry = LedgerEntry.from_dict(entry_dict)
            self.add_entry(entry)

    def to_dict_list(self) -> List[dict]:
        return [entry.to_dict() for entry in self.entries.values()]

    def to_json(self) -> str:
        return json.dumps(self.to_dict_list(), indent=2)
