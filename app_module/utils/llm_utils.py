import json
import os

from typing import Dict, Any, Optional
from json_repair import repair_json

import requests

from app_module.template.prompts_template import get_prompt_by_document_type
from app_module.core.config import settings

class DeepSeekAPI:
    def __init__(self, api_key: str, base_url: str = "https://ai-base-service.biz.3311csci.com/api/v1"):
        """
        初始化 DeepSeek API 客户端

        Args:
            api_key: DeepSeek API 密钥
            base_url: API 基础 URL，默认为 v1 版本
        """
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }

    def chat_completion(
            self,
            messages: list,
            model: str = "deepseek-v1",
            temperature: float = 0.7,
            stream: bool = False,
            **kwargs
    ) -> Dict[str, Any]:
        """
        调用 DeepSeek 聊天补全 API

        Args:
            messages: 消息列表，格式为 [{"role": "user", "content": "..."}]
            model: 使用的模型名称，默认为 "deepseek-chat"
            temperature: 温度参数，控制输出随机性
            max_tokens: 最大输出 token 数量
            stream: 是否流式输出
            **kwargs: 其他传递给 API 的参数

        Returns:
            API 响应结果
        """
        url = f"{self.base_url}/chat/completions"

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": stream,
            **kwargs
        }

        response = requests.post(url, headers=self.headers, json=payload)

        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"API 请求失败: {response.status_code} - {response.text}")

    def embeddings(self, input_text: str or list, model: str = "deepseek-reasoner") -> Dict[str, Any]:
        """
        调用 DeepSeek 嵌入 API

        Args:
            input_text: 输入文本，可以是单个字符串或字符串列表
            model: 使用的嵌入模型名称

        Returns:
            嵌入向量结果
        """
        url = f"{self.base_url}/embeddings"

        payload = {
            "model": model,
            "input": input_text
        }

        response = requests.post(url, headers=self.headers, json=payload)

        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"API 请求失败: {response.status_code} - {response.text}")


def call_deepseek_api(
        api_key: str,
        messages: list,
        model: str = "deepseek-v3",
        temperature: float = 0.7,
        max_tokens: int = 2048
) -> Optional[Dict[str, Any]]:
    """
    快速调用 DeepSeek API 的便捷函数

    Args:
        api_key: DeepSeek API 密钥
        messages: 消息列表
        model: 模型名称
        temperature: 温度参数
        max_tokens: 最大 token 数

    Returns:
        API 响应或 None（如果请求失败）
    """
    try:
        client = DeepSeekAPI(api_key=api_key)
        results = client.chat_completion(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens
        )

        # 提取 choices 中的第一个 message 的 content
        if 'choices' in results and len(results['choices']) > 0:
            return results['choices'][0]['message']['content']
        else:
            return None
    except Exception as e:
        print(f"调用 DeepSeek API 时发生错误: {e}")
        return None


def generate_prompt(ocr_text: str, document_type: str) -> str:
    """生成适配的Prompt"""
    prompt_template = get_prompt_by_document_type(document_type)
    return prompt_template.format(ocr_text=ocr_text)


def extract_data_with_llm(ocr_text: str,
                          document_type: str = None) -> Optional[Dict[str, Any]]:
    """
    使用大模型直接从OCR文本提取结构化数据的简化方法

    Args:
        ocr_text: OCR识别的文本内容
        document_type: 文档类型（可选）

    Returns:
        结构化数据字典或None（如果调用失败）
    """
    if not ocr_text or ocr_text.strip() == "":
        return None

    # 获取API密钥
    api_key = settings.CSCI_DEEPSEEK_API_KEY

    # 生成prompt
    prompt = generate_prompt(ocr_text, document_type)

    # 创建消息列表
    message = [
        {"role": "user", "content": prompt}
    ]

    # 调用API
    response_content = call_deepseek_api(  # 修正变量名
        api_key=api_key,
        messages=message
    )

    if response_content is None:
        return None

    repaired_content = repair_json(response_content)

    # 解析 JSON
    parsed_data = json.loads(repaired_content)
    return parsed_data


# 使用示例
if __name__ == "__main__":
    # 示例用法
    API_KEY = "sk-YTa0NgyzqHeSQ7g6taKr4WMKwMIWrwUL"

    ocr_text = """
Delivery Note

送貨日期：2023 年 8 月 15 日

Client : Chain State-Alchmix Joint Venture

Address: 將軍澳海水化淡廠第一期將軍澳環保大道 137 堆填區 (中國建築地盤)

(備註:送貨半小時前通知)
Contact : 德仔收
59629254
Invoice No.: SNT2308-0044
Site : CDX
將軍澳海水化淡廠
PO NO: CDX3070

<table>
  <tr>
    <th>箱號</th>
    <th>款式</th>
    <th>數量</th>
  </tr>
  <tr>
    <td>1-1</td>
    <td>MD2402 RHJ600/A 個人安全警報器</td>
    <td>8 部</td>
  </tr>
</table>

Total : 1 箱

Client Authorized Signature & Chop
*Please fax back to 30209751 after confirmation.
    """
    prompt = generate_prompt(ocr_text, "")
    # 创建消息列表
    messages = [
        {"role": "user", "content": prompt},
    ]

    # 调用 API
    result = call_deepseek_api(
        api_key=API_KEY,
        messages=messages
    )

    if result:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("API 调用失败")
