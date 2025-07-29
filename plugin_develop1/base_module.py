from PyQt5.QtCore import QObject
from abc import ABCMeta, abstractmethod
from typing_extensions import final
import weakref

# ✅ 统一元类：兼容 PyQt5 和 抽象类
class ABCQObjectMeta(type(QObject), ABCMeta):
    pass

class BaseModule(QObject, metaclass=ABCQObjectMeta):
    """基础模块类（支持 Qt 信号 + 抽象接口）"""
    _module_manespace = weakref.WeakValueDictionary()
    _class_id_registry = {}  # {ID: 类}
    _name_to_id_registry = {}  # {模块名称: ID}
    _next_id = 1  # 下一个可用ID

    def __init__(self):
        super().__init__()

    @property
    @abstractmethod
    def module_name(self) -> str:
        pass

    @final
    def get_module_name(self) -> str:
        return self.module_name

    @final
    def check_module_name(self) -> None:
        existing_cls = self._module_manespace.get(self.module_name)
        if existing_cls and existing_cls.__name__ != self.__class__.__name__:
            raise ValueError(f"模块名称 '{self.module_name}' 已被 {existing_cls.__name__} 占用")

    @final
    def get_module_names(self) -> list:
        return list(self._module_manespace.keys())

    @classmethod
    @final
    def get_class_by_id(cls, id_: int) -> type:
        """通过ID获取类"""
        return cls._class_id_registry.get(id_)
    
    @classmethod
    @final
    def get_id_by_name(cls, name: str) -> int:
        """通过模块名称获取ID"""
        return cls._name_to_id_registry.get(name)
    
    @classmethod
    @final
    def get_name_by_id(cls, id_: int) -> str:
        """通过ID获取模块名称"""
        if class_ := cls._class_id_registry.get(id_):
            return class_.module_name
        return None
    
    @classmethod
    @final
    def get_forward_dict(cls) -> dict:
        """获取正向字典 {ID: 模块名称}"""
        return {id_: class_.module_name 
                for id_, class_ in cls._class_id_registry.items()}
    
    @classmethod
    @final
    def get_reverse_dict(cls) -> dict:
        """获取反向字典 {模块名称: ID}"""
        return cls._name_to_id_registry.copy()

    @final
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if not hasattr(cls, 'module_name'):
            raise TypeError(f"模块 {cls.__name__} 必须实现 'module_name' 属性")
        if not cls.module_name:
            raise ValueError("模块名称不能为空")
        if cls.module_name in cls._module_manespace:
            raise ValueError(f"模块名称 '{cls.module_name}' 已被 {cls._module_manespace[cls.module_name]} 占用")
        cls._module_manespace[cls.module_name] = cls
        # 分配ID并注册
        if cls.module_name not in cls._name_to_id_registry:
            new_id = cls._next_id
            cls._next_id += 1
            
            cls._class_id_registry[new_id] = cls
            cls._name_to_id_registry[cls.module_name] = new_id