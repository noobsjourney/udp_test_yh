import importlib
import sys, time
from pathlib import Path
import logging

from types import ModuleType

class ModelReloader:
    def __init__(self, base_module_name: str = "models"):
        self.base_module = importlib.import_module(base_module_name)
        self.base_path = Path(self.base_module.__file__).parent
        self.loaded_modules = set()
        self.__EXCLUDE_PATTERNS = { "__init__.py", "model_base.py"}
    def _module_path_to_name(self, file_path: Path) -> str:
        """将文件路径转换为模块名"""
        # 确保路径转换基于正确的base_path
        try:
            relative_path = file_path.relative_to(self.base_path)
        except ValueError:
            relative_path = file_path.relative_to(self.base_path.parent)
        moduleName= f"{self.base_module.__name__}." + str(relative_path.with_suffix('')).replace('/', '.')
        print(f"[DEBUG] 转换路径: {file_path} -> {moduleName}") 
        return moduleName
    def reload_all_modules(self,models_dir: Path):
        """动态重载所有已加载的模块"""
        """遍历目录下的所有.py文件，导入并重新加载模块"""
        modules = []
        for file_path in models_dir.glob("**/*.py"):
            if file_path.is_file() and file_path.name not in self.__EXCLUDE_PATTERNS:  # 仅处理models目录下的文件:
                module_name = self._module_path_to_name(file_path)
                modules.append(module_name)

        for name in reversed(modules):  # 先子模块后父模块
            if name in sys.modules:
                module = sys.modules[name]
                    # 检查是否为模块类型
                del sys.modules[name]
                print(f"删除模块: {name}")

        for module_name in modules:  # 重新导入并加载模块
            try:
                    # 先尝试导入模块
                
                module = importlib.import_module(module_name)
                    # 执行重载
                importlib.reload(module)
                print (f"成功重载模块: {module_name}")
                print(f"成功重载模块: {module}")
            except KeyError:
                print(f"模块未加载: {module_name}")
            except Exception as e:
                print(f"重载模块失败: {module_name} - {str(e)}")
    def reload_module(self, changed_file: Path):
        """动态重载指定模块及其依赖"""
        changed_module = self._module_path_to_name(changed_file)
        #强制导入模块
        if changed_module not in sys.modules:
            try:
                importlib.import_module(changed_module)
                print (f"导入模块: {changed_module}")
                return
            except Exception as e:
                logging.error(f"导入模块失败: {changed_module} - {e}")
                return
        # 查找需要重新加载的模块链
        modules_to_reload = []
        for name, module in list(sys.modules.items()):
            if (name == changed_module or 
                (name.startswith(f"{changed_module}.") and 
                 getattr(module, '__file__', None) and 
                 Path(module.__file__).is_relative_to(self.base_path))):
                modules_to_reload.append(name)
        
        # 按依赖顺序重新加载
        for name in reversed(modules_to_reload):  # 先子模块后父模块
            logging.debug(f"重载模块: {name}")
            print(f"重载模块: {name}")  # 打印调试信息到stdout，便于查看日志
            
            importlib.reload(sys.modules[name])

if __name__ == "__main__":
    reloader = ModelReloader()
    while True:
        try:
            # 模拟文件变化
            # 传递正确的models目录路径
            models_dir = Path(__file__).parent / "models"
            reloader.reload_all_modules(models_dir)
            
            print("模型已重新加载")
            time.sleep(10)  # 等待10秒
        except Exception as e:
            print(f"错误: {e}")
