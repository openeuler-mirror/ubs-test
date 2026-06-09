from typing import Any, Optional, Union


def json_contain(json_data: Union[dict, list], key: str, value: Any = None) -> bool:
    """
    递归检查 JSON 中的所有字典和数组
    当 value != None: 检查是否包含{key=value}
    当 value == None: 检查是否包含key
    """
    if isinstance(json_data, dict):
        for k, v in json_data.items():
            if k == key:
                if value is None:
                    return True
                else:
                    return True if v == value else False
            elif isinstance(v, dict) or isinstance(v, list):
                if json_contain(v, key, value):
                    return True
    elif isinstance(json_data, list):
        for item in json_data:
            if json_contain(item, key, value):
                return True
    return False
