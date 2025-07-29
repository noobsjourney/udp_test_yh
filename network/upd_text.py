import sys
import json,time
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer
from udp import UDPNetworkManager  # 假设代码保存为 udp_protocol.py

class UDPDemoApp:
    def __init__(self):
        # 创建应用实例
        self.app = QApplication(sys.argv)
        
        # 初始化网络管理器（绑定到随机端口）
        self.manager = UDPNetworkManager(bind_port=0)
        local_addr = self.manager.get_local_addr()
        print(f"⚡ UDP 服务已启动 | 本地地址: {local_addr[0]}:{local_addr[1]}")
        
        # 连接信号槽
        self.manager.dataReceived.connect(self.handle_received_data)
        self.manager.transmissionFailed.connect(self.handle_send_failure)
        self.transmitter = self.manager.transmitter
        self.transmitter.ack_received.connect(self.handle_ack_packet)
        # 设置定时器发送测试数据
        #QTimer.singleShot(1000, self.send_test_data)
        self.send_data()
        # 设置退出定时器
        QTimer.singleShot(10000, self.cleanup)  # 30秒后退出
    def send_data(self):
        while True:
            self.send_test()
            self.send_test_data()
            time.sleep(5)
    def send_test(self):
        text_data = "你好，UDP协议测试！" *300 # 重复100次

        text_data = text_data.encode('utf-8')
        print(f"\n📤 发送文本消息到 node@123")
        self.manager.send_to(
            modename="node",
            node_id=123,
            data=text_data,
            dest_addr=("192.168.3.54", 60000)  # 发送到本机另一个端口
        ) 

    def send_test_data(self):
        """发送三种类型的测试数据"""
        # 1. 发送文本消息
        text_data = "你好，UDP协议测试！"  # 重复100次

        text_data = text_data.encode('utf-8')
        print(f"\n📤 发送文本消息到 node@123")
        self.manager.send_to(
            modename="node",
            node_id=123,
            data=text_data,
            dest_addr=("192.168.3.54", 60000)  # 发送到本机另一个端口
        )
        
        # 2. 发送JSON配置
        config = {
            "mode": "debug",
            "level": 3,
            "features": ["logging", "encryption"]
        }
        json_data = json.dumps(config).encode('utf-8')
        print(f"\n📤 发送JSON配置到 database@0")
        self.manager.send_to(
            modename="database",
            node_id=0,
            data=json_data,
            dest_addr=("192.168.3.54", 60000)
        )
        
        # 3. 发送二进制数据 (模拟)
        binary_data = bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A])  # PNG文件头
        print(f"\n📤 发送二进制数据到 plugin@456")
        self.manager.send_to(
            modename="plugin",
            node_id=456,
            data=binary_data,
            dest_addr=("192.168.3.54", 60000)
        )

    def handle_received_data(self, modename: str, node_id: int, data: bytes, source_addr: tuple):
        """处理接收到的数据"""
        addr_str = f"{source_addr[0]}:{source_addr[1]}"
        
        print(f"\n📥 收到来自 {addr_str} 的数据:")
        print(f"  模块: {modename}, 节点ID: {node_id}")
        
        try:
            # 尝试解码为文本
            text = data.decode('utf-8')
            print("  内容 (文本):")
            print(f"  {text}")
            
            # 尝试解析为JSON
            try:
                json_obj = json.loads(text)
                print("  内容 (JSON):")
                print(json.dumps(json_obj, indent=2))
            except:
                pass
        except UnicodeDecodeError:
            # 二进制数据
            print(f"  内容 (二进制, {len(data)}字节):")
            print(f"  十六进制: {data[:16].hex(' ')}...")
    def handle_ack_packet(self, modename: str, node_id: int, sequence_num: int, source_addr: tuple):
        """处理接收到的ACK包"""
        addr_str = f"{source_addr[0]}:{source_addr[1]}"
        ack_status_map = {
            0: "NORMAL",
            1: "CONFIRM",
            2: "RETRANSMIT"
        }
        
        # 获取ACK状态描述
        status_desc = ack_status_map.get(self.transmitter.last_ack_status, "UNKNOWN")
        
        print(f"\n🟢 收到ACK包: #{sequence_num}")
        print(f"  来自: {addr_str}")
        print(f"  模块: {modename}, 节点ID: {node_id}")
        print(f"  状态: {status_desc} ({self.transmitter.last_ack_status})")
        print(f"  时间: {time.strftime('%H:%M:%S')}")
        
    def handle_send_failure(self, modename: str, node_id: int, error: str, dest_addr: tuple):
        """处理发送失败"""
        addr_str = f"{dest_addr[0]}:{dest_addr[1]}"
        print(f"\n❌ 发送到 {modename}@{node_id} ({addr_str}) 失败: {error}")

    def cleanup(self):
        """清理资源并退出"""
        print("\n🛑 清理资源并退出...")
        self.manager.close()
        self.app.quit()

    def run(self):
        """运行应用"""
        sys.exit(self.app.exec_())

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='UDP通信测试程序')
    parser.add_argument("port", nargs='?', type=int, default=0, 
                       help="绑定端口号 (0=随机)")
    
    # 支持 -p 或 --port 参数
    parser.add_argument("-p", "--port", dest="alt_port", type=int,
                       help="绑定端口号 (别名)")
    
    args = parser.parse_args()
    
    # 确定绑定端口
    bind_port = args.port
    if args.alt_port is not None:
        bind_port = args.alt_port
    
    # 创建应用实例
    app = UDPDemoApp()
    app.manager = UDPNetworkManager(bind_port=bind_port)
    
    # 打印绑定信息
    local_addr = app.manager.get_local_addr()
    print(f"✅ 成功绑定到端口: {local_addr[1]}")
    
    app.run()

