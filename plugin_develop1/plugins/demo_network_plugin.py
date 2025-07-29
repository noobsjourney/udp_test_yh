# demo_network_plugin.py
import sys
import os

# 计算项目根目录绝对路径
_project_root = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")
)
sys.path.insert(0, _project_root)  # 插入到搜索路径最前

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 添加项目根目录到路径

from modules.service_bus import CoreServiceBus

class NetworkSenderPlugin:
    __plugin_metadata__ = {
        "name": "network_sender",
        "version": "1.2.0",
        "author": "MHX Team",
        "allowed_apis": ["network"]  # 需要网络API权限
    }

    def __init__(self, api_gateway):
        self.api = api_gateway
        self._register_signals()

    def _register_signals(self):
        # 自动注册网络信号
        CoreServiceBus.instance().get_network_signal("net_out").connect(
            self._handle_send_result
        )

    def _handle_send_result(self, target_id: str, status: bool):
        print(f"数据送达 {target_id}: {'成功' if status else '失败'}")


class NetworkReceiverPlugin:
    __plugin_metadata__ = {
        "name": "network_receiver",
        "version": "1.1.0",
        "author": "MHX Team",
        "allowed_apis": ["network"]  # 需要接收网络数据能力
    }

    def __init__(self):
        self.core_bus = CoreServiceBus.instance()
        self._bind_network()

    def _bind_network(self):
        self.core_bus.get_network_signal("net_in").connect(
            self._process_incoming_data
        )

    def _process_incoming_data(self, sender: str, data: bytes):
        print(f"来自 {sender} 的新数据包 [{len(data)}字节]")
        # 触发业务处理流水线
        self._data_pipeline(data)

    def _data_pipeline(self, raw: bytes):
        """数据解析处理流水线"""
        # 步骤1：协议校验
        if not raw.startswith(b"\xA0\xB0"):
            print("协议头校验失败")
            return

        # 步骤2：数据解密（示例）
        decrypted = raw[2:]  # 实际应替换为真实解密逻辑

        # 步骤3：业务处理
        print(f"处理有效载荷: {decrypted.decode()}")
