import random
import string


def generate_random_string(length=10):
    # 定义可以使用的字符集合：所有字母和数字
    characters = string.ascii_letters + string.digits
    # 使用 random.choices 从字符集合中随机选择指定长度的字符
    random_string = ''.join(random.choices(characters, k=length))
    return random_string
