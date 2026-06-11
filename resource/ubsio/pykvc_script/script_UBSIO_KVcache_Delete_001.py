import hashlib
import logging
import os
import random
import string   
import sys

import pykvc

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', handlers=[logging.StreamHandler(sys.stdout)])

def get_file_md5(file_path: str) -> str:
    try:
        md5_hash = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                md5_hash.update(chunk)
        return md5_hash.hexdigest()
    except Exception as e:
        logging.error(f"Error calculating MD5 for {file_path}: {e}")
        return None

def generate_random_data(min_length=1024 * 1024, max_length=8 * 1024 * 1024):
    length = random.randint(min_length, max_length)
    return os.urandom(length)

def generate_random_string_digits(min_length=1, max_length=255):
    letters = string.ascii_letters + string.digits + "@"
    length = random.randint(min_length, max_length)
    return ''.join(random.choice(letters) for _ in range(length))

put_file = sys.argv[1]
logging.info(f"put数据写入的文件名为：{put_file}")

get_file = sys.argv[2]
logging.info(f"get数据写入的文件名为：{get_file}")

key_name = generate_random_string_digits()
put_value = generate_random_data()

get_value_len = len(put_value)
logging.info(f"输入的key为：{key_name}")
logging.info(f"输入的key的长度为：{len(key_name)}")
logging.info(f"输入的value的长度为：{len(put_value)}")

try:
    ret = pykvc.initialize()
    assert ret == 0, f"initialize执行失败，结果为：{ret}"

    exist_ret = pykvc.exist(key_name)
    if exist_ret == 0:
        delete_ret = pykvc.delete(key_name)
    
    logging.info("====>>>>>开始执行put操作<<<<====")
    put_ret = pykvc.put(key_name, put_value)
    assert put_ret == 0, f"put操作失败，结果为：{put_ret}"
    logging.info(f"{' ' * 10} put操作执行成功{' ' * 10}")
    with open(put_file, "wb") as f:
        f.write(put_value)
    
    logging.info("====>>>>>开始执行get操作<<<<====")
    get_value = bytes(int(get_value_len))
    get_ret = pykvc.get(key_name, get_value)
    assert get_ret == 0, f"get操作失败，结果为：{get_ret}"
    logging.info(f"{' ' * 10} get操作执行成功{' ' * 10}")
    with open(get_file, "wb") as f:
        f.write(get_value)
    
    logging.info("=====>>>>>判断put和get数据是否一致<<<<<=====")
    assert put_value == get_value, "put和get的数据不一致"
    logging.info(f"{' ' * 10} put和get的数据一致{' ' * 10}")

    logging.info("=====>>>>>比较put和get数据MD5值是否一致<<<<<=====")
    assert get_file_md5(put_file) == get_file_md5(get_file), "put和get数据MD5值不一致"
    logging.info(f"{' ' * 10} put和get数据MD5值一致{' ' * 10}")

    logging.info("=====>>>>>开始执行delete操作<<<<<=====")
    delete_ret = pykvc.delete(key_name)
    assert delete_ret == 0, f"delete操作失败，结果为：{delete_ret}"
    logging.info(f"{' ' * 10} delete操作执行成功{' ' * 10}")

    exist_ret = pykvc.exist(key_name)
    assert exist_ret == False, "delete操作后，key仍然存在"
    logging.info(f"{' ' * 10} delete操作后，key不存在{' ' * 10}")

    logging.info("脚本执行成功")

finally:
    exist_ret = pykvc.exist(key_name)
    if exist_ret == 0:
        delete_ret = pykvc.delete(key_name)