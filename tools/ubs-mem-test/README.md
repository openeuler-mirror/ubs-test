# UBS-MEM Test Server

基于 HTTP API 的 UBS 共享内存测试服务器。

## 依赖

- CMake >= 3.14
- C++17 编译器
- pthread
- ubsm_sdk 库 (`/usr/local/ubs_mem/lib/libubsm_sdk.so`)
- 头文件路径: `/usr/local/ubs_mem/include`

## 编译

```bash
# 创建构建目录
mkdir -p build && cd build

# 生成构建文件
cmake ..

# 编译
make -j$(nproc)
```

## 编译输出

| 文件 | 路径 |
|------|------|
| 可执行文件 | `build/ubs_mem_test` |

## 运行

```bash
./build/ubs_mem_test -p 8080
```

### 命令行参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `-l <path>` | SDK 日志文件路径（不指定则输出到 stdout） | - |
| `-p <port>` | HTTP 服务端口 | 8080 |
| `-h` | 显示帮助信息 | - |

## API 接口

### 状态检查

```bash
curl http://localhost:8080/status
```

### API 请求

```bash
curl -X POST http://localhost:8080/api \
  -H "Content-Type: application/json" \
  -d '{"action":"ubsmem_initialize","params":{}}'
```

### 支持的 Action

| Action | 说明 |
|--------|------|
| `ubsmem_init_attributes` | 初始化属性 |
| `ubsmem_initialize` | 初始化 |
| `ubsmem_finalize` | 反初始化 |
| `ubsmem_set_logger_level` | 设置日志级别 |
| `ubsmem_set_extern_logger` | 注册外部日志回调 |
| `ubsmem_create_region` | 创建区域 |
| `ubsmem_lookup_region` | 查询区域 |
| `ubsmem_destroy_region` | 销毁区域 |
| `ubsmem_shmem_allocate` | 分配共享内存 |
| `ubsmem_shmem_allocate_with_provider` | 从指定节点分配共享内存 |
| `ubsmem_shmem_deallocate` | 释放共享内存 |
| `ubsmem_shmem_map` | 映射共享内存 |
| `ubsmem_shmem_unmap` | 解除映射 |
| `ubsmem_shmem_write_lock` | 写锁 |
| `ubsmem_shmem_read_lock` | 读锁 |
| `ubsmem_shmem_unlock` | 解锁 |
| `ubsmem_lease_malloc` | 租用内存分配 |
| `ubsmem_lease_free` | 租用内存释放 |
| `ubsmem_lookup_regions` | 查询所有区域 |
| `ubsmem_shmem_lookup` | 查询共享内存 |
| `ubsmem_shmem_list_lookup` | 列出共享内存 |
