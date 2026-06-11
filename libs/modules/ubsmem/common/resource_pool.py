import threading
from typing import List


class ResourcePool:
    def __init__(self, resources: List[object]):
        self._resources_queue = resources
        self.lock = threading.Lock()

    def acquire(self):
        with self.lock:
            return self._resources_queue.pop()

    def acquire_by_index(self, index):
        return self._resources_queue[index]

    def release(self, obj):
        with self.lock:
            self._resources_queue.append(obj)