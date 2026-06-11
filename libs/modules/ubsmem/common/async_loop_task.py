#!/usr/bin/python3.7
# -*- coding: utf-8 -*-
# 版权所有 (c) 华为技术有限公司 2025-2025

import threading
import time
from typing import Callable

from libs.utils.logger_compat import Log


class AsyncLoopTask:
    """
    并发任务类，通过 A.func()的方式调用传入的类对象的func()
    支持统一参数和定制参数
    统一参数与原func(a,b,c)调用方式一致
    """

    def __init__(self, obj: object, interval: float = 1.0, loop_run: bool = True):
        self._executor = obj
        self._task_interval = interval
        self._thread = None
        self._latest_result = None
        self._result_ready = False
        self._methods = self._get_methods()
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._condition = threading.Condition(self._lock)
        self._loop_run = loop_run
        self._logger = Log.getLogger(str(self.__module__))

    def __getattr__(self, method):
        if method in self._methods:
            return lambda *args, **kwargs: self._call_method(method, *args, **kwargs)
        raise AttributeError(f"No such attribute: {method}")

    def get_latest_result(self):
        time.sleep(1)
        with self._condition:
            while not self._result_ready:
                self._condition.wait()
            self._result_ready = False
            return self._latest_result

    def stop(self):
        self._stop_event.set()
        self._thread.join()

    def _get_methods(self):
        methods = set()
        for method in dir(self._executor):
            if callable(getattr(self._executor, method)) and not method.startswith("__"):
                methods.add(method)
        return methods

    def _run_loop(self, task_func: Callable, *args, **kwargs):
        if not self._loop_run:
            time.sleep(self._task_interval)
            with self._condition:
                self._latest_result = task_func(*args, **kwargs)
                self._logger.info(f"The return value({self._latest_result}) of executing the {task_func} method ")
                self._result_ready = True
                self._condition.notify()
            return
        while not self._stop_event.is_set():
            try:
                with self._condition:
                    self._latest_result = task_func(*args, **kwargs)
                    self._logger.info(f"The return value({self._latest_result}) of executing the {task_func} method ")
                    self._result_ready = True
                    self._condition.notify()
            except Exception as e:
                self._logger.error(f"Task error: {e}")
            self._stop_event.wait(self._task_interval)

    def _call_method(self, method, *args, **kwargs):
        method_to_call = getattr(self._executor, method)
        if method_to_call:
            self._thread = threading.Thread(target=self._run_loop, args=(method_to_call, *args,), kwargs=kwargs)
            self._thread.start()