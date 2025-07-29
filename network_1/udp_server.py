# 虚拟机作为服务器
import sys, json
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer
from network.udp import UDPNetworkManager

"""
    实现了一个基于 UDP 协议的服务器，运行在虚拟机上。
    该服务器能够接收来自客户端的不同类型数据，并对接收情况、ACK 包、发送失败以及端口状态变化等事件进行处理。
    模块包含一个 `UDPServer` 类，用于管理 UDP 服务器的初始化、数据接收处理、ACK 包处理、发送失败处理和端口状态变化处理等操作。
"""

class UDPServer:
    def __init__(self, bind_port=60000):
        """
        初始化 UDP 服务器实例。
        
        Args:
            bind_port (int, 可选): 服务器绑定的端口号，默认为 60000。
        """
        self.app = QApplication(sys.argv)
        self.manager = UDPNetworkManager(bind_port=bind_port)
        self.transmitter = self.manager.transmitter

        print(f"✅ UDP Server started on {self.manager.get_local_addr()}")

        self.manager.dataReceived.connect(self.handle_received_data)
        self.manager.transmissionFailed.connect(self.handle_send_failure)
        self.transmitter.ack_received.connect(self.handle_ack_received)
        self.transmitter.port_status_changed.connect(self.handle_port_status_changed)

    def handle_received_data(self, modename, node_id, data, source_addr):
        """
        处理接收到的数据。
        
        尝试将接收到的数据解码为文本，如果解码成功则打印前 100 个字符，
        若文本为有效的 JSON 格式则进一步解析并打印解析后的 JSON 对象；
        若解码失败则将数据视为二进制数据并打印其十六进制表示。
        
        Args:
            modename (str): 数据所属的模块名称。
            node_id (int): 发送数据的节点 ID。
            data (bytes): 接收到的原始字节数据。
            source_addr (tuple): 数据发送方的地址，格式为 (ip, port)。
        """
        print(f"\n📥 Received from {source_addr} | Module: {modename} | Node: {node_id}")
        try:
            text = data.decode("utf-8")
            print(f"  Text: {text[:100]}{'...' if len(text) > 100 else ''}")
            try:
                obj = json.loads(text)
                print("  JSON Parsed:")
                print(json.dumps(obj, indent=2))
            except: pass
        except:
            print(f"  Binary ({len(data)} bytes): {data.hex(' ')[:48]}...")

    def handle_ack_received(self, modename, node_id, seq, source_addr):
        """
        处理接收到的 ACK 包。
        
        打印接收到的 ACK 包的相关信息，包括模块名称、节点 ID、序列号和发送方地址。
        
        Args:
            modename (str): 模块名称。
            node_id (int): 节点 ID。
            seq (int): 序列号。
            source_addr (tuple): 发送 ACK 包的源地址，格式为 (ip, port)。
        """
        print(f"\n✅ ACK Received: {modename}@{node_id}, Seq: {seq}, From: {source_addr}")

    def handle_send_failure(self, modename, node_id, error_msg, dest_addr):
        """
        处理发送失败的情况。
        
        打印发送失败的相关信息，包括目标模块名称、节点 ID、目标地址和错误信息。
        
        Args:
            modename (str): 目标模块名称。
            node_id (int): 目标节点 ID。
            error_msg (str): 发送失败的错误信息。
            dest_addr (tuple): 目标地址，格式为 (ip, port)。
        """
        print(f"\n❌ Send Failed: {modename}@{node_id} -> {dest_addr} | Error: {error_msg}")

    def handle_port_status_changed(self, addr, online):
        """
        处理端口状态变化的通知。
        
        打印端口状态变化的信息，包括端口地址和在线状态（在线或离线）。
        
        Args:
            addr (tuple): 端口对应的地址，格式为 (ip, port)。
            online (bool): 端口是否在线，True 表示在线，False 表示离线。
        """
        print(f"\n🌐 Port Status: {addr} -> {'Online' if online else 'Offline'}")

    def run(self):
        """
        运行 UDP 服务器应用程序，启动 Qt 应用的事件循环。
        """
        self.app.exec_()

if __name__ == "__main__":
    server = UDPServer(bind_port=60000)
    server.run()
