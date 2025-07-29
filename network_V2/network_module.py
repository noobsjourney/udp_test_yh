import socket
import threading
from PyQt5.QtCore import QObject, pyqtSignal, QRunnable, QThreadPool
from typing import Optional, Union
import time

class TCPClientV2(QObject):
    """
    TCP 客户端 V2：支持接收线程、连接状态、主动接收 + 信号回传
    """
    received = pyqtSignal(dict)        # 自动解包后触发
    status_changed = pyqtSignal(str)   # 状态变化信号：DISCONNECTED, CONNECTING, CONNECTED, ERROR

    def __init__(self, node_id="default_node", timeout=5):
        super().__init__()
        self.sock = None
        self.node_id = node_id
        self.timeout = timeout

        self._recv_thread = None
        self._recv_running = False
        self._lock = threading.Lock()

        self.status = "DISCONNECTED"
        self.serial_number = 0

        self.modenameID = {"node": 0, "database": 1, "plugin": 2}
        self.modename = {v: k for k, v in self.modenameID.items()}

    def connect(self, host: str, port: int) -> bool:
        self._update_status("CONNECTING")
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(self.timeout)
            self.sock.connect((host, port))
            self._update_status("CONNECTED")
            self._start_recv_thread()
            return True
        except Exception as e:
            self._update_status("ERROR")
            print(f"[连接失败] {e}")
            return False

    def _start_recv_thread(self):
        if self._recv_thread and self._recv_thread.is_alive():
            return
        self._recv_running = True
        self._recv_thread = threading.Thread(target=self._recv_loop, daemon=True)
        self._recv_thread.start()

    def _recv_loop(self):
        try:
            buffer = bytearray()
            while self._recv_running:
                try:
                    packet = self.sock.recv(4096)
                    if not packet:
                        self._update_status("DISCONNECTED")
                        break
                    buffer.extend(packet)

                    while True:
                        header_start = buffer.find(b'TRae')
                        if header_start == -1:
                            break
                        if len(buffer) < header_start + 12:
                            break
                        del buffer[:header_start]

                        ptr = 4
                        ptype = buffer[ptr]
                        ptr += 1
                        serial_num = int.from_bytes(buffer[ptr:ptr+4], 'big')
                        ptr += 4
                        modename_id = buffer[ptr]
                        ptr += 1
                        node_id_len = buffer[ptr]
                        ptr += 1

                        if len(buffer) < ptr + node_id_len + 6:
                            break

                        node_id = buffer[ptr:ptr+node_id_len].decode()
                        ptr += node_id_len
                        data_len = int.from_bytes(buffer[ptr:ptr+4], 'big')
                        ptr += 4
                        checksum = int.from_bytes(buffer[ptr:ptr+2], 'big')
                        ptr += 2

                        total_len = ptr + data_len
                        if len(buffer) < total_len:
                            break

                        payload = buffer[ptr:ptr+data_len]
                        del buffer[:total_len]

                        actual_checksum = sum(payload) & 0xFFFF
                        if actual_checksum != checksum:
                            print("[校验失败]")
                            continue

                        info = {
                            "Ptype": ptype,
                            "serialNumber": serial_num,
                            "modenameID": modename_id,
                            "nodeID": node_id,
                            "payload": payload
                        }
                        self.received.emit(info)
                except socket.timeout:
                    continue
                except Exception as e:
                    self._update_status("ERROR")
                    print(f"[接收线程异常] {e}")
                    break
        finally:
            self._update_status("DISCONNECTED")

    def send(self, data: Union[str, bytes], modename: str = "node") -> bool:
        with self._lock:
            try:
                if isinstance(data, str):
                    data = data.encode("utf-8")
                header = self._build_header(0, modename, data)
                self.sock.sendall(header + data)
                self.serial_number += 1
                return True
            except Exception as e:
                print(f"[发送失败] {e}")
                self._update_status("ERROR")
                return False

    def _build_header(self, ptype: int, modename: str, data: bytes) -> bytes:
        magic = b'TRae'
        serial = self.serial_number.to_bytes(4, 'big')
        mid = self.modenameID.get(modename, 0).to_bytes(1, 'big')
        nid = len(self.node_id).to_bytes(1, 'big') + self.node_id.encode()
        data_len = len(data).to_bytes(4, 'big')
        checksum = (sum(data) & 0xFFFF).to_bytes(2, 'big')
        return magic + bytes([ptype]) + serial + mid + nid + data_len + checksum

    def close(self):
        self._recv_running = False
        if self.sock:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
                self.sock.close()
            except:
                pass
        self._update_status("DISCONNECTED")

    def _update_status(self, new_status: str):
        if self.status != new_status:
            self.status = new_status
            self.status_changed.emit(new_status)

    def is_connected(self) -> bool:
        return self.status == "CONNECTED"

class SendTask(QRunnable):
    def __init__(self, client: TCPClientV2, data, modename):
        super().__init__()
        self.client = client
        self.data = data
        self.modename = modename

    def run(self):
        self.client.send(self.data, self.modename)

class NetworkDispatcher(QObject):
    dataReceived = pyqtSignal(str, object)  # modename, data

    def __init__(self, client: TCPClientV2):
        super().__init__()
        self.client = client
        self.modules = {}  # modename -> callback
        self.pool = QThreadPool.globalInstance()
        self.client.received.connect(self._on_receive)

    def register_module(self, modename: str, callback):
        self.modules[modename] = callback

    def send(self, data, modename):
        task = SendTask(self.client, data, modename)
        self.pool.start(task)

    def _on_receive(self, packet):
        modename = self.client.modename.get(packet['modenameID'], "unknown")
        payload = packet["payload"]
        if modename in self.modules:
            self.modules[modename](payload)
        self.dataReceived.emit(modename, payload)
