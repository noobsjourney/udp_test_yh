import socket
import struct
import time
import threading
from PyQt5.QtCore import QObject, pyqtSignal, QThreadPool, QRunnable
from typing import Dict, List, Tuple, Optional, Union, Any
import logging
import queue
import random

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("UDPProtocol")

class UDPPacket:
    """UDP数据包基类"""
    HEADER_FORMAT = "!BBHII"  # 包类型(1B), ack位(1B), 校验(2B), model_id(4B), node_id(4B)
    HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
    
    # 包类型
    HEADER_PACKET = 0
    DATA_PACKET = 1
    FULL_PACKET = 2
    ACK_PACKET = 3
    
    # ACK状态
    ACK_NORMAL = 0
    ACK_CONFIRM = 1
    ACK_RETRANSMIT = 2
    
    def __init__(self, packet_type: int, ack_status: int, model_id: int, node_id: int):
        self.packet_type = packet_type
        self.ack_status = ack_status
        self.model_id = model_id
        self.node_id = node_id
        self.checksum = 0
        self.sequence_num = 0
        self.data = b''
    
    def build(self) -> bytes:
        """构建数据包"""
        header = struct.pack(
            self.HEADER_FORMAT,
            self.packet_type,
            self.ack_status,
            self.checksum,
            self.model_id,
            self.node_id
        )
        return header + self.data
    
    def calculate_checksum(self) -> int:
        """计算校验和"""
        data = self.build()[:self.HEADER_SIZE - 2] + self.data
        return sum(data) & 0xFFFF
    
    def verify_checksum(self) -> bool:
        """验证校验和"""
        return self.checksum == self.calculate_checksum()
    
    @classmethod
    def parse(cls, data: bytes) -> Optional['UDPPacket']:
        """解析数据包"""
        if len(data) < cls.HEADER_SIZE:
            return None
        
        try:
            header = data[:cls.HEADER_SIZE]
            packet_type, ack_status, checksum, model_id, node_id = struct.unpack(cls.HEADER_FORMAT, header)
            
            # 根据包类型创建不同的包对象
            if packet_type == cls.HEADER_PACKET:
                packet = HeaderPacket(model_id, node_id)
            elif packet_type == cls.DATA_PACKET:
                packet = DataPacket(model_id, node_id)
            elif packet_type == cls.FULL_PACKET:
                packet = FullPacket(model_id, node_id)
            elif packet_type == cls.ACK_PACKET:
                packet = ACKPacket(model_id, node_id)
            else:
                return None
                
            packet.packet_type = packet_type
            packet.ack_status = ack_status
            packet.checksum = checksum
            packet.data = data[cls.HEADER_SIZE:]
            
            if not packet.verify_checksum():
                logger.warning("Checksum verification failed")
                return None
                
            return packet
        except struct.error:
            return None


class HeaderPacket(UDPPacket):
    """包头包"""
    HEADER_FORMAT = UDPPacket.HEADER_FORMAT + "III"  # 增加数据长度(4B), 分包数(4B), 包序列号(4B)
    HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
    
    def __init__(self, model_id: int, node_id: int):
        super().__init__(self.HEADER_PACKET, self.ACK_NORMAL, model_id, node_id)
        self.total_length = 0
        self.packet_count = 0
        self.sequence_num = 0
    
    def build(self) -> bytes:
        header = struct.pack(
            self.HEADER_FORMAT,
            self.packet_type,
            self.ack_status,
            self.checksum,
            self.model_id,
            self.node_id,
            self.total_length,
            self.packet_count,
            self.sequence_num
        )
        return header
    
    def calculate_checksum(self) -> int:
        data = struct.pack(
            "!BBIIIII",
            self.packet_type,
            self.ack_status,
            self.model_id,
            self.node_id,
            self.total_length,
            self.packet_count,
            self.sequence_num
        )
        return sum(data) & 0xFFFF


class DataPacket(UDPPacket):
    """数据包"""
    HEADER_FORMAT = UDPPacket.HEADER_FORMAT + "I"  # 增加包序列号(4B)
    HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
    MAX_DATA_SIZE = 1400  # 最大数据长度
    
    def __init__(self, model_id: int, node_id: int):
        super().__init__(self.DATA_PACKET, self.ACK_NORMAL, model_id, node_id)
        self.sequence_num = 0
    
    def build(self) -> bytes:
        header = struct.pack(
            self.HEADER_FORMAT,
            self.packet_type,
            self.ack_status,
            self.checksum,
            self.model_id,
            self.node_id,
            self.sequence_num
        )
        return header + self.data
    
    def calculate_checksum(self) -> int:
        data = struct.pack(
            "!BBIII",
            self.packet_type,
            self.ack_status,
            self.model_id,
            self.node_id,
            self.sequence_num
        ) + self.data
        return sum(data) & 0xFFFF


class FullPacket(UDPPacket):
    """整体包（包头+数据）"""
    HEADER_FORMAT = UDPPacket.HEADER_FORMAT + "III"  # 增加数据长度(4B), 分包数(4B), 包序列号(4B)
    HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
    
    def __init__(self, model_id: int, node_id: int):
        super().__init__(self.FULL_PACKET, self.ACK_NORMAL, model_id, node_id)
        self.total_length = 0
        self.packet_count = 0
        self.sequence_num = 0
    
    def build(self) -> bytes:
        header = struct.pack(
            self.HEADER_FORMAT,
            self.packet_type,
            self.ack_status,
            self.checksum,
            self.model_id,
            self.node_id,
            self.total_length,
            self.packet_count,
            self.sequence_num
        )
        return header + self.data
    
    def calculate_checksum(self) -> int:
        data = struct.pack(
            "!BBIIIII",
            self.packet_type,
            self.ack_status,
            self.model_id,
            self.node_id,
            self.total_length,
            self.packet_count,
            self.sequence_num
        ) + self.data
        return sum(data) & 0xFFFF


class ACKPacket(UDPPacket):
    """ACK确认包"""
    HEADER_FORMAT = UDPPacket.HEADER_FORMAT + "I"  # 增加包序列号(4B)
    HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
    
    def __init__(self, model_id: int, node_id: int):
        super().__init__(self.ACK_PACKET, self.ACK_CONFIRM, model_id, node_id)
        self.sequence_num = 0
    
    def build(self) -> bytes:
        header = struct.pack(
            self.HEADER_FORMAT,
            self.packet_type,
            self.ack_status,
            self.checksum,
            self.model_id,
            self.node_id,
            self.sequence_num
        )
        return header
    
    def calculate_checksum(self) -> int:
        data = struct.pack(
            "!BBIII",
            self.packet_type,
            self.ack_status,
            self.model_id,
            self.node_id,
            self.sequence_num
        )
        return sum(data) & 0xFFFF


class UDPTransmitter(QObject):
    """UDP可靠传输协议实现"""
    transmission_complete = pyqtSignal(int, int, bytes, tuple)  # model_id, node_id, data, source_addr
    transmission_failed = pyqtSignal(int, int, str, tuple)      # model_id, node_id, error, source_addr
    ack_received = pyqtSignal(int, int, int, tuple)             # model_id, node_id, sequence_num, source_addr
    
    def __init__(self, bind_host: str = '0.0.0.0', bind_port: int = 0):
        """
        初始化UDP传输器
        :param bind_host: 绑定的主机地址
        :param bind_port: 绑定的端口号 (0表示随机端口)
        """
        super().__init__()
        self.bind_host = bind_host
        self.bind_port = bind_port
        
        # 创建UDP套接字
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((bind_host, bind_port))
        self.sock.settimeout(0.1)  # 设置短超时，避免阻塞
        actual_port = self.sock.getsockname()[1]
        logger.info(f"UDPTransmitter bound to {bind_host}:{actual_port}")
        
        # 接收线程
        self.recv_thread = threading.Thread(target=self._recv_loop, daemon=True)
        self.recv_running = True
        self.recv_thread.start()
        
        # 发送队列
        self.send_queue = queue.Queue()
        self.sequence_counter = random.randint(1, 0xFFFF)  # 随机初始序列号
        
        # 传输状态
        self.pending_transmissions: Dict[Tuple, Dict] = {}  # key: (model_id, node_id, seq_num)
        self.pending_receptions: Dict[Tuple, Dict] = {}     # key: (source_addr, model_id, node_id, seq_num)
        self.lock = threading.Lock()
        
        # 启动发送线程
        self.send_thread = threading.Thread(target=self._send_loop, daemon=True)
        self.send_thread.start()
        
        logger.info("UDPTransmitter initialized")
    
    def _recv_loop(self):
        """接收循环 - 处理所有传入的数据包"""
        while self.recv_running:
            try:
                data, addr = self.sock.recvfrom(65535)
                packet = UDPPacket.parse(data)
                if not packet:
                    logger.warning(f"Invalid packet received from {addr}")
                    continue
                
                logger.debug(f"Received packet type={packet.packet_type} from {addr}")
                
                if packet.packet_type == UDPPacket.ACK_PACKET:
                    self._handle_ack_packet(packet, addr)
                elif packet.packet_type == UDPPacket.HEADER_PACKET:
                    self._handle_header_packet(packet, addr)
                elif packet.packet_type == UDPPacket.DATA_PACKET:
                    self._handle_data_packet(packet, addr)
                elif packet.packet_type == UDPPacket.FULL_PACKET:
                    self._handle_full_packet(packet, addr)
            except socket.timeout:
                pass
            except Exception as e:
                logger.error(f"Error in recv loop: {str(e)}", exc_info=True)
    
    def _handle_ack_packet(self, packet: ACKPacket, addr: Tuple[str, int]):
        """处理ACK包 - 更新传输状态"""
        key = (packet.model_id, packet.node_id, packet.sequence_num)
        
        with self.lock:
            if key in self.pending_transmissions:
                transmission = self.pending_transmissions[key]
                
                if packet.ack_status == UDPPacket.ACK_CONFIRM:
                    # 确认成功
                    logger.info(f"ACK confirmed for {key} from {addr}")
                    del self.pending_transmissions[key]
                    self.ack_received.emit(packet.model_id, packet.node_id, packet.sequence_num, addr)
                elif packet.ack_status == UDPPacket.ACK_RETRANSMIT:
                    # 需要重传
                    logger.warning(f"Retransmission requested for {key} from {addr}")
                    transmission['retry_count'] += 1
                    transmission['last_sent'] = 0  # 立即重传
                else:
                    logger.warning(f"Unknown ACK status: {packet.ack_status} for {key} from {addr}")
            else:
                logger.debug(f"Received ACK for unknown transmission {key} from {addr}")
    
    def _handle_header_packet(self, packet: HeaderPacket, addr: Tuple[str, int]):
        """处理包头包 - 初始化接收状态"""
        # 创建接收状态键
        recv_key = (addr, packet.model_id, packet.node_id, packet.sequence_num)
        
        # 发送ACK确认
        self._send_ack(packet.model_id, packet.node_id, packet.sequence_num, addr)
        
        with self.lock:
            # 初始化接收状态
            self.pending_receptions[recv_key] = {
                'source_addr': addr,
                'total_length': packet.total_length,
                'packet_count': packet.packet_count,
                'received_packets': {},
                'last_received': time.time()
            }
            logger.info(f"Header received for {recv_key}, expecting {packet.packet_count} packets")
    
    def _handle_data_packet(self, packet: DataPacket, addr: Tuple[str, int]):
        """处理数据包 - 存储数据并发送ACK"""
        # 创建接收状态键
        recv_key = (addr, packet.model_id, packet.node_id, packet.sequence_num)
        
        # 发送ACK
        self._send_ack(packet.model_id, packet.node_id, packet.sequence_num, addr)
        
        with self.lock:
            if recv_key in self.pending_receptions:
                reception = self.pending_receptions[recv_key]
                
                # 存储数据包
                reception['received_packets'][packet.sequence_num] = packet.data
                reception['last_received'] = time.time()
                
                logger.debug(f"Received data packet {packet.sequence_num} for {recv_key}")
                
                # 检查是否接收完成
                if len(reception['received_packets']) == reception['packet_count']:
                    self._assemble_data(recv_key, reception)
            else:
                logger.warning(f"Received data packet for unknown header {recv_key}")
    
    def _handle_full_packet(self, packet: FullPacket, addr: Tuple[str, int]):
        """处理整体包 - 直接完成传输"""
        # 发送ACK确认
        self._send_ack(packet.model_id, packet.node_id, packet.sequence_num, addr)
        
        # 处理数据
        self.transmission_complete.emit(
            packet.model_id, 
            packet.node_id, 
            packet.data,
            addr
        )
        logger.info(f"Full packet received from {addr}, size: {len(packet.data)}")
    
    def _send_ack(self, model_id: int, node_id: int, seq_num: int, dest_addr: Tuple[str, int]):
        """发送ACK包到指定地址"""
        ack = ACKPacket(model_id, node_id)
        ack.sequence_num = seq_num
        ack.ack_status = UDPPacket.ACK_CONFIRM
        ack.checksum = ack.calculate_checksum()
        
        try:
            self.sock.sendto(ack.build(), dest_addr)
            logger.debug(f"Sent ACK for {model_id}-{node_id}-{seq_num} to {dest_addr}")
        except Exception as e:
            logger.error(f"Failed to send ACK to {dest_addr}: {str(e)}")
    
    def _assemble_data(self, recv_key: Tuple, reception: Dict):
        """组装接收到的数据并完成传输"""
        # 按序列号排序数据包
        sorted_packets = sorted(reception['received_packets'].items())
        data = b''.join(packet_data for _, packet_data in sorted_packets)
        
        # 验证数据长度
        if len(data) != reception['total_length']:
            logger.error(f"Data length mismatch for {recv_key}: expected {reception['total_length']}, got {len(data)}")
            return
        
        # 发射完成信号
        _, model_id, node_id, seq_num = recv_key
        self.transmission_complete.emit(model_id, node_id, data, reception['source_addr'])
        
        # 清理接收状态
        with self.lock:
            del self.pending_receptions[recv_key]
        
        logger.info(f"Data assembly complete for {recv_key}, size: {len(data)}")
    
    def _send_loop(self):
        """发送循环 - 处理发送队列和重传"""
        while self.recv_running:
            # 处理发送队列
            try:
                task = self.send_queue.get(timeout=0.5)
                self._send_data(task['data'], task['model_id'], task['node_id'], task['dest_addr'])
            except queue.Empty:
                pass
            
            # 检查重传
            self._check_retransmissions()
    
    def _send_data(self, data: bytes, model_id: int, node_id: int, dest_addr: Tuple[str, int]):
        """发送数据到指定地址"""
        # 分配序列号
        with self.lock:
            self.sequence_counter = (self.sequence_counter + 1) & 0xFFFFFFFF
            sequence_num = self.sequence_counter
            key = (model_id, node_id, sequence_num)
        
        if len(data) <= FullPacket.MAX_DATA_SIZE:
            # 使用整体包
            packet = FullPacket(model_id, node_id)
            packet.sequence_num = sequence_num
            packet.data = data
            packet.total_length = len(data)
            packet.packet_count = 1
            packet.checksum = packet.calculate_checksum()
            
            self._queue_for_transmission(key, packet, data, dest_addr)
            logger.info(f"Queued full packet for {key} to {dest_addr}, size: {len(data)}")
        else:
            # 分包传输
            # 1. 发送包头
            header = HeaderPacket(model_id, node_id)
            header.sequence_num = sequence_num
            header.total_length = len(data)
            header.packet_count = (len(data) + DataPacket.MAX_DATA_SIZE - 1) // DataPacket.MAX_DATA_SIZE
            header.checksum = header.calculate_checksum()
            
            self._queue_for_transmission(key, header, data, dest_addr)
            logger.info(f"Queued header for {key} to {dest_addr}, total packets: {header.packet_count}")
            
            # 2. 发送数据包
            packet_num = 0
            for i in range(0, len(data), DataPacket.MAX_DATA_SIZE):
                chunk = data[i:i+DataPacket.MAX_DATA_SIZE]
                data_packet = DataPacket(model_id, node_id)
                data_packet.sequence_num = sequence_num
                data_packet.data = chunk
                data_packet.checksum = data_packet.calculate_checksum()
                
                # 每个数据包使用相同的序列号但不同的包号
                sub_key = (model_id, node_id, sequence_num, packet_num)
                self._queue_for_transmission(sub_key, data_packet, chunk, dest_addr)
                packet_num += 1
                logger.debug(f"Queued data packet {packet_num} for {key} to {dest_addr}")
    
    def _queue_for_transmission(self, key: Tuple, packet: UDPPacket, data: bytes, dest_addr: Tuple[str, int]):
        """将数据包加入传输队列"""
        with self.lock:
            self.pending_transmissions[key] = {
                'packet': packet,
                'data': data,
                'dest_addr': dest_addr,  # 存储目标地址
                'retry_count': 0,
                'last_sent': 0,  # 0表示需要立即发送
                'sent': False
            }
    
    def _check_retransmissions(self):
        """检查需要重传的数据包"""
        now = time.time()
        retransmit_keys = []
        
        with self.lock:
            for key, transmission in list(self.pending_transmissions.items()):
                # 首次发送
                if not transmission['sent']:
                    retransmit_keys.append(key)
                    transmission['sent'] = True
                    transmission['last_sent'] = now
                    continue
                
                # 检查超时（1秒）
                if now - transmission['last_sent'] > 1.0:
                    if transmission['retry_count'] < 3:
                        retransmit_keys.append(key)
                    else:
                        # 重传超过3次，传输失败
                        logger.error(f"Transmission failed after 3 retries: {key}")
                        model_id, node_id, *_ = key
                        self.transmission_failed.emit(
                            model_id, 
                            node_id, 
                            "Max retries exceeded",
                            transmission['dest_addr']
                        )
                        del self.pending_transmissions[key]
        
        # 重传数据包
        for key in retransmit_keys:
            transmission = self.pending_transmissions[key]
            packet = transmission['packet']
            try:
                self.sock.sendto(packet.build(), transmission['dest_addr'])
                transmission['last_sent'] = time.time()
                transmission['retry_count'] += 1
                logger.debug(f"Sent packet (retry {transmission['retry_count']}) to {transmission['dest_addr']}: {key}")
            except Exception as e:
                logger.error(f"Failed to send packet to {transmission['dest_addr']}: {str(e)}")
    
    def send_to(self, model_id: int, node_id: int, data: bytes, dest_addr: Tuple[str, int]):
        """发送数据到指定地址"""
        self.send_queue.put({
            'model_id': model_id,
            'node_id': node_id,
            'data': data,
            'dest_addr': dest_addr
        })
    
    def get_local_addr(self) -> Tuple[str, int]:
        """获取本地绑定地址"""
        return self.sock.getsockname()
    
    def close(self):
        """关闭传输器"""
        self.recv_running = False
        if self.sock:
            self.sock.close()
        logger.info("UDPTransmitter closed")


class UDPSendTask(QRunnable):
    """UDP发送任务"""
    def __init__(self, transmitter: UDPTransmitter, model_id: int, node_id: int, 
                 data: bytes, dest_addr: Tuple[str, int]):
        super().__init__()
        self.transmitter = transmitter
        self.model_id = model_id
        self.node_id = node_id
        self.data = data
        self.dest_addr = dest_addr
    
    def run(self):
        self.transmitter.send_to(self.model_id, self.node_id, self.data, self.dest_addr)


class UDPNetworkManager(QObject):
    """UDP网络管理器"""
    dataReceived = pyqtSignal(int, int, bytes, tuple)  # model_id, node_id, data, source_addr
    transmissionFailed = pyqtSignal(int, int, str, tuple)  # model_id, node_id, error, dest_addr
    
    def __init__(self, bind_host: str = '0.0.0.0', bind_port: int = 0):
        super().__init__()
        self.transmitter = UDPTransmitter(bind_host, bind_port)
        self.transmitter.transmission_complete.connect(self._on_data_received)
        self.transmitter.transmission_failed.connect(self._on_transmission_failed)
        self.pool = QThreadPool.globalInstance()
    
    def send_to(self, model_id: int, node_id: int, data: bytes, dest_addr: Tuple[str, int]):
        """发送数据到指定地址"""
        task = UDPSendTask(self.transmitter, model_id, node_id, data, dest_addr)
        self.pool.start(task)
    
    def get_local_addr(self) -> Tuple[str, int]:
        """获取本地绑定地址"""
        return self.transmitter.get_local_addr()
    
    def _on_data_received(self, model_id: int, node_id: int, data: bytes, source_addr: Tuple[str, int]):
        """处理接收到的数据"""
        self.dataReceived.emit(model_id, node_id, data, source_addr)
    
    def _on_transmission_failed(self, model_id: int, node_id: int, error: str, dest_addr: Tuple[str, int]):
        """处理传输失败"""
        self.transmissionFailed.emit(model_id, node_id, error, dest_addr)
    
    def close(self):
        """关闭网络管理器"""
        self.transmitter.close()
