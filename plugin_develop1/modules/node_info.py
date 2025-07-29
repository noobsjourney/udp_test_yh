import hashlib
import platform
import subprocess
import os
import socket
import uuid
from typing import Dict, Optional


class SystemIdentity:
    """
    系统唯一标识生成器
    功能特点：
    - 跨平台硬件信息采集（主板/CPU/磁盘/MAC）
    - 优化的虚拟化环境检测
    - 复合型指纹生成策略
    - 自动降级备用方案
    """

    @staticmethod
    def get_hardware_fingerprint() -> str:
        """获取复合硬件特征指纹"""
        try:
            if platform.system() == 'Windows':
                if SystemIdentity.detect_virtualization() == 'virtual':
                    return SystemIdentity._get_windows_vm_id()
                return SystemIdentity._get_windows_physical_id()

            # Linux/Unix平台
            if SystemIdentity.detect_virtualization() == 'virtual':
                return SystemIdentity._get_linux_vm_id()
            return SystemIdentity._get_linux_physical_id()

        except Exception as e:
            return f"err_{hashlib.md5(str(e).encode()).hexdigest()[:8]}"

    @staticmethod
    def _get_windows_physical_id() -> str:
        """Windows物理机复合标识"""
        identifiers = []
        # 主板序列号
        try:
            result = subprocess.run(['wmic', 'baseboard', 'get', 'serialnumber'],
                                    capture_output=True, text=True, check=True)
            identifiers.append(result.stdout.split()[-1].strip())
        except Exception:
            pass

        # CPU ID
        try:
            result = subprocess.run(['wmic', 'cpu', 'get', 'processorid'],
                                    capture_output=True, text=True, check=True)
            identifiers.append(result.stdout.split()[-1].strip())
        except Exception:
            pass

        # 磁盘序列号
        try:
            result = subprocess.run(['wmic', 'diskdrive', 'get', 'serialnumber'],
                                    capture_output=True, text=True, check=True)
            identifiers.append(result.stdout.split()[-1].strip())
        except Exception:
            pass

        # MAC地址
        try:
            mac = uuid.getnode()
            identifiers.append(hex(mac)[2:])
        except Exception:
            pass

        return f"win_phys_{'_'.join(identifiers)}" if identifiers else "win_unknown"

    @staticmethod
    def _get_linux_physical_id() -> str:
        """Linux物理机复合标识"""
        identifiers = []
        # CPU序列号
        try:
            with open('/proc/cpuinfo') as f:
                cpu_info = f.read()
            cpu_id = [line.split(':')[-1].strip()
                      for line in cpu_info.splitlines()
                      if 'serial' in line.lower()]
            identifiers.extend(cpu_id)
        except Exception:
            pass

        # 磁盘ID
        try:
            disk_id = subprocess.check_output(
                ['lsblk', '-d', '-o', 'serial'],
                text=True
            ).split()[-1].strip()
            identifiers.append(disk_id)
        except Exception:
            pass

        # MAC地址
        try:
            with open('/sys/class/net/eth0/address') as f:
                identifiers.append(f.read().strip().replace(':', ''))
        except Exception:
            try:
                mac = uuid.getnode()
                identifiers.append(hex(mac)[2:])
            except Exception:
                pass

        return f"lin_phys_{'_'.join(identifiers)}" if identifiers else "lin_unknown"

    @staticmethod
    def _get_windows_vm_id() -> str:
        """Windows虚拟机标识"""
        try:
            result = subprocess.run(['wmic', 'csproduct', 'get', 'uuid'],
                                    capture_output=True, text=True, check=True)
            return f"win_vm_{result.stdout.split()[-1].strip()}"
        except Exception:
            return "win_vm_unknown"

    @staticmethod
    def _get_linux_vm_id() -> str:
        """Linux虚拟机标识"""
        vm_files = [
            '/sys/devices/virtual/dmi/id/product_uuid',
            '/sys/hypervisor/uuid',
            '/var/lib/cloud/instance/vendor-uuid'
        ]
        for fpath in vm_files:
            if os.path.exists(fpath):
                try:
                    with open(fpath) as f:
                        return f"lin_vm_{f.read().strip()}"
                except Exception:
                    continue
        return "lin_vm_unknown"

    @staticmethod
    def get_os_fingerprint() -> str:
        """获取操作系统特征指纹"""
        os_info = platform.uname()
        return (
            f"{os_info.system}_{os_info.release}_"
            f"{os_info.version}_{os_info.machine}"
        )

    @staticmethod
    def detect_virtualization() -> str:
        """虚拟化环境检测"""
        try:
            # Windows检测
            if platform.system() == 'Windows':
                try:
                    result = subprocess.run(
                        ['wmic', 'computersystem', 'get', 'model'],
                        capture_output=True, text=True, check=True
                    )
                    if 'Virtual' in result.stdout:
                        return 'virtual'

                    # 检查BIOS信息
                    result = subprocess.run(
                        ['wmic', 'bios', 'get', 'serialnumber'],
                        capture_output=True, text=True, check=True
                    )
                    bios_info = result.stdout.lower()
                    if 'vmware' in bios_info or 'virtual' in bios_info:
                        return 'virtual'
                except Exception:
                    pass
                return 'physical'

            # Linux检测
            # 检查CPU虚拟化标志
            try:
                with open('/proc/cpuinfo') as f:
                    if 'hypervisor' in f.read().lower():
                        return 'virtual'
            except Exception:
                pass

            # 检查虚拟化特征文件
            vm_indicators = [
                '/sys/hypervisor/uuid',
                '/etc/cloud/cloud.cfg',
                '/sys/devices/virtual/dmi/id/product_uuid'
            ]
            if any(os.path.exists(path) for path in vm_indicators):
                return 'virtual'

            # 容器环境检测
            container_indicators = [
                '/.dockerenv',
                '/.dockerinit',
                '/run/.containerenv'
            ]
            if any(os.path.exists(path) for path in container_indicators):
                return 'container'

            return 'physical'
        except Exception:
            return 'unknown'

    @classmethod
    def generate_identity(cls) -> str:
        """生成不可逆系统标识"""
        components = [
            cls.get_hardware_fingerprint(),
            cls.get_os_fingerprint(),
            cls.detect_virtualization()
        ]
        combined = "@".join(components).encode('utf-8')
        return hashlib.sha256(combined).hexdigest()

from base_module import BaseModule
class NodeInfo(BaseModule):
    """
        节点信息管理类
        功能：
        - 存储和管理节点信息
        - 提供获取节点信息的方法
        - 支持节点信息的持久化存储
        - 支持动态更新节点信息
        - 提供节点标识生成方法
        - 支持节点在线状态管理
        属性：
        - nodeIsOnline: bool 节点在线状态
        - node_id: int 节点标识，可以设置，用于标记相关的数据库，初始化后不可修改
        - node_name: str 节点名称，可自由修改
        - info_file: str 节点信息文件路径
        - _nodeGenerateId: str 节点生成唯一标识码，用于服务器识别节点，系统和硬件不变更的情况下保持不变
        - IP: str 节点IP地址，由系统IP获取

        方法：
        - get_node_info() -> dict: 获取节点信息
        - set_node_info(node_id: int, node_name: str) -> None: 设置节点信息
        - read_node_info() -> dict: 读取节点信息
        - save_node_info() -> None: 保存节点信息
        - set_nodeIsOnline_to_true(nodeIsOnline: bool) -> None: 设置节点为在线状态
        - set_nodeIsOnline_to_false(nodeIsOnline: bool) -> None: 设置节点为离线状态
        - set_ip(ip: str) -> None: 设置节点IP地址
        方法：
        注意：
        - 节点信息存储在info.txt文件中，格式：
          node_id:1234567890
          node_name:Node1
        - 节点标识由SystemIdentity类生成
        - 节点在线状态由nodeIsOnline属性管理
        - 节点信息更新后，需要调用save_node_info()方法保存
        - 节点信息读取后，可通过get_node_info()方法获取
        使用示例：
        node_info = NodeInfo()
        node_info.set_node_info(1234567890, "Node1")
        node_info.save_node_info()
        """

    def __init__(self):
        print("node_info初始化")
        self._nodeIsOnline: bool = False
        self._node_id: int = 0
        self.node_name: str = "Unnamed_Node"
        self.info_file = os.path.join(os.path.dirname(__file__), "node.cfg")
        self.IP: str = self._get_default_ip()
        self._nodeGenerateId: str = SystemIdentity.generate_identity()
        self._initialize()
    def module_name(self) -> str:
        return "nodeInfo"
    def _initialize(self):
        """配置初始化"""
        print("配置初始化")
        try:
            self.read_node_info()
        except FileNotFoundError:
            self._create_default_config()
        except Exception as e:
            print(f"[WARN] 配置初始化失败: {str(e)}")

    def _get_default_ip(self) -> str:
        """智能获取本机IP"""
        print("获取本机IP")
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
        except Exception:
            try:
                return socket.gethostbyname(socket.gethostname())
            except Exception:
                return "0.0.0.0"

    def _create_default_config(self):
        print("创建默认配置")
        """创建默认配置"""
        self.node_name = f"Node_{self.IP.replace('.', '-')}"
        self.save_node_info()

    @property
    def node_id(self) -> int:
        return self._node_id

    @property
    def nodeIsOnline(self) -> bool:
        return self._nodeIsOnline

    def set_online(self):
        """设置在线状态"""
        print("设置在线状态")
        self._nodeIsOnline = True

    def set_offline(self):
        """设置离线状态"""
        print("设置离线状态")
        self._nodeIsOnline = False

    def set_ip(self, ip: str) -> None:
        """设置IP地址（带验证）"""
        print("设置IP地址")
        if isinstance(ip, str) and len(ip.split('.')) == 4:
            self.IP = ip
            self.save_node_info()
        else:
            raise ValueError("无效的IP地址格式")

    def set_node_info(self, node_id: int, node_name: str) -> None:
        """设置节点信息（带验证）"""
        print("设置节点信息")
        if self._node_id == 0 and isinstance(node_id, int) and node_id > 0:
            self._node_id = node_id
        elif self._node_id != 0:
            raise RuntimeError("节点ID已初始化，不可修改")

        if isinstance(node_name, str) and 2 <= len(node_name) <= 32:
            self.node_name = node_name
        else:
            raise ValueError("节点名称长度需在2-32字符之间")

    def get_node_info(self) -> Dict:
        """获取完整节点信息"""
        print("获取完整节点信息")
        return {
            "node_id": self._node_id,
            "node_name": self.node_name,
            "online": self._nodeIsOnline,
            "ip": self.IP,
            "generate_id": self._nodeGenerateId,
            "last_update": os.path.getmtime(self.info_file) if os.path.exists(self.info_file) else 0
        }

    def read_node_info(self) -> Dict:
        """安全读取配置文件"""
        print("安全读取配置文件")
        config = {}
        try:
            with open(self.info_file, 'r') as f:
                for line in f:
                    if ':' in line:
                        key, value = line.strip().split(':', 1)
                        config[key.strip()] = value.strip()

            # 字段验证
            if 'node_id' in config:
                try:
                    self._node_id = int(config['node_id'])
                except ValueError:
                    pass

            if 'node_name' in config:
                self.node_name = config['node_name'][:32]  # 截断超长名称

            if 'last_ip' in config:
                self.IP = config['last_ip']

            return config
        except Exception as e:
            raise RuntimeError(f"配置读取失败: {str(e)}")

    def save_node_info(self) -> None:
        """安全保存配置文件"""
        print("安全保存配置文件")
        config = {
            'node_id': self._node_id,
            'node_name': self.node_name,
            'last_ip': self.IP,
            'generate_id': self._nodeGenerateId
        }

        try:
            with open(self.info_file, 'w') as f:
                for key, value in config.items():
                    f.write(f"{key}:{value}\n")
        except Exception as e:
            raise RuntimeError(f"配置保存失败: {str(e)}")

    def __str__(self) -> str:
        """调试信息"""
        print("调试信息")
        info = self.get_node_info()
        return (
            f"Node [{info['node_id']}] {info['node_name']}\n"
            f"IP: {info['ip']} | Status: {'Online' if info['online'] else 'Offline'}\n"
            f"指纹ID: {info['generate_id'][:16]}...\n"
            f"最后更新: {info['last_update']}"
        )