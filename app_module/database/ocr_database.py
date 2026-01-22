from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool

# 数据库连接配置
DATABASE_URL = ("mysql+pymysql://root:Y4t8btvdPqhl%Qgg@hk-cynosdbmysql-grp-bfn4zq51.sql.tencentcdb.com:24778"
                "/ocr_payment_test?charset=utf8mb4")

# 创建引擎
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=100,
    pool_pre_ping=True,
    echo=False  # 设为True可查看SQL执行日志
)

# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """获取数据库会话的依赖注入函数"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
