
import libs.ubturbo.api.system as system
from libs.ubturbo.common import basic


class SystemLog:
    """
    begin, end函数成对使用, 支持重入, end函数与离它最近的begin函数配对
    begin: 开始记录当下时间为start_time
    end: 记录当下时间为end_time，并且调用function(start_time, end_time)
    """

    def __init__(self, node, date_format, function=system.find_message_in_log, keyword: str = None):
        self.start_time = []
        self.date_format = date_format
        self.node = node
        self.function = function
        self.keyword = keyword

    def begin(self):
        self.start_time.append(system.get_time(self.node, date_format=self.date_format))

    def end(self, wait: bool = True):
        # 等待日志输出完毕
        if wait:
            result = basic.wait_until(
                lambda: not self.function(node=self.node, start_time=self.start_time[-1], message=self.keyword))
        else:
            result = self.function(node=self.node, start_time=self.start_time[-1])
        self.start_time.pop()
        return result

    def set_keyword(self, keyword):
        self.keyword = keyword
