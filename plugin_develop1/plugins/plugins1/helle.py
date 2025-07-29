
Model
class Users(GeneralStorageBaseModel):
    __tablename__ = 'users'  # 表名
    __table_args__ = {
        'extend_existing': True  # 如果表已存在，允许扩展
    }
    __abstract__ =  False
    id = Column(Integer, primary_key=True, autoincrement=True)  # 主键，自增
    name = Column(String(50), nullable=False)  # 非空字符串字段
    age = Column(Integer,default = 18)  # 整数字段
    email = Column(String(100), unique=True)  # 唯一字符串字段
    created_at = Column(DateTime, default=datetime)  # 日期时间字段，默认当前时间
    updated_at = Column(DateTime, default=datetime, onupdate=datetime.now)

class datas(GeneralStorageBaseModel):