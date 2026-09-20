# UBSMem P0 测试用例介绍

## 概述

UBSMem（UBS Memory）是 UB ServiceCore 的内存管理组件，提供内存借用（borrow）和共享内存（shared memory）功能。P0 级别为核心冒烟用例，共 **7 个**，覆盖基础内存借用和共享内存创建场景。

---

## 用例列表

### 内存借用（Memory Borrow）— 5 个

| 用例编号 | 文件名 | 测试场景 | 内存大小 |
|---|---|---|---|
| TC_UBS_MEM_BORROW_0003 | `test_tc_ubs_mem_borrow_0003` | 借用内存后先读后写 | 4M |
| TC_UBS_MEM_BORROW_0007 | `test_tc_ubs_mem_borrow_0007` | 借用内存后先读后写 | 128M |
| TC_UBS_MEM_BORROW_0008 | `test_tc_ubs_mem_borrow_0008` | 借用内存后先读后写 | 1024M |
| TC_UBS_MEM_BORROW_0011 | `test_tc_ubs_mem_borrow_0011` | NUMA 借用内存后先写后读 | 128M |
| TC_UBS_MEM_BORROW_0012 | `test_tc_ubs_mem_borrow_0012` | NUMA 借用内存后先写后读 | 1G |

**测试流程：**
1. 调用 `ubsmem_lease_malloc` 申请内存
2. 写入随机字符并验证内容一致
3. 调用 `ubsmem_lease_free` 释放内存

### 共享内存（Shared Memory）— 2 个

| 用例编号 | 文件名 | 测试场景 | 内存大小 |
|---|---|---|---|
| TC_UBS_SHM_CREATE_0009 | `test_tc_ubs_shm_create_0009` | 创建 UBSM_FLAG_CACHE 类型共享内存，双进程映射 | 1024M |
| TC_UBS_SHM_CREATE_0010 | `test_tc_ubs_shm_create_0010` | 创建 UBSM_FLAG_CACHE 类型共享内存，双进程映射 | 4M |

**测试流程：**
1. 调用 `ubsmem_shmem_allocate` 创建共享内存
2. 两个进程分别调用 `ubsmem_shmem_map` 映射内存
3. 两个进程调用 `ubsmem_shmem_unmap` 解除映射
4. 调用 `ubsmem_shmem_deallocate` 删除共享内存

---

## 环境准备

### 被测对象（UBS-Mem 服务）

UBS Memory（Unified Bus Service Core Memory）是基于 UB 硬件能力在超节点上提供内存高阶服务的组件，实现超节点上的内存借用、共享、缓存等能力。

**代码仓库：** https://gitcode.com/openeuler/ubs-mem.git

**构建要求：**
- 操作系统：推荐 openEuler 24.03 LTS SP3 或更高版本
- 工具：cmake (≥3.13)、ninja-build、gcc/gcc-c++ (≥10.3.1)、rpm-build
- 依赖库：numactl-devel、systemd-devel、openssl-devel、libboundscheck、ubs-comm-devel

**构建步骤：**

```bash
git clone https://gitcode.com/openeuler/ubs-mem.git
cd ubs-mem

# -t 指定编译方式（debug/release），-p 表示打 RPM 包
sh build.sh -t release -p
# 构建产物位于 build/release/output* 目录
```

**项目结构：**
- `src/` — 功能实现源码，仅该目录参与构建出包
- `build/` — 构建脚本目录
- `test/` — UT 和 dtfuzz 等测试
- `build.sh` — 统一构建入口

### 节点环境要求

- **两节点 UB 环境**，节点间网络互通
- 每个节点已部署 UBS-Engine、MMI 组件、UBS-Memory 服务

### 前置条件（PreCondition）

所有 P0 用例依赖以下前置条件：

| 条件 | 说明 |
|---|---|
| P1. UBS-Engine 进程正常拉起 | 引擎服务运行正常 |
| P2. MMI 组件加载正常 | 内存管理接口组件正常 |
| P3. UBS-Memory 服务加载正常 | 内存服务正常 |

Hooks 在执行用例前会自动完成环境检查和准备。

### 测试工具编译部署

UBSMem 测试依赖一个 C++17 测试工具，提供 HTTP API 接口实现共享内存的初始化、创建、查询、分配、释放等操作。

**代码路径：** 本仓库 `tools/ubs-mem-test/` 目录

**编译部署步骤：**

```bash
# 1. 进入测试工具目录（在本测试仓库根目录下执行）
cd tools/ubs-mem-test

# 2. 编译（C++17 环境）
mkdir -p build && cd build
cmake ..
make -j$(nproc)

# 3. 将编译产物放到节点指定位置
# 需要在每个测试节点上创建目录并拷贝
mkdir -p /opt/install/tmp/ubs-mem-dist/
cp ubs_mem_test /opt/install/tmp/ubs-mem-dist/
```

**自动部署机制：**

执行测试时，`ubs_mem_hook.py:62` 会自动将 `/opt/install/tmp/ubs-mem-dist/ubs_mem_test` 拷贝到各节点的工作目录 `{install_path}/bin/` 下。

---

## 执行命令

```bash
python -m pytest testcases/ubsmem/test_tc_ubs_mem_borrow_0003.py testcases/ubsmem/test_tc_ubs_mem_borrow_0007.py testcases/ubsmem/test_tc_ubs_mem_borrow_0008.py testcases/ubsmem/test_tc_ubs_mem_borrow_0011.py testcases/ubsmem/test_tc_ubs_mem_borrow_0012.py testcases/ubsmem/test_tc_ubs_shm_create_0009.py testcases/ubsmem/test_tc_ubs_shm_create_0010.py --resource-config=conf/env.json --no-cov -v
```

或使用 `-k` 关键字过滤：

```bash
python -m pytest testcases/ubsmem/ -k "0003 or 0007 or 0008 or 0011 or 0012 or 0009 or 0010" --resource-config=conf/env.json --no-cov -v
```
