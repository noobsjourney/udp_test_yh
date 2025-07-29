# 测试udp协议能否正常通信 
# 本机作为客户端，虚拟机作为服务器端
import sys, json
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer
from network.udp import UDPNetworkManager

"""
    实现了一个 UDP 客户端，用于与指定的服务器端进行通信。
    客户端会向服务器端发送不同类型的数据，包括文本消息、JSON 消息、二进制数据和大文件数据。
    同时，客户端会处理服务器端返回的 ACK 包、传输完成通知、端口状态变化通知以及发送失败通知。
"""

class UDPClient:
    def __init__(self, dest_ip="192.168.230.128", dest_port=60000):
        """
        初始化 UDP 客户端实例。
        
        Args:
            dest_ip (str, 可选): 目标服务器的 IP 地址，默认为 "192.168.230.128"。
            dest_port (int, 可选): 目标服务器的端口号，默认为 60000。
        """
        self.app = QApplication(sys.argv)
        self.manager = UDPNetworkManager(bind_port=0)
        self.transmitter = self.manager.transmitter
        self.dest_addr = (dest_ip, dest_port)

        print(f"✅ UDP Client started on {self.manager.get_local_addr()} -> sending to {self.dest_addr}")

        self.transmitter.ack_received.connect(self.handle_ack_received)
        self.transmitter.transmission_complete.connect(self.handle_transmission_complete)
        self.transmitter.port_status_changed.connect(self.handle_port_status_changed)
        self.manager.transmissionFailed.connect(self.handle_send_failure)

        QTimer.singleShot(1000, self.send_all_tests)
        QTimer.singleShot(10000, self.cleanup)

    def send_all_tests(self):
        """
        发送所有类型的测试数据包，包括文本消息、JSON 消息、二进制数据和大文件数据。
        """
        print("\n🚀 Sending test packets...")

        # Text message
        text_data = "Hello from client!".encode("utf-8")
        self.manager.send_to("test", 1, text_data, self.dest_addr)

        # JSON message
        json_data = json.dumps({"type": "status", "value": True}).encode("utf-8")
        self.manager.send_to("config", 2, json_data, self.dest_addr)

        # Binary data
        binary_data = bytes([0xAB, 0xCD, 0xEF, 0x00, 0x11])
        self.manager.send_to("binary", 3, binary_data, self.dest_addr)

        # Large data
        large_data = ("DATA" * 300).encode("utf-8")
        self.manager.send_to("bulk", 4, large_data, self.dest_addr)

        # Check port status
        self.manager.check_port(self.dest_addr)

    def handle_ack_received(self, modename, node_id, seq, source_addr):
        """
        处理接收到的 ACK 包。
        
        Args:
            modename (str): 模块名称。
            node_id (int): 节点 ID。
            seq (int): 序列号。
            source_addr (tuple): 发送 ACK 包的源地址，格式为 (ip, port)。
        """
        print(f"\n✅ ACK Received: {modename}@{node_id}, Seq: {seq}, From: {source_addr}")

    def handle_transmission_complete(self, modename, node_id, data, addr):
        """
        处理传输完成的通知。
        
        Args:
            modename (str): 模块名称。
            node_id (int): 节点 ID。
            data (bytes): 传输的数据。
            addr (tuple): 目标地址，格式为 (ip, port)。
        """
        print(f"\n📅 Transmission Success: {modename}@{node_id} -> {addr} | Length: {len(data)}")

    def handle_port_status_changed(self, addr, online):
        """
        处理端口状态变化的通知。
        
        Args:
            addr (tuple): 端口对应的地址，格式为 (ip, port)。
            online (bool): 端口是否在线，True 表示在线，False 表示离线。
        """
        print(f"\n🌐 Port Status: {addr} -> {'Online' if online else 'Offline'}")

    def handle_send_failure(self, modename, node_id, error_msg, dest_addr):
        """
        处理发送失败的情况。
        
        Args:
            modename (str): 模块名称。
            node_id (int): 节点 ID。
            error_msg (str): 发送失败的错误信息。
            dest_addr (tuple): 目标地址，格式为 (ip, port)。
        """
        print(f"\n❌ Send Failed: {modename}@{node_id} -> {dest_addr} | Error: {error_msg}")

    def cleanup(self):
        """
        清理资源并退出应用程序。关闭网络管理器并退出 Qt 应用。
        """
        print("\n📄 Cleaning up and exiting...")
        self.manager.close()
        self.app.quit()

    def run(self):
        """
        运行 UDP 客户端应用程序，启动 Qt 应用的事件循环。
        """
        sys.exit(self.app.exec_())

if __name__ == "__main__":
    # print("helllo ")
    client = UDPClient(dest_ip="192.168.230.128", dest_port=60000)
    client.run()
