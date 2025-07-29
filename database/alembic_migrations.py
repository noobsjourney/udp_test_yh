import logging
from pathlib import Path
from alembic import command
from sqlalchemy.orm import registry
from alembic.config import Config
from alembic.util import CommandError
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
import time
from sqlalchemy import engine_from_config 
from  .models.model_base import DataStorageBase,GeneralStorageBase,DataStorageBaseModel,GeneralStorageBaseModel
from sqlalchemy.pool import NullPool
from .models_reload import ModelReloader
from base_module import BaseModule
class DatabaseMigrator:
    """数据库迁移控制器"""
    
    def __init__(self, 
                 local_migration_dir: Path, 
                 remote_migration_dir: Path,
                 remote_status: int = 0):
        """
        初始化迁移控制器
        :param local_migration_dir: 本地数据库迁移目录
        :param remote_migration_dir: 远程数据库迁移目录
        :param remote_status: 远程数据库初始状态 (默认离线)
        """
        self.local_dir = local_migration_dir
        self.remote_dir = remote_migration_dir
        self.local_status = 1  # 本地数据库始终在线
        self.remote_status = remote_status
        
        # 初始化日志配置
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s"
        )
    def clean_matebase(self):
        """清理元数据"""
        DataStorageBase.metadata.clear()
        GeneralStorageBase.metadata.clear()
        DataStorageBaseModel.__model_registry__.clear()
        GeneralStorageBaseModel.__model_registry__.clear()
         # 重置 declarative base 的内部状态
        if hasattr(DataStorageBase, '_decl_class_registry'):
            DataStorageBase._decl_class_registry.clear()
        if hasattr(GeneralStorageBase, '_decl_class_registry'):
            GeneralStorageBase._decl_class_registry.clear()
          # 清除所有类型注册
       
    
    def set_remote_status(self, status: int):
        """设置远程数据库状态"""
        if status not in (0, 1):
            raise ValueError("Status must be 0 or 1")
        self.remote_status = status
    def execute_migrations(self):
        """执行全量迁移流程"""
        self._migrate_local()
        self._migrate_remote()
    def execute_generate_migrations(self):
        """执行全量脚本生成流程"""
        self._local_generate_migration()
        self._remote_generate_migration()
    
    def _migrate_local(self):
        """处理本地数据库迁移"""
        if self.local_status != 1:
            logging.warning("Local database status abnormal, skipping migration")
            return
        logging.info("Starting LOCAL database migration")
        self._run_alembic_migration(self.local_dir)
    def _migrate_remote(self):
        """处理远程数据库迁移"""
        if self.remote_status != 1:
            logging.warning("Remote database offline, skipping migration")
            return
        logging.info("Starting REMOTE database migration")
        self._run_alembic_migration(self.remote_dir)
    def _run_alembic_migration(self, migration_dir: Path):
        """执行实际的Alembic迁移"""
        try:
            config = Config(str(migration_dir / "alembic.ini"))
            config.set_main_option("script_location", str(migration_dir))
            
            command.upgrade(config, "head")
            logging.info(f"Migration success for {migration_dir.name}")
            
        except Exception as e:
            logging.error(f"Migration failed for {migration_dir.name}: {str(e)}")
            raise RuntimeError(f"Migration error in {migration_dir.name}") from e
    def _remote_generate_migration(self):
        """处理远程数据库脚本生成"""
        if self.remote_status != 1:
            logging.warning("Remote database offline, skipping migration")
            return
        logging.info("Starting REMOTE database migration")
        self._generate_migration(self.remote_dir, "Auto-generated migration")
    
    def _local_generate_migration(self):
        """处理本地数据库脚本生成"""
        if self.local_status!= 1:
            logging.warning("Local database status abnormal, skipping migration")
            return
        logging.info("Starting LOCAL database migration")
        self._generate_migration(self.local_dir, "Auto-generated migration")
    # 新增的迁移脚本生成方法
    
    def _generate_migration(self, migration_dir: Path, message: str):
        
        try:
            config = Config(str(migration_dir / "alembic.ini"))
            config.set_main_option("script_location", str(migration_dir))
            if migration_dir == self.local_dir:
                target_metadata = DataStorageBase.metadata
            elif migration_dir == self.remote_dir:
                target_metadata = GeneralStorageBase.metadata
            config.attributes["target_metadata"] = target_metadata
            config.attributes["compare_type"] = True 
        # 仅当有变更时才生成脚本

            engine = engine_from_config(
                config.get_section(config.config_ini_section),  # 读取 ini 的 [alembic] 段
                prefix="sqlalchemy.",  # 自动识别 sqlalchemy.url 等参数
                poolclass=NullPool
            )
            with engine.begin() as conn:
            # 合并上下文配置参数
                context = MigrationContext.configure(
                    conn,
                    opts={
                        'compare_type': True,
                        'compare_server_default': True,  # 可根据需要扩展
                        'target_metadata': target_metadata,
                    }
                )
                print("context",context)
                print("target_metadata",target_metadata)
                diffs = compare_metadata(context, target_metadata)
                if not diffs:  # 如果没有变更
                    logging.info(f"无模型变更 ({migration_dir.name})")
                    print(f"无模型变更 ({migration_dir.name})")
                    return  # 直接返回，不生成脚本
                else:
                   # print(f"有模型变更 (- {diffs[0]}: {diffs[1:]})")
                   print(f"有模型变更 (- {diffs[0]})")
                   pass
            command.revision(
                config,
                autogenerate=True,
                message=message
            )
            logging.info(f"已生成迁移脚本: {migration_dir}/versions/...")
        except CommandError as e:
        # 保留原有异常处理
            if "No changes in schema detected" in str(e):
                logging.info(f"无模型变更 ({migration_dir.name})")
            else:
                logging.error(f"脚本生成失败: {str(e)}")
                raise

class AutoDatabaseMigrator(DatabaseMigrator,BaseModule):
    """支持循环迁移的增强版"""
    
    def __init__(self, 
                 interval: int = 300,
                 max_retries: int = 3,
                 **kwargs):
        """
        :param interval: 迁移间隔时间（秒），默认5分钟
        :param max_retries: 最大重试次数
        """
        super().__init__(**kwargs)
        self.interval = interval
        self.max_retries = max_retries
        self.running = False
        self.modelsReload=ModelReloader()
    @property
    def module_name(self) -> str:
        return "auto_migrate"
    def start_mig(self):
        try:
            self.clean_matebase()
            self.modelsReload.reload_all_modules(Path(__file__).parent / "models")
            print(list(GeneralStorageBaseModel.get_all_modelname())) 
            self.execute_generate_migrations()
            self.execute_migrations()
        except Exception as e:
            logging.error(f"Migration cycle failed: {str(e)}")
            
      


    def start_loop(self):
        """启动迁移循环"""
        self.running = True
        logging.info("Starting auto-migration loop")
        
        while self.running:
            try:
                self.clean_matebase()
                self.modelsReload.reload_all_modules(Path(__file__).parent / "models")
                print(list(GeneralStorageBaseModel.get_all_modelname())) 
                self.execute_generate_migrations()
                self.execute_migrations()
            except Exception as e:
                logging.error(f"Migration cycle failed: {str(e)}")
                if self.max_retries <= 0:
                    break
                self.max_retries -= 1
            time.sleep(self.interval)
   
    def stop_loop(self):
        """停止迁移循环"""
        self.running = False
        logging.info("Auto-migration loop stopped")

# if __name__ == "__main__":
#     # 示例用法
#     local_migration_dir = Path("migrations2")  # 本地迁移目录
#     remote_migration_dir = Path("migrations")  # 远程迁移目录
#     migrator = AutoDatabaseMigrator(
#         local_migration_dir=local_migration_dir,
#         remote_migration_dir=remote_migration_dir,
#         remote_status=1,  # 远程数据库初始状态为离线 
#         interval=30,  # 超时时间为5分钟
#         max_retries=3  # 最大重试次数为3次
#     )
#
#     try:
#         migrator.start_loop()  # 启动迁移循环
#     except KeyboardInterrupt:
#         migrator.stop_loop()  # 手动停止迁移循环
#     finally:
#         print("Migration process completed.")
#
    