import asyncio
import tempfile
import urllib.parse
import os
from pathlib import Path

import aiohttp


async def download_file_from_url(
        url: str,
        source_path: str,
        chunk_size: int = 8192,
        timeout: int = 30,
        max_retries: int = 3,
        default_suffix: str = '.pdf'
) -> str:
    """
    从URL流式下载文件到临时目录（带超时和重试）
    :param url: 文件URL
    :param source_path: 文件存储路径，如果为空则使用临时文件
    :param chunk_size: 每次读取的块大小
    :param timeout: 超时时间（秒）
    :param max_retries: 最大重试次数
    :param default_suffix: 默认文件扩展名
    :return: 临时文件路径
    """
    for attempt in range(max_retries + 1):
        try:
            timeout_config = aiohttp.ClientTimeout(total=timeout)
            async with aiohttp.ClientSession(timeout=timeout_config) as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        raise Exception(f"下载文件失败: {response.status}")

                    # 从URL或响应头中提取文件扩展名
                    file_suffix = extract_file_extension(url, response)
                    if not file_suffix:
                        file_suffix = default_suffix

                    # 确保 source_path 是目录路径
                    if not os.path.isdir(source_path):
                        # 如果 source_path 不是目录，需要构建完整路径
                        filename = extract_filename_from_url(url)
                        full_path = os.path.join(source_path, filename)
                    else:
                        filename = extract_filename_from_url(url)
                        full_path = os.path.join(source_path, filename)

                    # 确保目录存在
                    os.makedirs(source_path, exist_ok=True)
                    with open(full_path, 'wb') as temp_file:
                        async for chunk in response.content.iter_chunked(chunk_size):
                            temp_file.write(chunk)
                    return full_path
        except Exception as e:
            if attempt == max_retries:
                raise e
            await asyncio.sleep(2 ** attempt)  # 指数退避


def extract_filename_from_url(url: str) -> str:
    """从URL中提取文件名"""
    parsed_url = urllib.parse.urlparse(url)
    filename = os.path.basename(parsed_url.path)
    if not filename or '.' not in filename:
        # 如果URL中没有文件名，使用默认名称
        return f"downloaded_file{extract_file_extension(url)}"
    return filename


def extract_file_extension(url: str, response=None) -> str:
    """
    从URL或响应头中提取文件扩展名
    :param url: 文件URL
    :param response: HTTP响应对象（可选）
    :return: 文件扩展名（包含点号）
    """
    # 从URL路径中提取扩展名
    parsed_url = urllib.parse.urlparse(url)
    path = parsed_url.path
    suffix = Path(path).suffix.lower()

    if suffix:
        return suffix

    # 如果URL中没有扩展名，尝试从响应头的Content-Type推断
    if response:
        content_type = response.headers.get('content-type', '').split(';')[0].strip()
        mime_to_ext = {
            'application/pdf': '.pdf',
            'application/msword': '.doc',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx',
            'application/vnd.ms-excel': '.xls',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': '.xlsx',
            'image/jpeg': '.jpg',
            'image/png': '.png',
            'image/gif': '.gif',
            'text/plain': '.txt',
            'application/zip': '.zip'
        }

        return mime_to_ext.get(content_type, '')