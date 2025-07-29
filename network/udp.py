from re import S
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
    """UDP数据包基类

    定义所有UDP数据包的基本结构和通用方法，包括包头格式、校验和计算等。
    支持数据包的构建、解析和校验功能，是其他具体数据包类型的父类。
    """
    """UDP数据包基类"""
    HEADER_FORMAT = "!BBHII"  # 包类型(1B), ack位(1B), 校验(2B), model_id(4B), node_id(4B)
    HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
    
    # 包类型
    HEADER_PACKET = 0
    DATA_PACKET = 1
    FULL_PACKET = 2
    ACK_PACKET = 3
    CHECK_PORT_PACKET = 4

    
    # ACK状态
    ACK_NORMAL = 0
    ACK_CONFIRM = 1
    ACK_RETRANSMIT = 2
    ACK_CHECKPORT = 3 
    
    # modename映射
    MODENAME_MAP = {0: "node", 1: "database", 2: "plugin"}
    MODENAME_ID_MAP = {"node": 0, "database": 1, "plugin": 2}
    
    def __init__(self, packet_type: int, ack_status: int, modename: str, node_id: int):
        """初始化UDP数据包

        Args:
            packet_type: 数据包类型，可选值为HEADER_PACKET、DATA_PACKET、FULL_PACKET、ACK_PACKET
            ack_status: ACK状态，可选值为ACK_NORMAL、ACK_CONFIRM、ACK_RETRANSMIT
            modename: 模块名称，对应MODENAME_MAP中的键
            node_id: 节点ID，标识发送/接收节点
        """
        self.packet_type = packet_type
        self.ack_status = ack_status
        self.modename = modename
        self.node_id = node_id
        self.checksum = 0
        self.sequence_num = 0
        self.packet_num = 0
        self.data = b''
    
    @property
    def model_id(self) -> int:
        """将modename转换为整数ID"""
        return self.MODENAME_ID_MAP.get(self.modename, -1)
    
    def build(self) -> bytes:
        """构建完整的UDP数据包

        将包头和数据部分组合成可发送的字节流，并计算校验和。

        Returns:
            bytes: 完整的UDP数据包字节流，如果modename无效则返回空字节流
        """
        """构建数据包"""
        model_id = self.model_id
        if model_id == -1:
            logger.error(f"Invalid modename: {self.modename}")
            return b''
            
        header = struct.pack(
            self.HEADER_FORMAT,
            self.packet_type,
            self.ack_status,
            self.checksum,
            model_id,
            self.node_id
        )
        return header + self.data
    
    def calculate_checksum(self) -> int:
        """计算数据包校验和

        通过对包头和数据部分进行求和计算校验和，用于数据完整性验证。

        Returns:
            int: 16位校验和值
        """
        """计算校验和"""
        model_id = self.model_id
        if model_id == -1:
            return 0
            
        # 构建无校验和的包头
        header_without_checksum = struct.pack(
            "!BBII",
            self.packet_type,
            self.ack_status,
            model_id,
            self.node_id
        )
        data_to_sum = header_without_checksum + self.data
        return sum(data_to_sum) & 0xFFFF
    
    def verify_checksum(self) -> bool:
        """验证数据包校验和

        比较当前校验和与重新计算的校验和是否一致，判断数据是否完整。

        Returns:
            bool: 校验通过返回True，否则返回False
        """
        """验证校验和"""
        return self.checksum == self.calculate_checksum()
    
    @classmethod
    def parse(cls, data: bytes) -> Optional['UDPPacket']:
        """解析数据包 - 添加损坏标记"""
        if len(data) < cls.HEADER_SIZE:
            return None
        
        try:
            header = data[:cls.HEADER_SIZE]
            packet_type, ack_status, checksum, model_id, node_id = struct.unpack(cls.HEADER_FORMAT, header)
            
            # 将整数ID转换为modename
            modename = cls.MODENAME_MAP.get(model_id, f"unknown({model_id})")
            
            # 根据包类型创建包对象
            if packet_type == cls.FULL_PACKET:
            # FULL 包格式：通用包头 + 总长度(4) + 分包数(4) + 序列号(4) = 24字节
                full_header = data[:FullPacket.HEADER_SIZE]
                unpacked = struct.unpack(FullPacket.HEADER_FORMAT, full_header)
            
            # 创建包对象
                packet = FullPacket(modename, node_id)
                packet.sequence_num = unpacked[7]  # 序列号位置
                packet.total_length = unpacked[5]   # 总长度
                packet.packet_count = unpacked[6]   # 分包数
                packet.packet_num = unpacked[8]    # 分包号
                packet.checksum = checksum
                packet.data = data[FullPacket.HEADER_SIZE:]
                return packet
            
            elif packet_type == cls.HEADER_PACKET:
            # HEADER 包格式：通用包头 + 总长度(4) + 分包数(4) + 序列号(4) = 24字节
                header_header = data[:HeaderPacket.HEADER_SIZE]
                unpacked = struct.unpack(HeaderPacket.HEADER_FORMAT, header_header)
            
            # 创建包对象
                packet = HeaderPacket(modename, node_id)
                packet.sequence_num = unpacked[7]  # 序列号位置
                packet.total_length = unpacked[5]   # 总长度
                packet.packet_count = unpacked[6]   # 分包数
                packet.packet_num = unpacked[8]    # 分包号
                packet.checksum = checksum
                return packet
            
            elif packet_type == cls.DATA_PACKET:
            # DATA 包格式：通用包头 + 分包号(4) + 序列号(4) = 20字节
                data_header = data[:DataPacket.HEADER_SIZE]
                unpacked = struct.unpack(DataPacket.HEADER_FORMAT, data_header)
            
            # 创建包对象
                packet = DataPacket(modename, node_id)
                packet.sequence_num = unpacked[5]  # 序列号位置
                packet.packet_num = unpacked[6]    # 分包号
                packet.checksum = checksum
                packet.data = data[DataPacket.HEADER_SIZE:]
                return packet
            
            elif packet_type == cls.ACK_PACKET:
            # ACK 包格式：通用包头 + 序列号(4) = 16字节
                ack_header = data[:ACKPacket.HEADER_SIZE]
                unpacked = struct.unpack(ACKPacket.HEADER_FORMAT, ack_header)
            
            # 创建包对象
                packet = ACKPacket(modename, node_id)
                packet.sequence_num = unpacked[6]  # 序列号位置
                packet.packet_num = unpacked[5]    # 分包号
                packet.checksum = checksum
                print("ACK包解析",unpacked[5],unpacked[6],unpacked[4])
                return packet
            
            elif packet_type == cls.CHECK_PORT_PACKET:  # 新增端口检查包解析
                # CHECK_PORT 包格式：通用包头 + 包序列号(4B) + 包号(4B)
                check_port_header = data[:CheckPortPacket.HEADER_SIZE]
                unpacked = struct.unpack(CheckPortPacket.HEADER_FORMAT, check_port_header)
                
                # 创建包对象
                packet = CheckPortPacket(modename, node_id)
                packet.sequence_num = unpacked[6]  # 序列号位置
                packet.packet_num = unpacked[5]    # 包号
                packet.checksum = checksum
                return packet
            # 添加损坏标记
                #packet.is_corrupted = not packet.verify_checksum()
            
           
                
            
        except struct.error as e:
            logger.error(f"Struct error: {str(e)}")
            return None

class HeaderPacket(UDPPacket):
    """包头包

    用于传输大数据时的头部信息，包含总数据长度、分包数量和序列号等元数据。
    接收方通过此包了解后续数据传输的整体情况。
    """
    """包头包"""
    HEADER_FORMAT = UDPPacket.HEADER_FORMAT + "IIII"  # 增加数据长度(4B), 分包数(4B), 包序列号(4B),分包号(4B)固定为零
    HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
    
    def __init__(self, modename: str, node_id: int):
        super().__init__(self.HEADER_PACKET, self.ACK_NORMAL, modename, node_id)
        self.total_length = 0
        self.packet_count = 0
        self.sequence_num = 0
    
    def build(self) -> bytes:
        model_id = self.model_id
        if model_id == -1:
            return b''
            
        header = struct.pack(
            self.HEADER_FORMAT,
            self.packet_type,
            self.ack_status,
            self.checksum,
            model_id,
            self.node_id,
            self.total_length,
            self.packet_count,
            self.sequence_num,
            self.packet_num
        )
        return header
    
    def calculate_checksum(self) -> int:
        model_id = self.model_id
        if model_id == -1:
            return 0
            
        data = struct.pack(
            "!BBIIIIII",
            self.packet_type,
            self.ack_status,
            model_id,
            self.node_id,
            self.total_length,
            self.packet_count,
            self.sequence_num,
            self.packet_num
        )
        return sum(data) & 0xFFFF


class DataPacket(UDPPacket):
    """数据包

    用于传输实际业务数据，支持大数据分包传输。每个数据包包含序列号，
    接收方根据序列号重组完整数据。
    """
    """数据包"""
    HEADER_FORMAT = UDPPacket.HEADER_FORMAT + "II"  # 增加包序列号(4B)，包号
    HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
    MAX_DATA_SIZE = 1400  # 最大数据长度
    
    def __init__(self, modename: str, node_id: int):
        super().__init__(self.DATA_PACKET, self.ACK_NORMAL, modename, node_id)
        self.sequence_num = 0
        self.packet_num = 0
    
    def build(self) -> bytes:
        model_id = self.model_id
        if model_id == -1:
            return b''
            
        header = struct.pack(
            self.HEADER_FORMAT,
            self.packet_type,
            self.ack_status,
            self.checksum,
            model_id,
            self.node_id,
            self.sequence_num,
            self.packet_num,
        )
        return header + self.data
    
    def calculate_checksum(self) -> int:
        model_id = self.model_id
        if model_id == -1:
            return 0
            
        data = struct.pack(
            "!BBIIII",
            self.packet_type,
            self.ack_status,
            model_id,
            self.node_id,
            self.sequence_num,
            self.packet_num,
        ) + self.data
        return sum(data) & 0xFFFF


class FullPacket(UDPPacket):
    """整体包（包头+数据）

    用于传输小尺寸数据，将头部信息和数据合并为一个包传输，提高传输效率。
    适用于数据量较小（不超过MAX_DATA_SIZE）的场景。
    """
    """整体包（包头+数据）"""
    HEADER_FORMAT = UDPPacket.HEADER_FORMAT + "IIII"  # 增加数据长度(4B), 分包数(4B), 包序列号(4B)
    HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
    MAX_DATA_SIZE = 1400  # 最大数据长度
    
    def __init__(self, modename: str, node_id: int):
        super().__init__(self.FULL_PACKET, self.ACK_NORMAL, modename, node_id)
        self.total_length = 0
        self.packet_count = 0
        self.sequence_num = 0
    
    def build(self) -> bytes:
        model_id = self.model_id
        if model_id == -1:
            return b''
            
        header = struct.pack(
            self.HEADER_FORMAT,
            self.packet_type,
            self.ack_status,
            self.checksum,
            model_id,
            self.node_id,
            self.total_length,
            self.packet_count,
            self.sequence_num,
            self.packet_num
        )
        return header + self.data
    
    def calculate_checksum(self) -> int:
        model_id = self.model_id
        if model_id == -1:
            return 0
            
        data = struct.pack(
            "!BBIIIIII",
            self.packet_type,
            self.ack_status,
            model_id,
            self.node_id,
            self.total_length,
            self.packet_count,
            self.sequence_num,
            self.packet_num,
        ) + self.data
        return sum(data) & 0xFFFF


class ACKPacket(UDPPacket):
    """ACK确认包

    用于数据传输确认机制，通知发送方数据接收状态，支持正常确认和重传请求。
    是实现可靠UDP传输的关键组件。
    """
    """ACK确认包"""
    HEADER_FORMAT = UDPPacket.HEADER_FORMAT + "II"  # 增加包序列号(4B), 包号
    HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
    
    def __init__(self, modename: str, node_id: int):
        super().__init__(self.ACK_PACKET, self.ACK_CONFIRM, modename, node_id)
        self.sequence_num = 0
        self.packet_num = 0
  
        
    
    def build(self) -> bytes:
        model_id = self.model_id
        if model_id == -1:
            return b''
            
        header = struct.pack(
            self.HEADER_FORMAT,
            self.packet_type,
            self.ack_status,
            self.checksum,
            model_id,
            self.node_id,
            self.packet_num,
            self.sequence_num
        )
        return header
    
    def calculate_checksum(self) -> int:
        model_id = self.model_id
        if model_id == -1:
            return 0
            
        data = struct.pack(
            "!BBIIII",
            self.packet_type,
            self.ack_status,
            model_id,
            self.node_id,
            self.packet_num,
            self.sequence_num,
        )
        return sum(data) & 0xFFFF

class CheckPortPacket(UDPPacket):
    """确认端口号包

    用于确认端口号，支持正常确认和重传请求。
    是实现可靠UDP传输的关键组件。
    """
    """确认端口号包"""
    HEADER_FORMAT = UDPPacket.HEADER_FORMAT + "II"  # 增加包序列号(4B), 包号
    HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
    def __init__(self,modename: str, node_id: int):

        super().__init__(self.CHECK_PORT_PACKET, self.ACK_NORMAL, modename, node_id)
        self.sequence_num = 0
        self.packet_num = 0
    def build(self) -> bytes:
        model_id = self.model_id
        if  self.model_id == -1:
            return b''

        header=struct.pack(
            self.HEADER_FORMAT,
            self.packet_type,
            self.ack_status,
            self.checksum,
            model_id,
            self.node_id,
            self.packet_num,
            self.sequence_num,
        )
        return header
    def calculate_checksum(self) -> int:
        model_id = self.model_id
        if model_id == -1:
            return 0
            
        data = struct.pack(
            "!BBIIII",
            self.packet_type,
            self.ack_status,
            model_id,
            self.node_id,
            self.packet_num,
            self.sequence_num,
        )
        return sum(data) & 0xFFFF

class UDPTransmitter(QObject):
    """UDP可靠传输协议实现

    基于UDP协议实现可靠数据传输，支持数据包分片/重组、ACK确认机制和超时重传。
    提供数据发送队列管理和多线程处理，确保数据可靠高效传输。
    继承QObject以支持Qt信号槽机制，方便事件通知。
    """

    transmission_complete = pyqtSignal(str, int, bytes, tuple)  # modename, node_id, data, source_addr
    transmission_failed = pyqtSignal(str, int, str, tuple)      # modename, node_id, error, source_addr
    ack_received = pyqtSignal(str, int, int, tuple)             # modename, node_id, sequence_num, source_addr
    port_status_changed = pyqtSignal(tuple, bool)  
    def __init__(self, bind_host: str = '0.0.0.0', bind_port: int = 0):
        """初始化UDP网络管理器

        创建UDP传输器实例并绑定信号槽，初始化Qt线程池用于异步发送任务。

        Args:
            bind_host: 绑定的主机地址，默认为'0.0.0.0'（所有网络接口）
            bind_port: 绑定的端口号，默认为0（随机分配端口）
        """
        """初始化UDP传输器

        创建UDP套接字并绑定到指定地址，初始化发送/接收线程和传输状态管理。

        Args:
            bind_host: 绑定的主机地址，默认为'0.0.0.0'（所有网络接口）
            bind_port: 绑定的端口号，默认为0（随机分配端口）
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
        self.online= False
        # 接收线程
        self.recv_thread = threading.Thread(target=self._recv_loop, daemon=True)
        self.recv_running = True
        self.recv_thread.start()
        
        # 发送队列
        self.send_queue = queue.Queue()
        self.sequence_counter = random.randint(1, 0xFFFF)  # 随机初始序列号
        
        # 传输状态
        self.pending_transmissions: Dict[Tuple, Dict] = {}  # key: (modename, node_id, seq_num)
        self.pending_receptions: Dict[Tuple, Dict] = {}     # key: (source_addr, modename, node_id, seq_num)
        self.lock = threading.Lock()
        
        # 启动发送线程
        self.send_thread = threading.Thread(target=self._send_loop, daemon=True)
        self.send_thread.start()
        self.port_check_targets: Dict[Tuple, Dict] = {}  # key: (ip, port)
        self.port_check_lock = threading.Lock()
        logger.info("UDPTransmitter initialized")
    
    def _recv_loop(self):
        """接收循环 - 处理所有传入的数据包

        在独立线程中运行，持续接收UDP数据报并根据包类型分发到相应处理方法。
        支持超时机制避免阻塞，捕获并记录接收过程中的异常。
        """
    
        while self.recv_running:
            try:
                data, addr = self.sock.recvfrom(65535)
                packet = UDPPacket.parse(data)
                if not packet:
                    logger.warning(f"Invalid packet received from {addr}")
                    continue
                
                logger.debug(f"Received packet type={packet.packet_type} from {addr}, modename={packet.modename}")
                
                if packet.packet_type == UDPPacket.ACK_PACKET:
                    self._handle_ack_packet(packet, addr)
                elif packet.packet_type == UDPPacket.HEADER_PACKET:
                    self._handle_header_packet(packet, addr)
                elif packet.packet_type == UDPPacket.DATA_PACKET:
                    self._handle_data_packet(packet, addr)
                elif packet.packet_type == UDPPacket.FULL_PACKET:
                    self._handle_full_packet(packet, addr)
                elif packet.packet_type == UDPPacket.CHECK_PORT_PACKET:
                    self._handle_check_port_packet(packet, addr)
            except socket.timeout:
                pass
            except Exception as e:
                logger.error(f"Error in recv loop: {str(e)}", exc_info=True)
    
    def _handle_check_port_packet(self, packet: CheckPortPacket, addr: Tuple[str, int]):
        """处理端口检查包 - 返回ACK状态3"""
        logger.info(f"Received port check packet from {addr}")
        
        # 创建ACK包，状态设为ACK_CHECKPORT
        ack = ACKPacket(packet.modename, packet.node_id)
        ack.sequence_num = packet.sequence_num
        ack.packet_num = packet.packet_num
        ack.ack_status = UDPPacket.ACK_CHECKPORT
        ack.checksum = ack.calculate_checksum()
        
        try:
            self.sock.sendto(ack.build(), addr)
            logger.info(f"Sent port check ACK to {addr}")
        except Exception as e:
            logger.error(f"Failed to send port check ACK to {addr}: {str(e)}")
    
    def _handle_ack_packet(self, packet: ACKPacket, addr: Tuple[str, int]):
        """处理ACK包 - 更新传输状态"""
        key = (packet.modename, packet.node_id, packet.sequence_num,packet.packet_num)
        #print("ack接收成功",key,packet.ack_status)
        with self.lock:
            if key in self.pending_transmissions:
                transmission = self.pending_transmissions[key]
                
                if packet.ack_status == UDPPacket.ACK_CONFIRM:
                    # 确认成功
                    print(f"ACK 接收成功 for {key} from {addr}")
                    logger.info(f"ACK confirmed for {key} from {addr}")
                    del self.pending_transmissions[key]
                    self.ack_received.emit(packet.modename, packet.node_id, packet.sequence_num, addr)
                elif packet.ack_status == UDPPacket.ACK_RETRANSMIT:
                    # 需要重传
                    logger.warning(f"Retransmission requested for {key} from {addr}")
                    transmission['retry_count'] += 1
                    transmission['last_sent'] = 0  # 立即重传
                elif packet.ack_status == UDPPacket.ACK_CHECKPORT:  # 处理端口检查ACK
                    logger.info(f"Port check ACK received for {key} from {addr}")
                    self._update_port_status(addr, True)
                    if key in self.pending_transmissions:
                        del self.pending_transmissions[key]
                else:
                    logger.warning(f"Unknown ACK status: {packet.ack_status} for {key} from {addr}")
            else:
                logger.debug(f"Received ACK for unknown transmission {key} from {addr}")
    
    def _handle_header_packet(self, packet: HeaderPacket, addr: Tuple[str, int]):
        """处理包头包 - 初始化接收状态"""
        # 创建接收状态键
        recv_key = (addr, packet.modename, packet.node_id, packet.sequence_num)
        print("开始包头接收")
        
        # 发送ACK确认
        self._send_ack(packet.modename, packet.node_id, packet.sequence_num,packet.packet_num, addr)

        with self.lock:
            print("包头接收,进入锁")
            # 初始化接收状态
            assemble_data = False
        
            if recv_key in self.pending_receptions:
            # 已存在接收状态（由数据包创建）
                reception = self.pending_receptions[recv_key]
            
                # 更新包头信息
                reception['total_length'] = packet.total_length
                reception['packet_count'] = packet.packet_count
                reception['header_received'] = True
                reception['last_received'] = time.time()
            
                print(f"更新包头信息，已接收包数: {len(reception['received_packets'])}")
                logger.info(f"Updated header for {recv_key}, expecting {packet.packet_count} packets")
            
                # 检查是否已接收所有包
                if len(reception['received_packets']) == reception['packet_count']:
                    assemble_data = True
            else:
            # 初始化接收状态
                self.pending_receptions[recv_key] = {
                    'source_addr': addr,
                    'total_length': packet.total_length,
                    'packet_count': packet.packet_count,
                    'received_packets': {},
                    'last_received': time.time(),
                    'header_received': True
                }
                print("包头接收成功")
                logger.info(f"Header received for {recv_key}, expecting {packet.packet_count} packets")
        
            print("包头接收,退出锁")
            if assemble_data :           
                self._assemble_data(recv_key, reception)
    
    def _handle_data_packet(self, packet: DataPacket, addr: Tuple[str, int]):
        """处理数据包 - 存储数据并发送ACK"""
        # 创建接收状态键
        recv_key = ( addr,packet.modename, packet.node_id, packet.sequence_num)

        
        # 发送ACK
        self._send_ack(packet.modename, packet.node_id, packet.sequence_num, packet.packet_num,addr)
        
        with self.lock:
            print("数据接收,进入锁")
            if recv_key not in self.pending_receptions:
            # 包头尚未到达，创建临时接收状态
                self.pending_receptions[recv_key] = {
                    'source_addr': addr,
                    'total_length': 0,
                    'packet_count': 0,
                    'received_packets': {packet.packet_num: packet.data},
                    'last_received': time.time(),
                    'header_received': False  # 标记包头未到达
                }
                print("包头未到达")
                logger.info(f"Buffering data packet before header: {recv_key}")
                return
                
                # 存储数据包
            reception = self.pending_receptions[recv_key]
            reception['received_packets'][packet.packet_num] = packet.data
            reception['last_received'] = time.time()
                
            logger.debug(f"Received data packet {packet.packet_num} for {recv_key}")
                
                # 检查是否接收完成
            if (reception['header_received'] and len(reception['received_packets']) == reception['packet_count']):
                assemble_data=True
            else:
                assemble_data=False
            print("数据接收,退出锁")
        if assemble_data:           
            self._assemble_data(recv_key, reception)


    def _handle_full_packet(self, packet: FullPacket, addr: Tuple[str, int]):
        """处理整体包 - 直接完成传输"""
        # 发送ACK确认
        self._send_ack(packet.modename, packet.node_id, packet.sequence_num,packet.packet_num, addr)
        print(f"收到完整包: {packet.modename}-{packet.node_id}-{packet.sequence_num}")
        # 处理数据
        self.transmission_complete.emit(
            packet.modename, 
            packet.node_id, 
            packet.data,
            addr
        )
        logger.info(f"Full packet received from {addr}, size: {len(packet.data)}")
    
    def _send_ack(self, modename: str, node_id: int, seq_num: int,packet_num:int ,dest_addr: Tuple[str, int]):
        """发送ACK包到指定地址"""
        ack = ACKPacket(modename, node_id)
        ack.packet_num=packet_num
        ack.sequence_num = seq_num
        ack.ack_status = UDPPacket.ACK_CONFIRM
        ack.checksum = ack.calculate_checksum()
        print(f"发送ACK包: {ack.build()}")
        try:
            self.sock.sendto(ack.build(), dest_addr)
            logger.debug(f"Sent ACK for {modename}-{node_id}-{seq_num} to {dest_addr}")
        except Exception as e:
            logger.error(f"Failed to send ACK to {dest_addr}: {str(e)}")
    
    def _assemble_data(self, recv_key: Tuple, reception: Dict):
        """组装接收到的数据并完成传输"""
        # 按序列号排序数据包
        print("开始数据组装")
        sorted_packets = sorted(reception['received_packets'].items())
        data = b''.join(packet_data for _, packet_data in sorted_packets)
        
        # 验证数据长度
        if len(data) != reception['total_length']:
            logger.error(f"Data length mismatch for {recv_key}: expected {reception['total_length']}, got {len(data)}")
            return
        
        # 发射完成信号
        _, modename, node_id, seq_num = recv_key
        self.transmission_complete.emit(modename, node_id, data, reception['source_addr'])
        print("数据组装完成")
        # 清理接收状态
        with self.lock:
            print("清理接收状态")
            if recv_key in self.pending_receptions:
                del self.pending_receptions[recv_key]
        
        logger.info(f"Data assembly complete for {recv_key}, size: {len(data)}")
    
    def _send_loop(self):
        """发送循环 - 处理发送队列和重传

        在独立线程中运行，处理发送队列中的数据发送任务，并定期检查超时未确认的数据包
        实现超时重传机制（最多3次重试），确保数据可靠送达。
        """
    
        while self.recv_running:
            # 处理发送队列
            try:
                task = self.send_queue.get(timeout=0.5)
                self._send_data(task['data'], task['modename'], task['node_id'], task['dest_addr'])
            except queue.Empty:
                pass
            
            # 检查重传
            self._check_retransmissions()
    
    def _send_data(self, data: bytes, modename: str, node_id: int, dest_addr: Tuple[str, int]):
    
        # 分配序列号
        with self.lock:
            self.sequence_counter = (self.sequence_counter + 1) & 0xFFFFFFFF
            sequence_num = self.sequence_counter
            key = (modename, node_id, sequence_num)
        
        if len(data) <= FullPacket.MAX_DATA_SIZE:
            # 使用整体包
            packet = FullPacket(modename, node_id)
            packet.sequence_num = sequence_num
            packet.data = data
            packet.total_length = len(data)
            packet.packet_count = 1
            packet.packet_num = 0  #整体包分包号固定为0
            packet.checksum = packet.calculate_checksum()
            key=(modename, node_id, sequence_num,0)
            self._queue_for_transmission(key, packet, data, dest_addr)
            print(f"发送完整包: {packet.build()} seq_num: {sequence_num}")
            logger.info(f"Queued full packet for {key} to {dest_addr}, size: {len(data)}")
        else:
            # 分包传输
            # 1. 发送包头
            header = HeaderPacket(modename, node_id)
            header.sequence_num = sequence_num
            header.packet_num = 0  # 包头分包号固定为0
            header.total_length = len(data)
            header.packet_count = (len(data) + DataPacket.MAX_DATA_SIZE - 1) // DataPacket.MAX_DATA_SIZE
            header.checksum = header.calculate_checksum()
            key=(modename, node_id, sequence_num,0)
            self._queue_for_transmission(key, header, data, dest_addr)
            logger.info(f"Queued header for {key} to {dest_addr}, total packets: {header.packet_count}")
            
            # 2. 发送数据包
            packet_num = 1
            for i in range(0, len(data), DataPacket.MAX_DATA_SIZE):
                chunk = data[i:i+DataPacket.MAX_DATA_SIZE]
                data_packet = DataPacket(modename, node_id)
                data_packet.sequence_num = sequence_num
                data_packet.data = chunk
                data_packet.checksum = data_packet.calculate_checksum()
                data_packet.packet_num = packet_num
                # 每个数据包使用相同的序列号但不同的包号
                sub_key = (modename, node_id, sequence_num, packet_num)
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
                        modename, node_id, *_ = key
                        if transmission['packet'].packet_type == UDPPacket.CHECK_PORT_PACKET:
                            self._update_port_status(transmission['dest_addr'], False)
                        self.transmission_failed.emit(
                            modename, 
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
    
    def _update_port_status(self, addr: Tuple[str, int], online: bool):
        """更新端口状态并发出信号"""
        with self.port_check_lock:
            # 获取当前状态（默认为离线）
            current_status = self.port_check_targets.get(addr, {'online': False, 'retry_count': 0})
            
            # 更新状态
            if online:
                # 收到ACK，重置重试计数并标记为在线
                current_status['online'] = True
                current_status['retry_count'] = 0
                logger.info(f"Port {addr} is online")
            else:
                # 重试超过3次，标记为离线
                current_status['online'] = False
                logger.warning(f"Port {addr} is offline")
            
            # 保存状态并发出信号
            self.port_check_targets[addr] = current_status
            self.port_status_changed.emit(addr, current_status['online'])
    
    def check_port(self, dest_addr: Tuple[str, int], modename: str = "node", node_id: int = 0):
        """发送端口检查包到指定地址

        Args:
            dest_addr: 目标地址 (host, port)
            modename: 模块名称，默认为"node"
            node_id: 节点ID，默认为0
        """
        # 创建端口检查包
        packet = CheckPortPacket(modename, node_id)
        
        # 分配序列号
        with self.lock:
            self.sequence_counter = (self.sequence_counter + 1) & 0xFFFFFFFF
            sequence_num = self.sequence_counter
            packet.sequence_num = sequence_num
            packet.checksum = packet.calculate_checksum()
        
        # 初始化端口状态
        with self.port_check_lock:
            if dest_addr not in self.port_check_targets:
                self.port_check_targets[dest_addr] = {
                    'online': False,
                    'retry_count': 0
                }
        
        # 加入传输队列
        key = (modename, node_id, sequence_num, 0)
        self._queue_for_transmission(key, packet, b'', dest_addr)
        logger.info(f"Queued port check packet for {dest_addr}")
    
    def is_port_online(self, addr: Tuple[str, int]) -> bool:
        """检查指定端口是否在线
        
        Args:
            addr: 目标地址 (ip, port)
            
        Returns:
            bool: 如果在线返回True，否则False
        """
        with self.port_check_lock:
            status = self.port_check_targets.get(addr)
            return status['online'] if status else False
    def send_to(self, modename: str, node_id: int, data: bytes, dest_addr: Tuple[str, int]):
        """发送数据到指定地址

        创建UDPSendTask任务并提交到线程池执行，实现异步非阻塞发送。

        Args:
            modename: 目标模块名称
            node_id: 目标节点ID
            data: 待发送的数据字节流
            dest_addr: 目标地址元组 (host, port)
        """
        """发送数据到指定地址

        将数据添加到发送队列，由发送线程异步处理。根据数据大小自动选择整体包或分包传输。

        Args:
            modename: 目标模块名称
            node_id: 目标节点ID
            data: 待发送的原始数据字节流
            dest_addr: 目标地址元组 (host, port)
        """
        """发送数据到指定地址"""
        self.send_queue.put({
            'modename': modename,
            'node_id': node_id,
            'data': data,
            'dest_addr': dest_addr
        })
    
    def get_local_addr(self) -> Tuple[str, int]:
        """获取本地绑定的地址和端口

        Returns:
            Tuple[str, int]: 本地地址元组 (host, port)
        """
        return self.sock.getsockname()
    
    def close(self):
        """关闭UDP传输器

        停止接收和发送线程，关闭UDP套接字，释放资源。
        """
        self.recv_running = False
        if self.sock:
            self.sock.close()
        logger.info("UDPTransmitter closed")


class UDPSendTask(QRunnable):
    """UDP发送任务

    基于QRunnable的异步发送任务，用于在Qt线程池中执行数据发送操作，避免阻塞主线程。
    封装了发送所需的所有参数，由线程池调度执行。
    """

    def __init__(self, transmitter: UDPTransmitter, modename: str, node_id: int, data: bytes, dest_addr: Tuple[str, int]):
        """初始化发送任务

        Args:
            transmitter: UDPTransmitter实例，用于实际数据发送
            modename: 目标模块名称
            node_id: 目标节点ID
            data: 待发送的数据字节流
            dest_addr: 目标地址元组 (host, port)
        """
        super().__init__()
        self.transmitter = transmitter
        self.modename = modename
        self.node_id = node_id
        self.data = data
        self.dest_addr = dest_addr
    
    def run(self):
        """执行发送任务

        在线程池中运行，调用transmitter的send_to方法发送数据。
        """
        self.transmitter.send_to(self.modename, self.node_id, self.data, self.dest_addr)


class UDPNetworkManager(QObject):
    """UDP网络管理器

    提供UDP网络通信的高层接口，封装UDPTransmitter和线程池管理，简化数据发送和接收流程。
    通过信号槽机制通知数据接收和传输失败事件，方便上层业务逻辑处理。
    """

    dataReceived = pyqtSignal(str, int, bytes, tuple)  # modename, node_id, data, source_addr
    transmissionFailed = pyqtSignal(str, int, str, tuple)  # modename, node_id, error, dest_addr
    portStatusChanged = pyqtSignal(tuple, bool) 
    def __init__(self, bind_host: str = '0.0.0.0', bind_port: int = 0):
        super().__init__()
        self.transmitter = UDPTransmitter(bind_host, bind_port)
        self.transmitter.transmission_complete.connect(self._on_data_received)
        self.transmitter.transmission_failed.connect(self._on_transmission_failed)
        self.transmitter.port_status_changed.connect(self._on_port_status_changed)
        self.pool = QThreadPool.globalInstance()

    def check_port(self, dest_addr: Tuple[str, int], modename: str = "node", node_id: int = 0):

        """发送端口检查包到指定地址

        

        Args:

            dest_addr: 目标地址 (host, port)

            modename: 模块名称，默认为"node"

            node_id: 节点ID，默认为0

        """

        self.transmitter.check_port(dest_addr, modename, node_id)    
    
    def is_port_online(self, addr: Tuple[str, int]) -> bool:
        """检查指定端口是否在线
        
        Args:
            addr: 目标地址 (ip, port)
            
        Returns:
            bool: 如果在线返回True，否则False
        """
        return self.transmitter.is_port_online(addr)
    
    def _on_port_status_changed(self, addr: Tuple[str, int], online: bool):
        """处理端口状态变化 - 信号槽回调

        Args:
            addr: 目标地址元组 (host, port)
            online: 端口是否在线
        """
        self.portStatusChanged.emit(addr, online)
    
    def send_to(self, modename: str, node_id: int, data: bytes, dest_addr: Tuple[str, int]):
        """发送数据到指定地址

        创建UDPSendTask任务并提交到线程池执行，实现异步非阻塞发送。

        Args:
            modename: 目标模块名称
            node_id: 目标节点ID
            data: 待发送的数据字节流
            dest_addr: 目标地址元组 (host, port)
        """
        task = UDPSendTask(self.transmitter, modename, node_id, data, dest_addr)
        self.pool.start(task)
    
    def get_local_addr(self) -> Tuple[str, int]:
        """获取本地绑定的地址和端口

        委托给内部UDPTransmitter实例获取当前绑定的地址和端口。

        Returns:
            Tuple[str, int]: 本地地址元组 (host, port)
        """
        return self.transmitter.get_local_addr()
    
    def _on_data_received(self, modename: str, node_id: int, data: bytes, source_addr: Tuple[str, int]):
        """处理接收到的数据 - 信号槽回调

        将UDPTransmitter的transmission_complete信号转发为dataReceived信号。

        Args:
            modename: 源模块名称
            node_id: 源节点ID
            data: 接收到的数据字节流
            source_addr: 源地址元组 (host, port)
        """
        self.dataReceived.emit(modename, node_id, data, source_addr)
    
    def _on_transmission_failed(self, modename: str, node_id: int, error: str, dest_addr: Tuple[str, int]):
        """处理传输失败 - 信号槽回调

        将UDPTransmitter的transmission_failed信号转发为transmissionFailed信号。

        Args:
            modename: 目标模块名称
            node_id: 目标节点ID
            error: 错误描述信息
            dest_addr: 目标地址元组 (host, port)
        """
        self.transmissionFailed.emit(modename, node_id, error, dest_addr)
    
    def close(self):
        """关闭网络管理器

        关闭内部UDPTransmitter实例，释放所有网络资源。
        """
        self.transmitter.close()
