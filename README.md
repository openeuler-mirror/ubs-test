# UBS Test

针对 UB ServiceCore 进行多组件的特性测试和集成测试

## 快速开始

> 新手入门指南：5 分钟完成环境搭建并执行第一次测试

### 前置条件

- Python 3.9+ 环境
- SSH 可访问的测试节点（用于集成测试）

### 快速搭建步骤

```bash
# 1. 克隆项目
git clone https://gitcode.com/openeuler/ubs-test.git && cd ubs-test

# 2. 创建并激活虚拟环境
python3 -m venv .venv && source .venv/bin/activate

# 3. 安装项目依赖
pip install -e .

# 4. 验证安装成功
pytest --version && python3 -c "from libs import TestCase; print('环境验证成功')"
```

### 创建节点配置文件

集成测试需要配置测试节点信息。有两种配置方式：

#### 方式一：默认配置路径（推荐）

项目支持自动读取默认配置文件 `conf/env.json`：

```bash
# 创建默认配置目录和文件
mkdir -p conf

cat > conf/env.json << 'EOF'
{
  "hosts": {
    "1": {
      "ip": "192.168.1.100",
      "port": 22,
      "username": "root",
      "password": "your_password",
      "nodeId": "Node0",
      "params": {
        "rack_path": "/usr/local/softbus/ctrlbus"
      }
    }
  },
  "devices": {},
  "global": {"testbed_name": "testbed"}
}
EOF
```

使用默认配置时，无需指定 `--resource-config` 参数：

```bash
pytest testcases/ -v -m integration
```

#### 方式二：指定配置文件路径

创建自定义配置文件（如 `test_nodes.json`）：

```bash
cat > test_nodes.json << 'EOF'
{
  "hosts": {
    "1": {
      "ip": "192.168.1.100",
      "port": 22,
      "username": "root",
      "password": "your_password",
      "nodeId": "Node0",
      "params": {
        "rack_path": "/usr/local/softbus/ctrlbus"
      }
    }
  },
  "devices": {},
  "global": {"testbed_name": "testbed"}
}
EOF
```

执行时指定配置文件：

```bash
pytest --resource-config=test_nodes.json testcases/ -v -m integration
```

> 💡 **提示**: 
> - `params` 字段可选，用于存储节点特定参数
> - `user` 字段已更名为 `username`，请使用新版配置格式
> - 详细配置说明见「节点信息配置文件」章节

### 执行前环境准备

#### 执行 HCOM 测试用例前

需要拉取 ubs_comm 开源仓代码，编译 perf_test 测试工具：

- **开源仓链接**：https://atomgit.com/openeuler/ubs-comm/tree/br_BeiMing.26.0.RC1
- **分支**：`br_BeiMing.26.0.RC1`
- **commitid**：`f0df29c2864e59331c7b4c9a4621f091d8513704`
- **测试工具目录**：`test/hcom/tools/perf_test`

以拉取代码仓方式为例：

```bash
git clone https://atomgit.com/openeuler/ubs-comm.git
cd ubs-comm
git checkout f0df29c2864e59331c7b4c9a4621f091d8513704
cd test/hcom/tools/perf_test
mkdir build && cd build
cmake -DHCOM_INCLUDE_DIR=/usr/lib64 -DHCOM_LIB_DIR=/usr/include/hcom/ ..
make -j8
```

编译完成后会在 `build` 目录下得到 `hcom_perf` 二进制文件。HCOM 用例依赖两节点环境，需要将 `hcom_perf` 同时放在两个节点各自的 `/home/ubs-comm/hcom/perf_test` 文件夹下。

以编译节点为例：

```bash
mkdir -p /home/ubs-comm/hcom/perf_test
cp -r hcom_perf /home/ubs-comm/hcom/perf_test
```

#### 执行 ubsrmrs 测试用例前

需要在执行节点上提前准备创建虚拟机的镜像文件：

1. 在每个执行节点上创建目录：
   ```bash
   mkdir -p /home/mempooling-test/img
   ```
2. 将镜像文件拷贝到该目录下，并将镜像名字修改为 `openEuler-22.03-LTS-SP1-aarch64.qcow2`

#### 执行 ubsvirt 测试用例前

1. 需确保执行节点已安装部署 ubs-openstack 插件
   - 安装指南：https://atomgit.com/openFuyao/ubs-openstack-enable/blob/master/docs/%E5%AE%89%E8%A3%85%E9%83%A8%E7%BD%B2.md
2. 需在执行节点上提前准备创建虚拟机的镜像文件，且镜像中需要安装stress-ng加压工具
   1. 在每个执行节点上创建目录：
      ```bash
      mkdir -p /opt/install/tmp/openstack/images/
      ```
   2. 将镜像文件拷贝到该目录下，并将镜像名字修改为 `openEuler-22.03-SP2-aarch64-everything-redis-Performance.qcow2`


#### 执行 Vas虚拟机线性度测试用例前

需要在执行节点上配置以下操作：

1. 执行硬件环境的cpu需要为鲲鹏950版本以及以上版本，OS和虚拟机OS版本需要为openEuler-22.03及以上版本。
2. 根据安装指南安装好vas进程包以及vas进程需要的qemu、libvirt、libboundscheck等软件，启动libvirtd进程，确保vas可以正常启动，
再配置好vas内核启动参数，修改报存后重启节点生效。 
3. 修改SELINUX配置，修改/etc/selinux/config文件，修改SELINUX=permissive，修改报存后重启节点生效。 
4. yum安装edk2安装包，测试用例创建虚拟机需要此软件。
5. 在/home/目录下存放一个/home/openEuler-24.03-LTS-SP2-everything-aarch64-dvd.iso镜像，用于启动创建虚拟机。
也可以拷贝其他openEuler（大于22.03版本）的镜像，并修改create_vm中iso_path参数内容即可。

   
### 执行测试

```bash
# 执行单元测试（无需节点配置）
pytest tests/ -v

# 执行集成测试（使用默认配置 conf/env.json）
pytest testcases/ -v -m integration

# 执行集成测试（指定配置文件）
pytest --resource-config=test_nodes.json testcases/ -v -m integration

# 执行特定测试模块
pytest testcases/ubturbo/mempooling/ -v

# 查看测试覆盖率报告
pytest --cov=libs --cov-report=html
# 报告位置: htmlcov/index.html
```

***

> 💡 **提示**: 详细的环境搭建、测试执行、用例编写、常见问题解答请参阅下文「测试执行完整指南」章节。

***

## 项目能力总结

UBS Test 是一个专有的测试项目，用于对 UB ServiceCore 进行全面的多组件特性测试和集成测试。项目基于 pytest 框架构建，提供完整的测试基础设施和自动化测试能力。

### 测试覆盖范围

| 测试模块     | 用例数量    | 测试内容                                     |
| -------- | ------- | ---------------------------------------- |
| hcom     | 30      | HCOM API 可用性测试                           |
| ubse     | 16      | UB Pooling Management、UB Controller 管理测试 |
| ubsocket | 22      | Socket 通信功能测试（BRPC TCP/UB/MIX 协议）        |
| ubturbo  | 41      | 内存池化、分布式功能、NUMA 资源管理等测试                  |
| **总计**   | **109** | 多组件集成测试                                  |

### 核心能力

- **测试框架**: 提供 TestCase 和 TestRunner 等核心测试组件，兼容 legacy UniAutos 框架
- **环境管理**: 自动化的测试环境设置和清理，支持 setup/teardown 钩子
- **节点连接**: 通过 SSH 远程执行测试命令，支持 paramiko 库的安全连接
- **配置管理**: 支持 JSON/XML 格式的资源配置文件，灵活定义测试节点信息
- **日志追踪**: 完整的测试步骤日志记录，支持 logStep、logInfo 等日志方法
- **断言验证**: 内置 assertTrue、assertEqual 等断言方法，支持自动化测试验证
- **并行执行**: 支持 pytest-xdist 并行测试执行，提升测试效率
- **测试标记**: 支持多种测试标记（unit、integration、virt、container、slow）灵活筛选

***

## 测试执行完整指南

### 一、前置依赖安装

#### 1. 系统要求

- **操作系统**: Linux（推荐 openEuler 22.03 LTS 或更高版本）
- **Python 版本**: Python 3.9+（支持 3.9、3.10、3.11、3.12、3.13）
- **网络要求**: 能够 SSH 连接到测试节点

#### 2. 安装 Python 环境

```bash
# 检查 Python 版本
python3 --version
# 输出应为 Python 3.9.x 或更高版本

# 如需安装 Python 3.9+（以 openEuler 为例）
sudo dnf install python39 python39-pip
```

#### 3. 克隆项目仓库

```bash
# 克隆仓库
git clone https://gitcode.com/openeuler/ubs-test.git
cd ubs-test

# 或者使用已存在的项目目录
cd /path/to/ubs-test
```

#### 4. 创建虚拟环境（推荐）

```bash
# 创建虚拟环境
python3 -m venv .venv

# 激活虚拟环境
source .venv/bin/activate

# 验证虚拟环境
which python
# 输出应为 .venv/bin/python
```

#### 5. 安装项目依赖

**方式一：使用 requirements.txt 安装**

```bash
# 安装核心依赖
pip install -r requirements.txt
```

**方式二：使用 pyproject.toml 安装（推荐）**

```bash
# 安装项目及所有依赖
pip install -e .

# 安装开发依赖（可选，用于代码格式化和类型检查）
pip install -e ".[dev]"
```

**依赖列表说明**:

| 依赖包            | 版本要求      | 用途          |
| -------------- | --------- | ----------- |
| pytest         | >= 7.4.0  | 测试框架核心      |
| pytest-cov     | >= 4.1.0  | 测试覆盖率报告     |
| pytest-asyncio | >= 0.21.0 | 异步测试支持      |
| pytest-xdist   | >= 3.3.0  | 并行测试执行      |
| paramiko       | >= 3.0.0  | SSH 远程连接    |
| black          | >= 23.7.0 | 代码格式化（开发依赖） |
| isort          | >= 5.12.0 | 导入排序（开发依赖）  |
| mypy           | >= 1.5.0  | 类型检查（开发依赖）  |

#### 6. 验证安装

```bash
# 验证 pytest 安装
pytest --version
# 输出应为 pytest 7.x.x 或更高版本

# 验证 paramiko 安装
python3 -c "import paramiko; print(paramiko.__version__)"
# 输出应为 3.x.x 或更高版本

# 验证项目安装
python3 -c "from libs import TestCase; print('OK')"
# 输出应为 OK
```

***

### 二、节点信息配置文件

测试用例执行需要配置测试节点信息，项目支持 JSON 和 XML 两种配置格式。

#### 1. JSON 配置文件格式（推荐）

创建资源配置文件 `test_nodes.json`：

```json
{
  "hosts": {
    "1": {
      "ip": "192.168.1.100",
      "port": 22,
      "user": "root",
      "password": "your_password",
      "nodeId": "Node0",
      "localIP": "192.168.1.100",
      "params": {
        "rack_path": "/usr/local/softbus/ctrlbus",
        "log_path": "/var/log/scbus"
      }
    }
  },
  "devices": {},
  "global": {
    "testbed_name": "ubs_testbed_01"
  }
}
```

**字段说明**:

| 字段       | 必填 | 说明                |
| -------- | -- | ----------------- |
| ip       | 是  | 节点 IP 地址          |
| port     | 是  | SSH 端口（默认 22）     |
| user     | 是  | SSH 用户名（通常为 root） |
| password | 是  | SSH 密码            |
| nodeId   | 是  | 节点标识符             |
| localIP  | 否  | 本地 IP（用于多网卡场景）    |
| params   | 否  | 节点特定参数（键值对字典）     |

#### 2. XML 配置文件格式（兼容 Legacy）

创建资源配置文件 `test_bed.xml`：

```xml
<?xml version="1.0" encoding="UTF-8"?>
<testbed>
  <host id="1" ip="192.168.1.100" port="22" user="root" password="your_password" nodeId="Node0">
    <params>
      <rack_path>/usr/local/softbus/ctrlbus</rack_path>
      <log_path>/var/log/scbus</log_path>
    </params>
  </host>
  <global>
    <testbed_name>ubs_testbed_01</testbed_name>
  </global>
</testbed>
```

#### 3. 验证配置文件

```bash
# 验证 JSON 配置文件格式
python3 -c "import json; json.load(open('test_nodes.json')); print('JSON OK')"

# 验证配置文件内容
python3 -c "
from libs.utils.env_config import load_resource_config
config = load_resource_config('test_nodes.json')
print(f'Hosts: {len(config[\"hosts\"])} nodes loaded')
"
```

***

### 三、执行测试用例

#### 1. 基本测试执行命令

```bash
# 执行所有测试用例（需要节点配置文件）
pytest --resource-config=test_nodes.json

# 执行测试并生成覆盖率报告
pytest --resource-config=test_nodes.json --cov=libs --cov-report=html

# 执行测试并显示详细输出
pytest --resource-config=test_nodes.json -v --tb=long
```

#### 2. 按测试标记筛选执行

项目支持以下测试标记：

| 标记          | 说明    | 示例命令                    |
| ----------- | ----- | ----------------------- |
| unit        | 单元测试  | `pytest -m unit`        |
| integration | 集成测试  | `pytest -m integration` |
| virt        | 虚拟化测试 | `pytest -m virt`        |
| container   | 容器测试  | `pytest -m container`   |
| slow        | 慢速测试  | `pytest -m slow`        |

```bash
# 执行单元测试
pytest -m unit

# 执行集成测试（需要节点配置）
pytest --resource-config=test_nodes.json -m integration

# 跳过慢速测试
pytest --resource-config=test_nodes.json -m "not slow"

# 执行虚拟化测试
pytest --resource-config=test_nodes.json -m virt

# 组合标记：执行集成测试但跳过慢速测试
pytest --resource-config=test_nodes.json -m "integration and not slow"
```

#### 3. 按测试模块执行

```bash
# 执行指定测试模块
pytest testcases/ubturbo/mempooling/

# 执行指定测试文件
pytest testcases/ubturbo/mempooling/test_memory_pooling_first_borrowstrategy_001.py

# 执行指定测试类
pytest testcases/ubturbo/mempooling/test_memory_pooling_first_borrowstrategy_001.py::memory_pooling_first_BorrowStrategy_001

# 执行指定测试方法
pytest testcases/ubturbo/mempooling/test_memory_pooling_first_borrowstrategy_001.py::memory_pooling_first_BorrowStrategy_001::test_memory_pooling_first_borrowstrategy_001
```

#### 4. 并行执行测试

```bash
# 使用 pytest-xdist 并行执行（自动检测 CPU 核数）
pytest --resource-config=test_nodes.json -n auto

# 指定并行进程数
pytest --resource-config=test_nodes.json -n 4

# 并行执行并显示每个进程的输出
pytest --resource-config=test_nodes.json -n 4 -v
```

#### 5. 通过配置文件批量执行（run_suite.py）

通过 JSON 配置文件定义要跑的用例列表和统一入参，一键批量执行：

**配置文件格式（如 `testcases/ubsmem/ubsmem_suite.json`）：**

```json
{
  "hook": "libs.ubsmem.ubsshmem.ubs_mem_hook.UbsMemHook",
  "tests": [
    "testcases/ubsmem/test_tc_ubs_mem_borrow_0007.py",
    "testcases/ubsmem/test_tc_ubs_mem_borrow_0008.py"
  ],
  "params": {
    "install_path": "/home/ci/ubs_mem",
    "log_bak_path": "/home/ubs_mem_log_bak",
    "cmc_package_path": "/ko/matrix_shmem"
  }
}
```

- `hook` — (可选) hook 类全限定名，如 `libs.ubsmem.ubsshmem.ubs_mem_hook.UbsMemHook`。`run_suite.py` 自动将其传递为 `--test-hook`
- `tests` — 用例脚本列表（相对于项目根目录的路径）
- `params` — 统一入参，对应 `--test-params`，测试中通过 `custom_params` fixture 读取，hook 的 `_init_from_fixture()` 也会接收此参数

**执行命令：**

```bash
# 基本执行
python run_suite.py testcases/ubsmem/ubsmem_suite.json

# 透传 pytest 参数
python run_suite.py testcases/ubsmem/ubsmem_suite.json \
    --resource-config=..\conf\env.json \
    --no-cov -v \
    -o log_cli=true --log-cli-level=DEBUG \
    -W ignore::SyntaxWarning
```

执行完成后会打印汇总信息：

```
============================================================
  [run_suite]  Passed: 20  |  Failed: 2  |  Total: 22
============================================================
```

#### 5.1. Hook 机制 — 测试套前置/后置操作

测试套可声明一个 **hook 类**，在用例执行前自动完成环境准备（安装软件、修改配置、
启动服务等），在用例执行后执行清理。

**启用 Hook 的条件：**

1. **Suite JSON** 中声明 `hook` 字段（全限定类名）
2. **测试包目录** 中存在 `conftest.py`，导入框架 fixture：

   ```python
   # testcases/<your-package>/conftest.py
   from libs.core.hook_runner import package_hook_fixture
   ```

3. **Hook 类** 实现以下三个方法即可，**无需继承特定基类**：

   ```python
   class MyHook:
       """Hook 类。注意：属性应在 _init_from_fixture() 中设置，而非 __init__。"""

        def _init_from_fixture(self, nodes, custom_params):
            """Fixture 注入入口。框架传入 SSH 节点列表和 test-params 字典。
            在这里初始化 self.nodes、self.install_path 等实例属性。"""
            self.ssh_hosts = nodes
            self.my_param = custom_params.get("my_param", "default_value")

       def beforePreTestSet(self):
           """在包内所有用例之前执行。用于安装软件、修改配置、启动服务等。"""
           ...

       def afterPostTestSet(self):
           """在包内所有用例之后执行。用于清理、恢复配置等。"""
           ...
   ```

    - `_init_from_fixture(nodes, custom_params)` — 接收 `--resource-config` 构建的 `libs.host.Linux` 节点列表和 `--test-params` JSON 字典
   - `beforePreTestSet()` — 前置操作
   - `afterPostTestSet()` — 后置操作
   - 三个方法**缺一不可**；`_init_from_fixture` 被框架识别后会自动调用，即使为空也需定义

   > 💡 如果 hook 逻辑较复杂需要日志、`sleep()` 等辅助方法，可继承 `libs.ubsmem.common.mem_hook_base.MemHookBase`（提供 `self.logger`、`self.sleep()` 等），但**非强制**。

**执行流程：**

```
run_suite.py 读取 hook 字段 → --test-hook libs.xxx.MyHook
    │
    ├─ [package scope] package_hook_fixture
    │   ├─ importlib 动态加载 hook 类
    │   ├─ 读 --resource-config → 构建 Linux 节点列表
    │   ├─ 读 --test-params → custom_params 字典
    │   ├─ hook._init_from_fixture(nodes, custom_params)
    │   ├─ hook.beforePreTestSet()   ← 前置操作
    │   └─ yield
    │
    ├─ 逐个执行 tests 列表中的用例...
    │
    └─ hook.afterPostTestSet()   ← 后置清理
```

#### 6. 测试报告生成

```bash
# 生成 HTML 覆盖率报告
pytest --resource-config=test_nodes.json --cov=libs --cov-report=html
# 报告位置: htmlcov/index.html

# 生成 XML 覆盖率报告（用于 CI/CD）
pytest --resource-config=test_nodes.json --cov=libs --cov-report=xml

# 生成 JUnit XML 测试报告
pytest --resource-config=test_nodes.json --junitxml=test-results.xml
```

#### 7. 失败重试与调试

```bash
# 失败用例重试 2 次
pytest --resource-config=test_nodes.json --reruns 2

# 显示失败用例的详细 traceback
pytest --resource-config=test_nodes.json --tb=long

# 进入调试模式（失败时暂停）
pytest --resource-config=test_nodes.json --pdb

# 只执行上次失败的用例
pytest --resource-config=test_nodes.json --lf

# 先执行上次失败的用例
pytest --resource-config=test_nodes.json --ff
```

***

### 四、测试用例编写指南

#### 1. 测试用例基本结构

```python
"""
测试用例文档说明
"""

import pytest
from typing import Any, Dict, List
from libs.core import TestCase

class TestExample(TestCase):
    """
    测试用例描述
    
    CaseNumber: test_example_001
    RunLevel: Level 1
    EnvType: integration
    
    CaseName: 示例测试用例
    PreCondition: 测试前置条件
    TestStep: 测试步骤说明
    ExpectedResult: 预期结果
    Author: 作者
    """
    
    def setup_method(self):
        """测试前置设置（Legacy: preTestCase）"""
        self.logStep("Prepare test environment")
        # 初始化测试环境
    
    def test_example_001(self):
        """测试主逻辑"""
        self.logStep("Execute test step 1")
        
        # 执行测试操作
        result = self.node.run({"command": ["ls -la"], "timeout": 30})
        
        # 验证结果
        self.assertTrue(result["returnCode"] == 0, "Command execution failed")
    
    def teardown_method(self):
        """测试后置清理（Legacy: postTestCase）"""
        self.logStep("Cleanup test environment")
        # 清理测试环境
```

#### 2. 使用 pytest fixtures

```python
import pytest

def test_with_nodes(nodes, node_dict, resource):
    """使用 fixtures 注入测试资源"""
    # nodes: 节点列表
    # node_dict: 节点名称映射字典
    # resource: 资源配置字典
    
    controller = nodes[0]
    agent = nodes[1] if len(nodes) > 1 else None
    
    # 执行测试操作
    result = controller.run({"command": ["hostname"], "timeout": 10})
    assert result["returnCode"] == 0
```

#### 3. 测试标记使用

```python
import pytest

@pytest.mark.integration
@pytest.mark.virt
class TestVMMigration(TestCase):
    """虚拟机迁移测试"""
    
    @pytest.mark.slow
    def test_vm_migration_slow(self):
        """慢速迁移测试"""
        pass
    
    def test_vm_migration_fast(self):
        """快速迁移测试"""
        pass
```

***

### 五、常见问题解答

#### Q1: pytest 报错 "ModuleNotFoundError: No module named 'libs'"

**解决方案**:

```bash
# 确保已安装项目依赖
pip install -e .

# 或确保当前目录在 Python 路径中
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
pytest --resource-config=test_nodes.json
```

#### Q2: 测试报错 "Failed to connect to node"

**解决方案**:

1. 检查节点 IP 地址是否正确
2. 检查 SSH 用户名和密码是否正确
3. 检查网络连通性：

```bash
# 测试 SSH 连接
ssh root@192.168.1.100
```

1. 检查目标节点 SSH 服务状态：

```bash
# 在目标节点执行
systemctl status sshd
```

#### Q3: 测试报错 "nodes list is empty"

**解决方案**:
确保已提供正确的资源配置文件：

```bash
pytest --resource-config=test_nodes.json

# 或在测试代码中使用 resource fixture
def test_example(resource, nodes):
    assert len(nodes) > 0, "No nodes configured"
```

#### Q4: 如何查看测试覆盖率报告

**解决方案**:

```bash
# 生成 HTML 覆盖率报告
pytest --cov=libs --cov-report=html

# 打开报告
# Linux:
xdg-open htmlcov/index.html
# macOS:
open htmlcov/index.html
```

#### Q5: 如何调试失败的测试用例

**解决方案**:

```bash
# 显示详细 traceback
pytest --tb=long -v

# 只运行失败的测试
pytest --lf --tb=short

# 进入 PDB 调试器
pytest --pdb

# 打印测试执行过程中的变量
pytest -s --capture=no
```

#### Q6: 测试报错 "Empty suite" 或测试类未被pytest收集

**原因分析**:

1. **类名不符合pytest命名规范**：`python_classes = ["Test*"]` 要求类名以 `Test` 开头
2. **缺失依赖包**：如 `pandas` 未安装导致导入失败

**解决方案**:

```bash
# 检查1: 类名是否以Test开头
grep -n "^class " testcases/xxx/test_xxx.py

# 如果类名如 "memory_pooling_first_return_success_1"（不以Test开头）
# 需重命名为 "TestMemoryPoolingFirstReturnSuccess1"

# 检查2: 是否有导入错误
pytest testcases/xxx/test_xxx.py --collect-only --tb=short

# 如果看到 ImportError: No module named 'pandas'
pip install pandas
```

#### Q7: 测试报错 "'XXX' object has no attribute 'nodeagent'"

**原因分析**:

BaseCase的fixture定义在类内部（方法），pytest无法正确触发依赖注入链。

**典型错误模式**:

```python
# ❌ 错误 - fixture在类内部
class ATBaseCase(TestCase):
    @pytest.fixture(autouse=True)
    def inject_dependencies(self, resource, custom_params):
        self.resource = resource  # pytest无法正确触发
```

**正确模式**:

```python
# ✅ 正确 - fixture在类外部（独立函数）
@pytest.fixture(autouse=True)
def inject_at_basecase_dependencies(request, nodes, resource, custom_params):
    if not isinstance(request.instance, ATBaseCase):
        return
    request.instance.nodes = nodes
    # ...

class ATBaseCase(TestCase):
    # 无fixture方法
```

**解决方案**:

1. 检查BaseCase的fixture是否定义在类外部
2. 确认fixture已导入到 `testcases/conftest.py`
3. 参考 `libs/core/basecase/rackcontrol/cm_basecase.py` 的正确模式

```bash
# 检查fixture是否导入到conftest
grep "inject.*basecase.*dependencies" testcases/conftest.py

# 如果缺少ATBaseCase的fixture导入，添加：
# from libs.core.basecase.ubturbo.at_basecase import inject_at_basecase_dependencies
```

### 六、项目结构说明

```
ubs-test/
├── libs/                    # 测试库核心代码
│   ├── core/               # 核心框架（TestCase, fixtures, hook_runner, basecase）
│   ├── utils/              # 工具函数（env_config, node_adapter, logger_compat）
│   ├── host/               # Linux SSH 节点封装
│   └── modules/            # 测试 AW
│       ├── ubsmem/         # UBSMem AW
│       ├── hcom/           # HCOM AW
│       ├── ubturbo/        # UBTurbo AW
│       ├── ubsocket/       # UBSocket AW
│       └── rackcontrol/    # RackControl AW
├── conf/                   # 默认配置目录
├── testcases/              # 测试用例目录
│   ├── ubscomm/               # 通信测试用例
│       ├── hcom/         		# HCOM 测试用例
│       ├── ubsocket/          # UBSocket 测试用例
│   ├── ubse/               # UBSE 测试用例
│   ├── ubturbo/            # 内存池化等测试用例
│   └── ubsmem/             # UBSMem 测试用例
├── tests/                  # 单元测试
├── scripts/                # 迁移脚本
├── tools/                  # 工具目录
├── docs/                   # 文档目录
├── examples/               # 使用示例
```

***

### 七、快速验证命令汇总

在全新环境中，按照以下步骤快速验证：

```bash
# 1. 克隆项目
git clone https://github.com/example/ubs-test.git && cd ubs-test

# 2. 创建虚拟环境
python3 -m venv .venv && source .venv/bin/activate

# 3. 安装依赖
pip install -e .

# 4. 创建节点配置文件（替换为实际节点信息）
cat > test_nodes.json << 'EOF'
{
  "hosts": {
    "1": {"ip": "192.168.1.100", "port": 22, "user": "root", "password": "your_password", "nodeId": "Node0"}
  },
  "devices": {},
  "global": {"testbed_name": "testbed"}
}
EOF

# 5. 验证配置
python3 -c "from libs.utils.env_config import load_resource_config; c=load_resource_config('test_nodes.json'); print(f'OK: {len(c[\"hosts\"])} nodes')"

# 6. 执行单元测试（无需节点配置）
pytest tests/ -v

# 7. 执行集成测试（需要节点配置）
pytest --resource-config=test_nodes.json testcases/ -v -m integration

# 8. 查看测试覆盖率报告
pytest --cov=libs --cov-report=html && xdg-open htmlcov/index.html
```

***

## 开发环境

- Python 3.9+
- pytest 7.4.0+
- paramiko 3.0.0+
- Black 23.7.0+（代码格式化）
- isort 5.12.0+（导入排序）
- mypy 1.5.0+（类型检查）

## 代码规范

```bash
# 格式化代码
black .
isort .

# 类型检查
mypy libs/

# 运行 pre-commit 检查
pre-commit run --all-files
```

## 贡献指南

我们欢迎所有形式的贡献！请查看 [CONTRIBUTING.md](CONTRIBUTING.md) 了解详细的贡献指南。

### 贡献流程

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

## 许可证

本项目采用 MulanPSL2 许可证 - 详见 [LICENSE](LICENSE) 文件。

## 联系方式

- 作者: Jinhui Tong
- 项目主页: <https://gitcode.com/openeuler/ubs-test>
- 问题反馈: <https://gitcode.com/openeuler/ubs-test/issues>

## 致谢

感谢所有为本项目做出贡献的开发者！
