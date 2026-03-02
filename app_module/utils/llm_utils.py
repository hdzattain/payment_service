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
    prompts = generate_prompt(ocr_text, document_type)

    # 创建消息列表
    message = [
        {"role": "user", "content": prompts}
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

ID：中國CDX / 4224
Customer 中國建築工程(香港)有限公司(海水化淡廠)
客戶：
Attention 卓生 Phone : 9138 2007
Reference DPC/GEN/23003 Fax : 3010 8232

Delivery Note # D23/005012
Date：04 December, 2023
Page：1 of 2
Salesperson CHOW

To：將軍澳海水化淡廠
Ship To：將軍澳海水化淡廠 137 堆填區，翠谷
卓生 9138 2007 / 林生 9215 3007 / 謝生 5962 9254

Delivery 04 December, 2023
Payment 月結
Currency HKD
Shipped FOB

<table>
  <tr>
    <th>#</th>
    <th>Description</th>
    <th>Quantity</th>
  </tr>
  <tr><td>001</td><td>維達三摺式抹手紙(16包/箱)</td><td>30 箱</td></tr>
  <tr><td>002</td><td>維達廁紙 藍色</td><td>60 條</td></tr>
  <tr><td>003</td><td>維達面紙(60盒/箱)</td><td>6 箱</td></tr>
  <tr><td>004</td><td>汽車香座香片</td><td>6 個</td></tr>
  <tr><td>005</td><td>口罩(獨立包裝)</td><td>10 盒</td></tr>
  <tr><td>006</td><td>藥水膠布100片/盒</td><td>2 盒</td></tr>
  <tr><td>007</td><td>防疫面罩(洗廁所用)</td><td>10 個</td></tr>
  <tr><td>008</td><td>透明膠水壺(2.8L)</td><td>2 個</td></tr>
  <tr><td>009</td><td>洗潔精(斧頭牌泵裝)</td><td>3 支</td></tr>
  <tr><td>010</td><td>香必飄空氣清新噴霧(薰衣草味)</td><td>5 支</td></tr>
  <tr><td>011</td><td>潔廁得</td><td>16 支</td></tr>
  <tr><td>012</td><td>思高海綿百潔布(3M長抗菌)</td><td>10 件</td></tr>
  <tr><td>013</td><td>高樂氏漂白水(3L)(大)</td><td>10 支</td></tr>
  <tr><td>014</td><td>金寶鐘綠水(3L)</td><td>2 支</td></tr>
  <tr><td>015</td><td>紅威寶(泵裝)</td><td>3 支</td></tr>
  <tr><td>016</td><td>滴露消毒噴霧</td><td>5 支</td></tr>
  <tr><td>017</td><td>滴露消毒濕紙巾</td><td>17 筒</td></tr>
  <tr><td>018</td><td>NAXOS 酒精噴霧(可皮膚)</td><td>15 支</td></tr>
  <tr><td>019</td><td>威露士洗手皂液</td><td>12 支</td></tr>
  <tr><td>020</td><td>地拖頭 遮棍(釘頭)</td><td>2 支</td></tr>
  <tr><td>021</td><td>掃把頭 (螺絲頭)</td><td>2 支</td></tr>
  <tr><td>022</td><td>細毛巾(白色)</td><td>12 條</td></tr>
  <tr><td>023</td><td>思高Scotch-Brite 吸水抹布</td><td>2 包</td></tr>
  <tr><td>024</td><td>菊花牌膠手套(中碼) 紅色</td><td>6 對</td></tr>
  <tr><td>025</td><td>菊花牌膠手套(中碼) 黃色</td><td>4 對</td></tr>
  <tr><td>026</td><td>36" X 48" 黑色垃圾袋100個/包 厚身</td><td>3 包</td></tr>
  <tr><td>027</td><td>水鞋(38碼)</td><td>1 對</td></tr>
  <tr><td>028</td><td>透明即棄膠手套(100只/盒)(白色M碼)</td><td>11 盒</td></tr>
  <tr><td>029</td><td>大垃圾桶連蓋16" X 17" X 24" (45L) 腳踏灰色</td><td>4 個</td></tr>
</table>

to be Continued
    """
    prompt = generate_prompt(ocr_text, "delivery_note")
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
