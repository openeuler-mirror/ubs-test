#! /bin/python3
# -*- coding: utf-8 -*-
# 版权所有 (c) 华为技术有限公司 2012-2025

import os
import json
from libs.utils.logger_compat import Log


def get_cida_parameters(params_parser=None):
    base = os.path.dirname(os.path.dirname(Log.LogFileDir))
    fn = os.path.join(base, "task.json")
    if not os.path.exists(fn):
        return {}

    params = json.loads(open(fn, encoding="utf-8").read())
    _param = params['param']['param'] if params['param'].get('param') else params['param']
    if not (_param.get("userExtendContent") and 'exeParam' in _param.get("userExtendContent")):
        return {}

    user_params = json.loads(_param["userExtendContent"])
    exe_params = json.loads(str(user_params['exeParam'])) if user_params['exeParam'] else {}
    if params_parser:
        exe_params = params_parser(exe_params)
    return exe_params


CIDA_PARAMS = get_cida_parameters()

