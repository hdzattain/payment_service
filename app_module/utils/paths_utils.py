import os
from datetime import datetime


def build_storage_paths(task_id: str):
    """构建存储路径"""
    date_dir = datetime.now().strftime("%Y-%m-%d")
    # base_path = "/ocr_file/store"
    # 使用项目根目录下的临时存储路径
    base_path = os.path.join(os.getcwd(), "temp_files", "store")
    source_path = os.path.join(base_path, date_dir, task_id, "source_file")
    split_path = os.path.join(base_path, date_dir, task_id, "split_file")

    # 创建目录
    os.makedirs(source_path, exist_ok=True)
    os.makedirs(split_path, exist_ok=True)

    return source_path, split_path
