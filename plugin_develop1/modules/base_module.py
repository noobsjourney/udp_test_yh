from PyQt6.QtCore import QObject
from abc import ABCMeta, abstractmethod
from typing_extensions import final
import weakref
SignalManager = None  # 占位，避免 IDE 报错

class BaseModule:
    def __init__(self):
        global SignalManager
        if SignalManager is None:
            from .signal_manager import SignalManager  # 延迟导入
        self.signal = SignalManager()


class ABCMetaQ(type(QObject), ABCMeta):
    pass

class BaseModule(QObject, metaclass=ABCMetaQ):
    """模块基类（强制子类实现模块名称）
    -属性：
        _module_manespace: 模块命名空间，用于存储模块名称
    -方法：
        get_module_name: 获取模块名称（基类实现禁止重写）
        check_module_name: 检查模块名称是否重名
        __init_subclass__: 子类初始化时检查模块名称是否重名
        module_name：必须实现的模块名称属性，@property装饰器实现的属性，访问时不需要加括号
        使用示例：
            class TestModuleA(BaseModule):
                def __init__(self):
                    super().__init__()
                    
                @property
                def module_name(self):
                    return "test_module_a"
                #以下两种方式都可以在模块中获取模块名称
                def test(self):
                    print(self.module_name)
                    print(self.get_module_name())
            # 实例化模块并获取模块名称
            class GetModuleAname():
                def __init__(self):
                    super().__init__()
                    self.testModuleA = TestModuleA()
                    self.module_name_A = self.testModuleA.get_module_name()
    """
    _module_manespace = weakref.WeakValueDictionary()  # 弱引用注册表


    @property
    @abstractmethod
    def module_name(self) -> str:
        """必须实现的模块名称属性"""
        pass

    @final
    def get_module_name(self) -> str:
        """获取模块名称（基类实现禁止重写）"""
        return self.module_name
    @final
    def check_module_name(self) -> None:
        """检查模块名称是否重名（基类实现禁止重写）"""
        existing_cls = self._module_manespace.get(self.module_name)
        if existing_cls and existing_cls.__name__ != self.__class__.__name__:
            raise ValueError(f"模块名称 '{self.module_name}' 已被 {existing_cls.__name__} 占用")
    @final
    def get_module_names(self) -> list:
        """获取所有模块名称（基类实现禁止重写）"""
        return list(self._module_manespace.keys())
    @final
    def __init_subclass__(cls, **kwargs):
        """该方法在子类完成定义后被调用，导入文件时会自动执行"""
        super().__init_subclass__(**kwargs)
        # 检查子类是否实现了模块名称属性
        if not hasattr(cls, 'module_name'):
            raise TypeError(f"模块 {cls.__name__} 必须实现 'module_name' 属性")
        if not cls.module_name:
            raise ValueError("模块名称不能为空")
        # 注册模块并检查重复
        if cls.module_name in cls._module_manespace:
            raise ValueError(f"模块名称 '{cls.module_name}' 已被 {cls._module_manespace[cls.module_name]} 占用")
        cls._module_manespace[cls.module_name] = cls  # 存储类引用



