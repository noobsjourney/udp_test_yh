from abc import ABC, abstractmethod
from typing import Type, Dict, Any, Optional
import weakref
from base_module import BaseModule
# 测试模块类定义
class TestModuleA(BaseModule):
    def __init__(self):
        super().__init__()
    @property
    def module_name(self):
        return "test_module_a"

class TestModuleB(BaseModule):
    def __init__(self):
        super().__init__()
        print("当前注册模块：", list(BaseModule._module_manespace.values()))
    @property
    def module_name(self):
        return "test_module_b"

class TestModuleC(BaseModule):

    def __init__(self):
        super().__init__()
        print("当前注册模块：", self.module_name)
    @property
    def module_name(self):
        return "test_module_c"

# 在应用启动前验证模块注册

if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication
    
    # 初始化Qt应用
    app = QApplication(sys.argv)
    
    # 实例化测试模块以触发注册
    TestModuleA()
    TestModuleB()
    TestModuleC()
    
    # 打印当前所有注册模块
    print(TestModuleA().get_module_name(),TestModuleB().module_name)
    print("当前注册模块列表:", [cls.__name__ for cls in BaseModule._module_manespace.values()])
    sys.exit(app.exec())