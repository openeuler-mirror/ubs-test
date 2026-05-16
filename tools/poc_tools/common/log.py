# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2025-2025. All rights reserved.
import logging
import os
from datetime import timedelta, timezone, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

from poc_tools.common.config import CONF

LOG = logging.getLogger(__name__)
LOG_FILE = None
LOG_LEVEL = "INFO"
LOG_MAX_BYTES = 10485760
BACKUP_COUNT = 14
LOG_FORMAT: str = ("[%(asctime)s]"
                   "[%(levelname)s]"
                   "[%(process)s]"
                   "[%(site_pkg_path)s:%(lineno)d] %(message)s")
CONSOLE_ENABLED: bool = True
PERMISSIONS_R__R___ = 0o440


class Formatter(logging.Formatter):

    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, tz=timezone(timedelta(hours=8)))
        milliseconds = dt.microsecond // 1000
        time_str = dt.strftime('%Y-%m-%d %H:%M:%S') + f'.{milliseconds:03d}' + dt.strftime(' %z')
        return time_str

    def format(self, record):
        full_path = record.pathname
        path_obj = Path(full_path)
        site_packages_dirs = [p for p in path_obj.parents if p.name == "poc_tools"]
        if site_packages_dirs:
            site_pkg_dir = site_packages_dirs[-1]
            relative_path = path_obj.relative_to(site_pkg_dir.parent)
            record.site_pkg_path = (
                str(relative_path).replace("/", ".").replace("\\", ".").replace(".py", ""))
        else:
            try:
                record.site_pkg_path = str(path_obj.relative_to(Path.cwd()))
            except ValueError:
                record.site_pkg_path = full_path
        return super().format(record)


class SecureRotatingFileHandler(RotatingFileHandler):
    def doRollover(self):
        if self.stream:
            self.stream.close()
            self.stream = None
        if self.backupCount > 0:
            for i in range(self.backupCount - 1, 0, -1):
                self.deal_with_backup_log(i)
            dfn = self.rotation_filename(self.baseFilename + ".1")
            if os.path.exists(dfn):
                os.remove(dfn)
            self.rotate(self.baseFilename, dfn)
            os.chmod(dfn, PERMISSIONS_R__R___)
        if not self.delay:
            self.stream = self._open()

    def deal_with_backup_log(self, i):
        sfn = self.rotation_filename("%s.%d" % (self.baseFilename, i))
        dfn = self.rotation_filename("%s.%d" % (self.baseFilename, i + 1))
        if os.path.exists(sfn):
            if os.path.exists(dfn):
                os.remove(dfn)
            os.rename(sfn, dfn)


def init_log():
    global LOG_FILE, LOG_LEVEL, BACKUP_COUNT, LOG_MAX_BYTES, CONSOLE_ENABLED
    LOG_FILE = CONF["log"]["log_path"]
    LOG_LEVEL = CONF.get("log", {}).get("log_level", "INFO")
    BACKUP_COUNT = CONF.get("log", {}).get("backup_count", 14)
    LOG_MAX_BYTES = CONF.get("log", {}).get("max_bytes", 10485760)
    setup()


def setup():
    global LOG
    LOG.setLevel(LOG_LEVEL)
    LOG.propagate = False
    file_handler = SecureRotatingFileHandler(
        filename=str(LOG_FILE),
        maxBytes=LOG_MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
        mode="a"
    )
    formatter = Formatter(
        fmt=LOG_FORMAT,
        datefmt="%Y-%m-%d %H:%M:%S.%03d %z",
    )

    if CONSOLE_ENABLED:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(LOG_LEVEL)
        LOG.addHandler(console_handler)
    file_handler.setFormatter(formatter)
    LOG.addHandler(file_handler)
