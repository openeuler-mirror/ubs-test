from concurrent.futures import ThreadPoolExecutor
from typing import List

from libs.utils.logger_compat import Log


class MultiTask:
    """
    并发任务类，通过 A.func()的方式调用传入的类对象的func()
    支持统一参数和定制参数
    统一参数与原func(a,b,c)调用方式一致
    定制参数使用func([(a,b,c),(d,e,f)])元祖列表的方式传入
    """
    def __init__(self, objects: List[object]):
        self.objects = objects
        self.methods = self._get_methods()
        self.logger = Log.getLogger(str(self.__module__))

    def _get_methods(self):
        methods = set()
        for obj in self.objects:
            for method in dir(obj):
                if callable(getattr(obj, method)) and not method.startswith("__"):
                    methods.add(method)
        return methods

    def _call_method(self, method, *args, **kwargs):
        if args and isinstance(args[0], list) and all(isinstance(x, tuple) for x in args[0]):
            param_list = args[0]
            if len(param_list) != len(self.objects):
                raise ValueError(f"The length of the parameter list({len(param_list)}) must be the same as"
                                 f" that of the object list({len(self.objects)}).")
            args_per_object = param_list
        else:
            args_per_object = [args] * len(self.objects)
        with ThreadPoolExecutor(max_workers=32) as executor:
            futures = []
            for i, obj in enumerate(self.objects):
                method_to_call = getattr(obj, method)
                if method_to_call:
                    self.logger.debug(f"check param {i} {args_per_object[i]}")
                    futures.append(executor.submit(method_to_call, *(args_per_object[i]), **kwargs))
            return [future.result() for future in futures]

    def __getattr__(self, method):
        if method in self.methods:
            return lambda *args, **kwargs: self._call_method(method, *args, **kwargs)
        else:
            raise AttributeError(f"Method {method} not found in object list.")