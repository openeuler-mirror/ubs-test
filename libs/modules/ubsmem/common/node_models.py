#!/usr/bin/python3.7
# -*- coding: utf-8 -*-
# 版权所有 (c) 华为技术有限公司 2025-2025

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class FileStat:
    st_mode: int
    st_ino: int
    st_dev: int
    st_rdev: int
    st_nlink: int
    st_uid: int
    st_gid: int
    st_size: int
    st_atime: int
    st_mtime: int
    st_ctime: int
    st_blksize: int
    st_blocks: int


@dataclass
class FileMate:
    file_name: str
    file_mode: int
    user_name: str
    child: List[Optional['FileMate']]


@dataclass
class UserIdentity:
    user_name: str
    uid: int
    gid: int