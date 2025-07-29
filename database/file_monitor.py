import sys
import importlib
import time
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from PyQt5.QtCore import QObject, QThread, pyqtSignal, pyqtSlot, QCoreApplication
class FileMonitor(QObject):
    # 定义文件变化信号
    file_changed = pyqtSignal(str)  # 参数为文件路径
    def __init__(self, watch_dir):
        super().__init__()
        self.watch_dir = watch_dir
        self.observer = None
        self.last_trigger = 0
    def start(self):
        """启动文件监控"""
        class Handler(FileSystemEventHandler):
            def __init__(self, outer):
                super().__init__()
                self.outer = outer
            def on_modified(self, event):
                current_time = time.time()
                if current_time - self.outer.last_trigger > 1:
                    print("检测到变更:", event.src_path)
                    self.outer.file_changed.emit(event.src_path)
                    self.outer.last_trigger = current_time

            def on_created(self, event):
                current_time = time.time()
                if current_time - self.outer.last_trigger > 1:
                    print("检测到创建:", event.src_path)
                    self.outer.file_changed.emit(event.src_path)
                    self.outer.last_trigger = current_time
        self.observer = Observer()
        self.observer.schedule(Handler(self), self.watch_dir, recursive=True)
        self.observer.start()
    def stop(self):
        """停止文件监控"""
        if self.observer:
            self.observer.stop()
            self.observer.join()

if __name__ == "__main__":
    import os
    import sys
    import time

    def print_change(path):
        print(f"检测到变更: {path}")

    monitor = FileMonitor(os.path.abspath("test_dir"))
    monitor.file_changed.connect(print_change)

    monitor.start()
    print("监控已启动，按Ctrl+C停止...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        monitor.stop()
        print("\n监控已停止")