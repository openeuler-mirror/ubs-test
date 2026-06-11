#! /bin/python3
# -*- coding: utf-8 -*-
# 版权所有 (c) 华为技术有限公司 2012-2025
from dataclasses import dataclass
from typing import List, Dict


@dataclass
class LedgerEntry:
    name: str
    src_node: str
    src_numa: int
    src_remote_numa: int
    borrow_mem_id: List[int]
    lent_node: str
    lent_socket: int
    lent_numa: List[Dict]
    lent_mem_id: List[int]
    size: int

    @staticmethod
    def from_dict(data: dict) -> 'LedgerEntry':
        return LedgerEntry(
            name=data.get("name", ""),
            src_node=data.get("borrowNode", ""),
            src_numa=data.get("borrowLocalNuma", 0),
            src_remote_numa=data.get("borrowRemoteNuma", 0),
            borrow_mem_id=data.get("borrowMemId", []),
            lent_node=data.get("lentNode", ""),
            lent_socket=data.get("lentSocketId", 0),
            lent_numa=data.get("lentNuma", []),
            lent_mem_id=data.get("borrowMemId", []),
            size=data.get("size", 0)
        )

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "borrowNode": self.src_node,
            "borrowLocalNuma": self.src_numa,
            "borrowRemoteNuma": self.src_remote_numa,
            "borrowMemId": self.borrow_mem_id
        }

    def get_total_lent(self) -> int:
        """
        :return: 以M为单位
        """
        total_lent = 0
        for lent_info in self.lent_numa:
            total_lent += int(lent_info["lentSize"])
        return total_lent // 1024 // 1024
