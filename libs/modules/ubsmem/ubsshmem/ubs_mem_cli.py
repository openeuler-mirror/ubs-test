#!/usr/bin/python3.7
# -*- coding: utf-8 -*-
# 版权所有 (c) 华为技术有限公司 2025-2025

import re
from typing import Optional, List, Union

import requests

from libs.utils.logger_compat import Log
from libs.modules.ubsmem.common.node_excutor import NodeExecutor
from libs.modules.ubsmem.ubsshmem.ubs_mem_models import UbsMemInstance, AddrDesc, UbsmemRegionAttributes, \
    UbsmemRegionDesc, UBSMemLocation, UBSMemProvider, \
    UBSMemShmInfo


class UbsMemHttpClient:
    def __init__(self, host_node: NodeExecutor, install_path: str, app_port: int):
        self.install_path = install_path
        self._host_node = host_node
        self._file_set = set()
        self.app_id = app_port
        self._api_url = f"http://{host_node.ip}:{self.app_id}/api"
        self.logger = Log.getLogger(str(self.__module__))

    def _call(self, action: str, params: Optional[dict] = None) -> dict:
        """内部方法：发送HTTP请求"""
        payload = {"action": action, "params": params or {}}
        self.logger.info(f"[UbsMemHttpClient] send to {self._api_url}, action: {action}, params: {params}")
        try:
            resp = requests.post(self._api_url, json=payload, timeout=630)
            result = resp.json()
        except requests.exceptions.RequestException as e:
            result = {"success": False, "message": str(e)}
        self.logger.info(f"[UbsMemHttpClient] result from {self._api_url}, action: {action}, result: {result}")
        return result

    @staticmethod
    def str_convert(normal_str: Optional[str]) -> str:
        if normal_str == "":
            return "empty"
        if normal_str is None:
            return "NULL"
        return normal_str

    def get_addr_file(self, adds_list: List[str]) -> str:
        file_id = id(adds_list)
        addr_file = f"{self.install_path}/bin/addr_{self.app_id}_{file_id}.txt"
        if file_id in self._file_set:
            return addr_file
        self.logger.info(f"create addr file: {addr_file}")
        addr_str = "\n".join(adds_list)
        self._host_node.write_file(addr_file, addr_str)
        self._file_set.add(file_id)
        return addr_file

    def clear_addr_file(self, adds_list: List[str]):
        file_id = id(adds_list)
        addr_file = f"{self.install_path}/bin/addr_{self.app_id}_{file_id}.txt"
        self._host_node.read_file(addr_file)
        self._host_node.remove_file(addr_file)

    def get_map_addr_file(self, shm_name: str) -> str:
        return f"{self.install_path}/bin/{shm_name}{self.app_id}.addr"

    def get_map_addr(self, shm_name: str, index: int, count: int) -> List[str]:
        """
        :param shm_name: 共享内存的前缀
        :param index: 下标，从0开始
        :param count: 查询的数量
        :return: 返回16进制地址字符串列表
        """
        result = self._host_node.run(f"head -n {index + count} {self.get_map_addr_file(shm_name)} | tail -n {count}")
        matches = re.findall(r"(0x[0-9a-fA-F]+)", result.std_out)
        return matches

    def ubsmem_lease_malloc(self, region_name: Optional[str], size: int,
                          mem_distance: UbsMemInstance, flags: int, local_ptr: int = -1) -> AddrDesc:
        """Alloc an area from the resource pool

        对应C接口: int ubsmem_lease_malloc(const char *region_name, size_t size,
                                           ubsmem_distance_t mem_distance, uint64_t flags,
                                           void **local_ptr)

        Args:
            region_name: name of the region
            size: size of the space to allocate in bytes
            mem_distance: performance distance
            flags: Special marking for this object

        Returns:
            (ret, local_ptr) - ret: 0 on success; local_ptr: pointer address string
        """
        result = self._call("ubsmem_lease_malloc", {
            "region_name": region_name,
            "size": size,
            "distance": mem_distance.value,
            "flags": flags
        })
        ptr = result.get("data", {}).get("ptr", "")
        return AddrDesc(result.get("result", -1), ptr)

    def ubsmem_lease_malloc_with_location(self, src_loc: Optional[UBSMemLocation], size: int, flags: int, local_ptr: int = -1) -> AddrDesc:
        """Alloc memory from a specified location

        对应C接口: int ubsmem_lease_malloc_with_location(
            const ubs_mem_location_t *src_loc, size_t size, uint64_t flags, void **local_ptr)

        Args:
            src_loc: location information (slot_id, socket_id, numa_id, port_id)
            size: size of the space to allocate in bytes
            flags: Special marking for this object

        Returns:
            (ret, local_ptr) - ret: 0 on success; local_ptr: pointer address string
        """
        params = {"size": size, "flags": flags}
        params.update(src_loc.to_json())
        result = self._call("ubsmem_lease_malloc_with_location", params)
        ptr = result.get("data", {}).get("ptr", "")
        return AddrDesc(result.get("result", -1), ptr)

    def ubsmem_lease_free(self, local_ptr: str) -> int:
        """Release the pointer

        对应C接口: int ubsmem_lease_free(void *local_ptr)

        Args:
            local_ptr: The pointer returned by the malloc function

        Returns:
            0 on success and other on failure
        """
        result = self._call("ubsmem_lease_free", {"ptr": local_ptr})
        return result.get("result", -1)

    def ubsmem_shmem_allocate(self, region_name: Optional[str], name: Optional[str], size: int, mode: int, flags: int) -> int:
        """Allocate some named space within a region

        对应C接口: int ubsmem_shmem_allocate(const char *region_name, const char *name,
                                            size_t size, mode_t mode, uint64_t flags)

        Args:
            region_name: name of the region
            name: name of the share memory object
            size: size of the space to allocate in bytes
            mode: mode associated with this space
            flags: Special marking for this object

        Returns:
            0 on success and other on failure
        """
        result = self._call("ubsmem_shmem_allocate", {
            "region_name": region_name,
            "name": name,
            "size": size,
            "mode": mode,
            "flags": flags
        })
        return result.get("result", -1)

    def ubsmem_shmem_allocate_batch(self, region_name: Optional[str], name: Optional[str], size: int, mode: int, flags: int, batch_num: int) -> int:
        """Batch allocate named shared memory: name_0 ... name_{batch_num-1}.
        Failed mid-way triggers rollback of already-created names.

        对应服务端自定义接口: ubsmem_shmem_allocate_batch

        Args:
            region_name: name of the region
            name: prefix of the share memory object name
            size: size of each space to allocate in bytes
            batch_num: number of allocations
            mode: mode associated with this space
            flags: Special marking for this object

        Returns:
            0 on success, -1 on failure
        """
        result = self._call("ubsmem_shmem_allocate_batch", {
            "region_name": region_name,
            "name": name,
            "size": size,
            "mode": mode,
            "flags": flags,
            "batch_num": batch_num
        })
        return result.get("result", -1)

    def ubsmem_shmem_allocate_with_provider(self, src_loc: Optional[UBSMemProvider], name: str, size: int, mode: int, flags: int) -> int:
        """Allocate named shared memory from a specified node (provider)

        对应C接口: int ubsmem_shmem_allocate_with_provider(
            const ubs_mem_provider_t *src_loc, const char *name, size_t size, mode_t mode, uint64_t flags)

        Args:
            src_loc: provider node information
            name: name of the share memory object
            size: size of the space to allocate in bytes
            mode: mode associated with this space
            flags: Special marking for this object

        Returns:
            0 on success and other on failure
        """
        params = {"name": name, "size": size, "mode": mode, "flags": flags}
        params.update(asdict(src_loc))
        result = self._call("ubsmem_shmem_allocate_with_provider", params)
        return result.get("result", -1)

    def ubsmem_shmem_deallocate(self, name: str) -> int:
        """Deallocate allocated space in memory

        对应C接口: int ubsmem_shmem_deallocate(const char *name)

        Args:
            name: name of the share memory object

        Returns:
            0 on success and other on failure
        """
        result = self._call("ubsmem_shmem_deallocate", {"name": name})
        return result.get("result", -1)

    def ubsmem_shmem_deallocate_batch(self, name: str, batch_num: int) -> int:
        """Batch deallocate shared memory: name_0 ... name_{batch_num-1}

        对应服务端自定义接口: ubsmem_shmem_deallocate_batch

        Args:
            name: prefix of the share memory object name
            batch_num: number of deallocations

        Returns:
            0 on success
        """
        result = self._call("ubsmem_shmem_deallocate_batch", {
            "name": name,
            "batch_num": batch_num
        })
        return result.get("result", -1)

    def ubsmem_shmem_map(self, addr: Union[int, str], length: int, prot: int, flags: int, name: Optional[str],
                       offset: int, local_ptr: int = -1) -> AddrDesc:
        """Map item in UBSMSHMEM to the local virtual address space

        对应C接口: int ubsmem_shmem_map(void *addr, size_t length, int prot, int flags,
                                        const char *name, off_t offset, void **local_ptr)

        Args:
            addr: The starting address (None for kernel to choose)
            length: The length of the mapping (must be greater than 0)
            prot: desired memory protection
            flags: same as mmap
            name: name of the share memory object
            offset: offset must be a multiple of the page size

        Returns:
            (ret, local_ptr) - ret: 0 on success; local_ptr: pointer address string
        """
        params = {
            "addr": addr or "",
            "length": length,
            "prot": prot,
            "flags": flags,
            "name": name,
            "offset": offset
        }
        result = self._call("ubsmem_shmem_map", params)
        ptr = result.get("data", {}).get("ptr", "")
        return AddrDesc(result.get("result", -1), ptr)

    def ubsmem_shmem_map_batch(self, addr: Union[int, str], length: int, prot: int, flags: int, name: Optional[str],
                       offset: int, batch_num: int) -> int:
        """Batch map shared memory: name_0 ... name_{batch_num-1}.
        Pointers are stored internally on server, keyed by name.

        对应服务端自定义接口: ubsmem_shmem_map_batch

        Args:
            name: prefix of the share memory object name
            length: length of each mapping
            batch_num: number of mappings
            addr: starting address (None for kernel to choose)
            prot: memory protection
            flags: mapping flags
            offset: offset

        Returns:
            0 on success, -1 on failure
        """
        result = self._call("ubsmem_shmem_map_batch", {
            "name": name,
            "length": length,
            "batch_num": batch_num,
            "addr": addr or "",
            "prot": prot,
            "flags": flags,
            "offset": offset
        })
        return result.get("result", -1)

    def ubsmem_shmem_unmap(self, local_ptr: str, length: int) -> int:
        """Unmap a data item in UBSMSHMEM

        对应C接口: int ubsmem_shmem_unmap(void *local_ptr, size_t length)

        Args:
            local_ptr: pointer within the process virtual address space
            length: the size to be unmapped

        Returns:
            0 on success and other on failure
        """
        result = self._call("ubsmem_shmem_unmap", {"ptr": local_ptr, "length": length})
        return result.get("result", -1)

    def ubsmem_shmem_unmap_batch(self, shm_name: str, length: int, batch_num: int) -> int:
        """Batch unmap shared memory by name prefix.
        Looks up internally stored pointers on server.

        对应服务端自定义接口: ubsmem_shmem_unmap_batch

        Args:
            shm_name: prefix of the share memory object name
            batch_num: number of unmappings
            length: length of each mapping

        Returns:
            0 on success
        """
        result = self._call("ubsmem_shmem_unmap_batch", {
            "name": shm_name,
            "batch_num": batch_num,
            "length": length
        })
        return result.get("result", -1)

    def ubsmem_shmem_set_ownership(self, name: Optional[str], start: str, length: int, prot: int) -> int:
        """Change permissions associated with a data item descriptor

        对应C接口: int ubsmem_shmem_set_ownership(const char *name, void *start,
                                               size_t length, int prot)

        Args:
            name: descriptor associated with some data item
            start: starting address pointer string
            length: length of the region
            prot: new permissions for the data item

        Returns:
            0 on success and other on failure
        """
        result = self._call("ubsmem_shmem_set_ownership", {
            "name": name,
            "start": start,
            "length": length,
            "prot": prot
        })
        return result.get("result", -1)

    def mem_write(self, ptr: str, length: int, value: int) -> int:
        """Write a byte value into each byte of the specified memory range
        Args:
            ptr: starting address pointer string
            length: number of bytes to write
            value: byte value (0-255) to fill

        Returns:
            0 on success
        """
        result = self._call("mem_write", {"ptr": ptr, "length": length, "value": value})
        return result.get("result", -1)

    def mem_check(self, ptr: str, length: int, value: int) -> int:
        """Verify every byte in the specified memory range equals the given value
        Args:
            ptr: starting address pointer string
            length: number of bytes to check
            value: expected byte value (0-255)

        Returns:
            0 if all bytes match, -1 otherwise
        """
        result = self._call("mem_check", {"ptr": ptr, "length": length, "value": value})
        return result.get("result", -1)

    def ubsmem_create_region(self, region_name: Optional[str], size: int, reg_attr: Optional[UbsmemRegionAttributes]) -> int:
        """Create a large region of UBSMSHMEM

        对应C接口: int ubsmem_create_region(const char *region_name, size_t size,
                                            const ubsmem_region_attributes_t *reg_attr)

        Args:
            region_name: name of the region
            size: size (in bytes) requested for the region
            reg_attr: details of UBSMSHMEM region attributes

        Returns:
            0 on success and other on failure
        """
        params = {"region_name": region_name, "size": size}
        params.update(reg_attr.to_json())
        result = self._call("ubsmem_create_region", params)
        return result.get("result", -1)

    def ubsmem_lookup_region(self, region_name: Optional[str], region_desc: Optional[UbsmemRegionDesc]) -> int:
        """Look up a region in UBSMSHMEM by name

        对应C接口: int ubsmem_lookup_region(const char *region_name, ubsmem_region_desc_t *region_desc)

        Args:
            region_name: name of the region
            region_desc: [out] The descriptor to the region

        Returns:
            (ret, region_desc) - ret: 0 on success
        """
        result = self._call("ubsmem_lookup_region", {"region_name": region_name})
        ret = result.get("result", -1)
        data = result.get("data", {})
        region_desc.region_name = data.get("region_name", "")
        region_desc.size = data.get("size", 0)
        region_desc.host_num = data.get("host_num", 0)
        region_desc.hosts = []
        for h in data.get("hosts", []):
            region_desc.hosts.append(ubsmem_host_t(
                host_name=h.get("host_name", ""),
                affinity=h.get("affinity", False)
            ))
        return ret

    def ubsmem_destroy_region(self, region_name: Optional[str]) -> int:
        """Destroy a region

        对应C接口: int ubsmem_destroy_region(const char *region_name)

        Args:
            region_name: name of the region

        Returns:
            0 on success and other on failure
        """
        result = self._call("ubsmem_destroy_region", {"region_name": region_name})
        return result.get("result", -1)


    def ubsmem_shmem_lookup(self, name: str, shm_info: UBSMemShmInfo) -> int:
        """Look up shared memory info

        对应C接口: int ubsmem_shmem_lookup(const char *name, ubsmem_shmem_info_t *shm_info)

        Args:
            name: name of the share memory object
            shm_info: [out] shared memory info

        Returns:
            (ret, shm_info)
        """
        result = self._call("ubsmem_shmem_lookup", {"name": name})
        ret = result.get("result", -1)
        data = result.get("data", {})
        shm_info.name = data.get("name", "")
        shm_info.size = data.get("size", 0)
        shm_info.mem_num = data.get("mem_num", 0)
        shm_info.mem_unit_size = data.get("mem_unit_size", 0)
        return ret
