from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QTextEdit,
    QVBoxLayout, QHBoxLayout, QLineEdit
)
from PyQt5.QtCore import Qt
from network_module import TCPClientV2, NetworkDispatcher
import sys

class NetworkUIV2(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("网络通信模块 V2 - 状态展示")
        self.resize(500, 400)

        self.client = TCPClientV2()
        self.dispatcher = NetworkDispatcher(self.client)
        self.dispatcher.register_module("node", self.on_node_data)

        self.client.status_changed.connect(self.update_status_label)
        self.dispatcher.dataReceived.connect(self.on_any_data)

        self._setup_ui()

    def _setup_ui(self):
        self.status_label = QLabel("状态：未连接")
        self.status_label.setStyleSheet("color: red")

        self.connect_btn = QPushButton("连接服务器")
        self.connect_btn.clicked.connect(self.connect_server)

        self.msg_input = QLineEdit()
        self.msg_input.setPlaceholderText("输入消息")

        self.send_btn = QPushButton("发送")
        self.send_btn.clicked.connect(self.send_message)

        self.output_box = QTextEdit()
        self.output_box.setReadOnly(True)

        hlayout = QHBoxLayout()
        hlayout.addWidget(self.msg_input)
        hlayout.addWidget(self.send_btn)

        layout = QVBoxLayout()
        layout.addWidget(self.status_label)
        layout.addWidget(self.connect_btn)
        layout.addLayout(hlayout)
        layout.addWidget(self.output_box)

        self.setLayout(layout)

    def connect_server(self):
        ok = self.client.connect("127.0.0.1", 8000)
        if ok:
            self.output_box.append("[连接成功] 客户端已连接服务器")
        else:
            self.output_box.append("[连接失败] 无法连接服务器")

    def update_status_label(self, status):
        color = {
            "CONNECTED": "green",
            "DISCONNECTED": "red",
            "CONNECTING": "orange",
            "ERROR": "darkred"
        }.get(status, "gray")
        self.status_label.setText(f"状态：{status}")
        self.status_label.setStyleSheet(f"color: {color}")

    def send_message(self):
        text = self.msg_input.text().strip()
        if text:
            self.dispatcher.send(text, "node")
            self.output_box.append(f"[发送] {text}")
            self.msg_input.clear()

    def on_node_data(self, data):
        if isinstance(data, bytes):
            data = data.decode(errors='ignore')
        self.output_box.append(f"[node模块] 收到：{data}")

    def on_any_data(self, modename, data):
        if isinstance(data, bytes):
            data = data.decode(errors='ignore')
        self.output_box.append(f"[信号] {modename}: {data}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = NetworkUIV2()
    win.show()
    sys.exit(app.exec_())
