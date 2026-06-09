import logging
import os
import random
import string
import sys
from concurrent.futures import ThreadPoolExecutor

import pykvc

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', handlers=[logging.StreamHandler(sys.stdout)])
list_len_str = sys.argv[1] 
logging.info(f"batch操作时，传入的数据组数为：{list_len_str}")
list_len = int(list_len_str)

put_file = sys.argv[2]
logging.info(f"put数据写入的文件名为：{put_file}")

get_file = sys.argv[3]
logging.info(f"get数据写入的文件名为：{get_file}")

def generate_random_data(min_length=1024 * 1024, max_length=8 * 1024 * 1024) -> bytes:
    """Generate random binary data.
    
    Args:
        min_length: Minimum length in bytes
        max_length: Maximum length in bytes
        
    Returns:
        Random bytes
    """
    length = random.randint(min_length, max_length)
    return os.urandom(length)

def generate_random_string_digits_bytes(min_length=1, max_length=255) -> bytes:
    """Generate random string with digits as bytes.
    
    Args:
        min_length: Minimum length
        max_length: Maximum length
        
    Returns:
        Random bytes
    """
    chars = string.ascii_letters + string.digits + "@"
    length = random.randint(min_length, max_length)

    random_bytes = random.randbytes(length)
    return ''.join(chars[b % len(chars)] for b in random_bytes)

def generate_key_value_pair():
    """Generate a list of random key-value pairs.
        
    Returns:
        List of dictionaries with 'key' and 'value' as bytes
    """
    key = generate_random_string_digits_bytes()
    value = generate_random_data()
    return key, value

key_list = set()
values_list = []
get_values_list = []
value_len = 0
with ThreadPoolExecutor() as executor:
    furtures = [executor.submit(generate_key_value_pair) for _ in range(list_len * 2)]
    for future in furtures:
        key, value = future.result()
        if key not in key_list:
            key_list.add(key)
            values_list.append(value)
            get_values_list.append(value)
            value_len += len(value)
            if len(key_list) == list_len:
                break

key_list = list(key_list)

logging.info(f"输入的value总长度为：{value_len}")
logging.info(f"输入的key_list为： {key_list}")

try:
    ret = pykvc.initialize()
    assert ret == 0, f"initialize执行失败，结果为：{ret}"

    for single_key in key_list:
        exist_ret = pykvc.exist(single_key)
        if exist_ret == 0:
            pykvc.delete(single_key)
    
    logging.info("=====>>>>>开始执行put操作<<<<<=====")
    put_ret = pykvc.batch_put(key_list, values_list)
    assert put_ret.count(0) == list_len, f"batch_put执行失败，结果为：{put_ret}"
    logging.info(f"{' ' * 10}batch_put执行成功{' ' * 10}")
    if list_len <= 5000:
        with open(put_file, 'wb') as f:
            f.writelines(values_list)
    
    logging.info("=====>>>>>开始执行get操作<<<<<=====")
    ge_ret = pykvc.batch_get(key_list, get_values_list)
    assert ge_ret.count(0) == list_len, f"batch_get执行失败，结果为：{ge_ret}"
    logging.info(f"{' ' * 10}batch_get执行成功{' ' * 10}")
    if list_len <= 5000:
        with open(get_file, 'wb') as f:
            f.writelines(get_values_list)
    
    logging.info("=====>>>>>判断batch put和batch get数据是否一致<<<<<=====")
    assert values_list == get_values_list, "batch_put和batch_get的数据不一致"
    logging.info(f"{' ' * 10}batch_put和batch_get的数据一致{' ' * 10}")
    
    logging.info("脚本执行成功")

finally:
    for single_key in key_list:
        exist_ret = pykvc.exist(single_key)
        if exist_ret == 0:
            pykvc.delete(single_key)