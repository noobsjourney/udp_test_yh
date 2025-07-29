from tokenize import Double
from sqlalchemy.types import REAL, Integer,String,DateTime,Boolean,Float,Enum,Text,Date,Time,Interval,JSON,BigInteger,SmallInteger,DECIMAL,Numeric,CHAR,VARCHAR,BINARY,VARBINARY,BOOLEAN,DATE,TIME,TIMESTAMP,TIMESTAMP
from .modelbase import DataStorageBaseModel,GeneralStorageBaseModel
from datetime import datetime
from sqlalchemy import Column

class  TestModel1(DataStorageBaseModel):
    __tablename__ = "test1"
    __table_args__ = {
        'extend_existing': True,  # 如果表已存在，允许扩展
    }
    __abstract__ =  False
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    qdata = Column(REAL, default=0.0)
    idata = Column(REAL, default=0.0)
    time  = Column(DateTime, default=datetime.now)