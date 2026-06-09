# Resource Directory

资源文件存储目录，用于保存各子项目用例测试过程中依赖的资源文件。

## 目录结构

```
resource/
    ubse/                                   # UBSE子项目资源
        RackControl/
            Resource_Management/
                Mem_SDK_Management/         # SDK测试依赖文件
                    TestUbsTopoNodeLocalGet_Python_SDK.py
                    TestUbsTopoLinkList_Python_SDK.py
                    TestUbsTopoNodeList_Python_SDK.py
                    Mem_BorrowAccount_SDK_001.py
                    ...
    ubturbo/                                # UBTurbo子项目资源（待添加）
    ubsocket/                               # UBSocket子项目资源（待添加）
    hcom/                                   # HCOM子项目资源（待添加）
    rackcontrol/                            # RackControl子项目资源（待添加）
```

## 使用方式

资源文件通过pytest fixture（SDK_Hook等）上传到测试节点：

```python
@pytest.fixture(scope="package")
def sdk_hook(nodes):
    from libs.rackcontrol import rack_common
    
    rack_common.create_directory_and_upload(
        nodes=nodes,
        files=['TestUbsTopoNodeLocalGet_Python_SDK.py'],
        relative_path='resource/ubse/RackControl/Resource_Management/Mem_SDK_Management',
        dir_path='/root/manager/SDK_File'
    )
```

## 文件来源

资源文件从Legacy框架迁移：
- 原路径：`legency/testcase/{subproject}/lib/resource/`
- 新路径：`resource/{subproject}/`

## 添加新资源文件

1. 确定子项目和模块层级
2. 创建对应目录：`resource/{subproject}/{module}/`
3. 复制资源文件到目录
4. 更新对应conftest.py中的路径配置