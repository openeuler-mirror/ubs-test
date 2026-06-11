import re
from typing import List, Optional, Dict

import pandas as pd


class KernelTestCase:
    def __init__(self, name: str, result: str, test_type: str, script: str) -> None:
        self.name = name
        self.result = result
        self.test_type = test_type
        self.script = script

    def __repr__(self) -> str:
        return f"KernelTestCase(name={self.name}, result={self.result}, test_type={self.test_type}, script={self.script})"


def load_testcases_from_excel(
    excel_path: str,
    sheet_name: str,
    case_list: Optional[List[str]] = None,
    filters: Optional[Dict[str, str]] = None,
) -> List[KernelTestCase]:
    # 使用pandas读取Excel文件
    if filters is None:
        filters = {}
    df = pd.read_excel(excel_path, sheet_name=sheet_name,
                       usecols=["TestCase", "Execute_Result", "Type", "TestCase_Script"])

    # 初始化一个空列表来存放ATestCase对象
    testcases = []
    for index, row in df.iterrows():
        # 提取每一行的数据
        name = row['TestCase']
        result = row['Execute_Result']
        test_type = row['Type']
        script = row['TestCase_Script']
        match_flag = True
        for key in filters.keys():
            if key not in ['TestCase', 'Execute_Result', 'Type', 'TestCase_Script']:
                continue
            value = filters.get(key)
            if value != row[key]:
                match_flag = False
                break
        if not match_flag or (case_list and name not in case_list):
            continue
        testcases.append(KernelTestCase(name, result, test_type, script))
    return testcases


def load_testcases_from_testsuite(suite_file: str) -> List[str]:
    case_list = []
    with open(suite_file, 'r') as file:
        for line in file:
            line = line.strip()
            if line and not line.startswith('#'):
                # 使用split(' ', 1)来只分割第一个空格
                parts = re.split(r'[\s\t]+', line, 1)
                if len(parts) == 2:
                    case_name, case_script = parts
                    case_list.append(case_name)
    return case_list
