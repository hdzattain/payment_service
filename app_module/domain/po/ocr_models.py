from sqlalchemy import Column, Integer, String, DateTime, Text, SmallInteger
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime, UTC

Base = declarative_base()


def utcnow_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class OcrTask(Base):
    __tablename__ = 'ocr_tasks'

    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键id')
    task_id = Column(String(255), nullable=False, unique=True, comment='任务Id')
    foreign_id = Column(String(255), comment='外部系统Id')
    callback_url = Column(String(500), comment='回调url')
    file_url = Column(String(500), comment='文件url')
    local_path = Column(String(500), comment='文件本地存储路径')
    file_page = Column(Integer, comment='文件页数')
    is_full_type = Column(SmallInteger, default=0, comment='票据是否齐全 0-否 1-是')
    merge_mode = Column(SmallInteger, default=0, comment='是否启用合并模式 0-否 1-是')
    status = Column(SmallInteger, default=0, comment='执行状态 0-待执行、1-执行中、2-执行成功、3-执行失败、4-部分执行失败')
    confidence = Column(String(32), comment='任务平均置信度')
    heuristic_confidence = Column(String(32), comment='任务平均启发式置信度')
    create_id = Column(String(255), default='1000000000000', comment='创建者id')
    update_id = Column(String(255), default='1000000000000', comment='更新者id')
    create_datetime = Column(DateTime, default=utcnow_naive, comment='创建时间')
    update_datetime = Column(DateTime, default=utcnow_naive, onupdate=utcnow_naive, comment='更新时间')


class OcrTaskDetail(Base):
    __tablename__ = 'ocr_tasks_detail'

    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键id')
    task_id = Column(String(255), nullable=False, comment='任务Id')
    page_no = Column(Integer, comment='识别页码')
    file_url = Column(String(255), comment='分割文件url')
    document_type = Column(String(32), comment='文件类型')
    ocr_task_id = Column(String(255), comment='olmocr任务id')
    group_id = Column(String(200), comment='分组ID（document_no）')
    status = Column(SmallInteger, default=0, comment='执行状态 0-待执行、1-执行中、2-执行成功、3-执行失败')
    confidence = Column(String(32), comment='页级置信度')
    heuristic_confidence = Column(String(32), comment='页级启发式置信度')
    ocr_text = Column(Text, comment='OCR识别内容类型')
    structured_data = Column(Text, comment='结构化数据JSON')
    single_structured_data = Column(Text, comment='单页结构化提取数据')
    llm_structured_data = Column(Text, comment='LLM结构化提取数据')
    regex_structured_data = Column(Text, comment='规则匹配结构化提取数据')
    create_id = Column(String(255), default='1000000000000', comment='创建者id')
    update_id = Column(String(255), default='1000000000000', comment='更新者id')
    create_datetime = Column(DateTime, default=utcnow_naive, comment='创建时间')
    update_datetime = Column(DateTime, default=utcnow_naive, onupdate=utcnow_naive, comment='更新时间')


class OcrTaskCallbackRecord(Base):
    __tablename__ = 'ocr_task_callback_record'

    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键id')
    task_id = Column(String(255), nullable=False, index=True, comment='任务Id')
    foreign_id = Column(String(255), comment='外部系统Id')
    callback_url = Column(String(500), comment='回调url')
    page_no = Column(String(255), comment='回调页码，单页如1，多页如[1,2]')
    callback_seq = Column(Integer, comment='回调序号')
    callback_total = Column(Integer, comment='计划回调总数')
    is_final_callback = Column(SmallInteger, default=0, comment='是否最终回调 0-否 1-是')
    callback_status = Column(SmallInteger, comment='回调报文状态 0-待执行、1-执行中、2-成功、3-失败、4-部分失败')
    send_status = Column(SmallInteger, default=0, index=True, comment='发送结果 0-待发送、1-发送成功、2-HTTP失败、3-业务失败、4-发送异常')
    http_status = Column(Integer, comment='HTTP状态码')
    business_code = Column(String(64), comment='响应业务码')
    request_body = Column(Text, comment='回调请求报文JSON')
    response_body = Column(Text, comment='回调响应内容')
    error_message = Column(String(1000), comment='失败原因或异常信息')
    request_datetime = Column(DateTime, comment='请求发起时间')
    response_datetime = Column(DateTime, comment='请求响应时间')
    create_datetime = Column(DateTime, default=utcnow_naive, comment='创建时间')
    update_datetime = Column(DateTime, default=utcnow_naive, onupdate=utcnow_naive, comment='更新时间')

