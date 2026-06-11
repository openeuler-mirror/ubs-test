import re
from typing import Dict, List, Optional

import pandas as pd
import json


class MugenTestCase:
    testsuite: Optional[str] = None
    cost_time: int = 0

    def __init__(self, name: str, result: Optional[str], test_type: Optional[str], script: Optional[str]) -> None:
        self.name = name
        self.result = result
        self.test_type = test_type
        self.script = script

    def __repr__(self) -> str:
        return f"KernelTestCase(name={self.name}, result={self.result}, test_type={self.test_type}, script={self.script})"


def load_testcases_from_excel(
    excel_path: str,
    suite_name: str,
    case_list: Optional[List[str]] = None,
    filters: Optional[Dict[str, str]] = None,
) -> List[MugenTestCase]:
    # 使用pandas读取Excel文件
    if filters is None:
        filters = {}
    df = pd.read_excel(excel_path, sheet_name="用例列表",
                       usecols=["TestCase", "TestSuites", "Execute_Result", "Type", "TestCase_Script"])

    # 初始化一个空列表来存放ATestCase对象
    testcases = []
    for index, row in df.iterrows():
        # 提取每一行的数据
        name = row['TestCase']
        testsuites = row['TestSuites']
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
        if not match_flag or (case_list and name not in case_list) or suite_name not in testsuites:
            continue
        testcases.append(MugenTestCase(name, result, test_type, script))
    return testcases


def load_testcases_from_testsuite(suite_file: str) -> List[str]:
    case_list = []
    with open(suite_file+'.json', 'r') as file:
        # 读取JSON内容
        data = json.load(file)
    for i in data["cases"]:
        case_list.append(i["name"])
    return case_list


def parse_log(testsuite: str, log_lines: List[str]) -> Dict[str, MugenTestCase]:
    start_pattern = re.compile(r"start to run testcase:(\S+).")
    exit_pattern = re.compile(r"The case exit by code (\d+)")
    time_pattern = re.compile(r"Execute testsuite: (\S+) testcase: (\S+) cost time is (\d+)")

    current_testcase = None
    results = {}
    for line in log_lines:
        # 匹配用例开始
        line = line.strip()
        match_start = start_pattern.search(line)
        if match_start:
            current_testcase = match_start.group(1)
            results[current_testcase] = MugenTestCase(current_testcase, None, None, None)
            results[current_testcase].testsuite = testsuite

            # 匹配用例退出代码
        match_exit = exit_pattern.search(line)
        if match_exit and current_testcase:
            code = int(match_exit.group(1))
            if code == 0:
                status = "PASS"
            elif code == 255:
                status = "SKIP"
            else:
                status = "FAIL"
            results[current_testcase].result = status

            # 匹配执行时间和测试套
        match_time = time_pattern.search(line)
        if match_time and current_testcase:
            results[current_testcase].cost_time = int(match_time.group(3))
    return results
