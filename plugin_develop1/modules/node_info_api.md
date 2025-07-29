# NodeInfo API 文档

## 类概述
管理节点配置信息，提供节点标识生成、状态管理和持久化存储功能

## 属性
- `node_id: int` 只读节点ID（初始化后不可修改）
- `node_name: str` 可修改的节点名称（2-32字符）
- `IP: str` 节点当前IP地址

## 方法列表

### `__init__()`
初始化节点信息，自动加载配置文件或创建默认配置

### `set_node_info(node_id: int, node_name: str)`
**参数**:
- `node_id` - 必须为大于0的整数（仅首次设置有效）
- `node_name` - 2-32个字符的节点名称

### `get_node_info() -> Dict`
**返回**: 包含完整节点信息的字典
```python
{
    "node_id": 12345,
    "node_name": "Main_Server",
    "online": True,
    "ip": "192.168.1.100",
    "generate_id": "sha256_hash_string"
}
```

### `save_node_info()`
将当前节点配置持久化到 node.cfg 文件

## 使用示例

### 基础初始化
```python
node = NodeInfo()
print(node.get_node_info())
# 输出：初始默认配置信息
```

### 配置新节点
```python
try:
    node.set_node_info(1001, "Edge_Node_01")
    node.save_node_info()
except ValueError as e:
    print(f"配置失败: {str(e)}")
```

### 状态管理
```python
# 上线节点
node.set_online()
print(node.nodeIsOnline)  # 输出: True

# 下线节点
node.set_offline()
print(node.nodeIsOnline)  # 输出: False
```

### 网络配置
```python
node.set_ip("192.168.1.150")
print(node.IP)  # 输出: 192.168.1.150
```