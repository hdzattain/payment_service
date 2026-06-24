"""
飞书消息推送工具类 Python 实现
"""
import json
import time
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any

import requests

from app_module.core.config import settings
from app_module.logger.logger_config import setup_logger

# 初始化日志记录器
logger = setup_logger("feishu_utils")


@dataclass
class SendMsgDTO:
    """
    发送消息参数
    """
    receive_id_type: str  # 接收者 ID 类型: open_id, union_id, user_id, email, chat_id
    msg_type: str  # 消息类型
    content: str  # 消息内容
    receive_id: str  # 消息接收者的 ID
    uuid: Optional[str] = None  # 唯一字符串序列，用于去重

    def to_dict(self):
        """转换为字典格式"""
        result = {}
        if self.receive_id_type:
            result['receive_id_type'] = self.receive_id_type
        if self.msg_type:
            result['msg_type'] = self.msg_type
        if self.content:
            result['content'] = self.content
        if self.receive_id:
            result['receive_id'] = self.receive_id
        if self.uuid:
            result['uuid'] = self.uuid
        return result


@dataclass
class BatchSendMsgDTO:
    """
    批量发送消息参数
    """
    user_ids: List[str]
    msg_type: str
    content: str
    uuid: Optional[str] = None

    def to_dict(self):
        """转换为字典格式"""
        result = asdict(self)
        # 移除空值
        return {k: v for k, v in result.items() if v is not None}


@dataclass
class FeiShuResultDTO:
    """
    飞书接口返回结果封装
    """
    code: int
    data: Optional[Any] = None
    msg: Optional[str] = None

    def check_and_get_data(self):
        """校验并返回数据"""
        if self.code != 0:
            logger.error(f"请求飞书出现异常, {self}")
            raise Exception(f"请求飞书出现异常: {self.msg}")
        return self.data


@dataclass
class FeiShuTenantAccessTokenDTO:
    """
    飞书租户访问令牌
    """
    tenant_access_token: str
    expire: int


@dataclass
class ErrorLog:
    """
    错误日志数据对象
    """
    id: str
    result_msg: str
    result_code: Optional[int] = None
    result_data: Optional[str] = None


class InteractiveMsgCreate:
    """
    交互式卡片消息创建工具类
    对应Java版本的InteractiveMsgCreate
    """

    @staticmethod
    def error_msg(body_elements: List[Dict], server: str) -> str:
        # 合并所有元素
        all_elements = body_elements.copy()

        return InteractiveMsgCreate._create_interactive_msg("red", server, all_elements)

    @staticmethod
    def _create_interactive_msg(color: str, title: str, elements: List[Dict]) -> str:
        """
        创建交互式卡片消息
        """
        card_data = {
            "config": {
                "wide_screen_mode": True
            },
            "header": {
                "template": color,
                "title": {
                    "content": title,
                    "tag": "plain_text"
                }
            },
            "elements": elements
        }
        return json.dumps(card_data, ensure_ascii=False)

    @staticmethod
    def element_body_msg(error_log: ErrorLog) -> List[Dict]:
        """
        创建飞书element-body消息
        返回元素列表而不是字符串
        """
        # 转义双引号以避免JSON格式问题
        escaped_result_msg = error_log.result_msg.replace('"', '\\"')

        elements = [
            {
                "tag": "div",
                "text": {
                    "content": f"** 任务ID：**{error_log.id}",
                    "tag": "lark_md"
                }
            },
            {
                "tag": "div",
                "text": {
                    "content": f"** 错误内容：**{escaped_result_msg}",
                    "tag": "lark_md"
                }
            }
        ]

        return elements

    @staticmethod
    def element_foot_msg(content: str) -> List[Dict]:
        """
        创建飞书element底部消息
        返回元素列表而不是字符串
        """
        escaped_content = content.replace('"', '\\"')
        return [
            {"tag": "hr"},
            {
                "elements": [
                    {
                        "content": escaped_content,
                        "tag": "lark_md"
                    }
                ],
                "tag": "note"
            }
        ]


class FeiShuConfig:
    """
    飞书配置类
    """

    def __init__(self):
        # 从全局配置获取飞书设置
        self.bot_group_id = settings.FEISHU_BOT_GROUP_ID

        # 应用配置
        self.apps = {
            'web': {
                'web_app_id': settings.FEISHU_APP_ID,
                'web_app_secret': settings.FEISHU_APP_SECRET
            }
        }

        # API 地址配置
        self.api_urls = {
            'tenant_access_token': 'https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal',
            'send_msg': 'https://open.feishu.cn/open-apis/im/v1/messages',
            'batch_send_msg': 'https://open.feishu.cn/open-apis/im/v1/messages/batch_send'
        }


class FeiShuUtils:
    """
    飞书工具类 Python 实现
    """
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self.__class__._initialized:
            self.config = FeiShuConfig()
            self._token_cache = {}
            self.__class__._initialized = True

    def _make_request(self, method: str, url: str, headers: Dict, data: Optional[Dict] = None) -> Dict:
        """发送HTTP请求"""
        try:
            if method.upper() == 'GET':
                response = requests.get(url, headers=headers, params=data)
            elif method.upper() == 'POST':
                response = requests.post(url, headers=headers, json=data)
            else:
                raise ValueError(f"不支持的请求方法: {method}")

            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"请求飞书接口失败: {e}, URL: {url}")
            raise

    def _obj_to_json(self, obj) -> str:
        """对象转JSON字符串"""
        if hasattr(obj, 'to_dict'):
            obj_dict = obj.to_dict()
        else:
            obj_dict = asdict(obj) if hasattr(obj, '__dataclass_fields__') else obj

        # 确保中文字符正常显示
        return json.dumps(obj_dict, ensure_ascii=False)

    def get_tenant_access_token(self, app_type: str = 'web') -> FeiShuTenantAccessTokenDTO:
        """
        获取租户访问令牌
        """
        app = self.config.apps.get(app_type)
        if not app:
            raise ValueError(f"未找到应用配置: {app_type}")

        # 根据应用类型选择正确的字段
        if app_type == 'web':
            app_id = app.get('web_app_id')
            app_secret = app.get('web_app_secret')
        else:
            app_id = app.get('app_id')
            app_secret = app.get('app_secret')

        if not app_id or not app_secret:
            raise ValueError(f"应用配置不完整: {app_type}")

        cache_key = f"{app_id}_{app_secret}"

        # 检查缓存
        cached_token = self._token_cache.get(cache_key)
        if cached_token:
            # 检查是否即将过期（提前30秒刷新）
            if time.time() < cached_token['expire_time'] - 30:
                return FeiShuTenantAccessTokenDTO(
                    tenant_access_token=cached_token['token'],
                    expire=int(cached_token['expire_time'] - time.time())
                )

        # 请求新令牌
        data = {
            'app_id': app_id,
            'app_secret': app_secret
        }

        headers = {'Content-Type': 'application/json; charset=utf-8'}
        response = self._make_request('POST', self.config.api_urls['tenant_access_token'], headers, data)

        if 'tenant_access_token' not in response:
            raise Exception(f"获取租户访问令牌失败: {response}")

        token = response['tenant_access_token']
        expire = response.get('expire', 7200)  # 默认2小时

        # 缓存令牌
        expire_time = time.time() + expire
        self._token_cache[cache_key] = {
            'token': token,
            'expire_time': expire_time
        }

        return FeiShuTenantAccessTokenDTO(tenant_access_token=token, expire=expire)

    def send_msg(self, params: SendMsgDTO) -> Optional[str]:
        """
        发送消息
        """
        token = self.get_tenant_access_token().tenant_access_token

        # 构建请求URL - 移除receive_id_type参数，因为它现在在请求体中
        base_url = self.config.api_urls['send_msg']

        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json; charset=utf-8'
        }

        # 准备请求体数据，包含接收者ID和消息内容
        request_body = {
            'receive_id': params.receive_id,
            'receive_id_type': params.receive_id_type,
            'msg_type': params.msg_type,
            'content': params.content
        }

        # 添加UUID（如果提供）
        if params.uuid:
            request_body['uuid'] = params.uuid

        # 添加接收者ID类型参数到URL
        url_with_params = f"{base_url}?receive_id_type={params.receive_id_type}"

        response = self._make_request('POST', url_with_params, headers, request_body)

        result = FeiShuResultDTO(**response)

        # 非0表示失败
        if result.code != 0:
            logger.error(f"发送消息失败 {result}")
            return None

        data = result.check_and_get_data()
        return data.get('message_id') if isinstance(data, dict) else None

    def batch_send_msg(self, params: BatchSendMsgDTO):
        """
        批量发送消息
        飞书限制最多200条一次
        """
        token = self.get_tenant_access_token().tenant_access_token

        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json; charset=utf-8'
        }

        # 按200条分批处理
        user_ids = params.user_ids[:]
        batch_size = 200

        for i in range(0, len(user_ids), batch_size):
            batch_user_ids = user_ids[i:i + batch_size]
            batch_params = BatchSendMsgDTO(
                user_ids=batch_user_ids,
                msg_type=params.msg_type,
                content=params.content,
                uuid=params.uuid
            )

            response = self._make_request('POST', self.config.api_urls['batch_send_msg'], headers,
                                          batch_params.to_dict())

            result = FeiShuResultDTO(**response)

            # 非0表示失败
            if result.code != 0:
                logger.error(f"批量发送消息失败 {result}")
                continue

            data = result.check_and_get_data()
            if isinstance(data, dict) and data.get('invalid_user_ids'):
                logger.warning(f"批量发送消息未完全成功, 这些用户ID不合法 {data['invalid_user_ids']}")

    def send_error_log_message(self, error_log: ErrorLog, receive_id: str = None,
                               server_name: str = "Payment AI OCR 服务"):
        """
        发送错误日志消息的便捷方法

        Args:
            error_log: ErrorLog对象，包含错误信息
            receive_id: 接收者ID，默认使用配置中的群ID
            server_name: 服务器名称，默认为"系统"

        Returns:
            发送结果，成功返回消息ID，失败返回None
        """
        # 使用配置中的群ID作为默认接收ID
        target_receive_id = receive_id or self.config.bot_group_id

        # 生成卡片消息body
        body_elements = InteractiveMsgCreate.element_body_msg(error_log)

        # 组装卡片消息
        content = InteractiveMsgCreate.error_msg(
            body_elements,
            server_name,
        )

        # 构建消息参数
        msg_params = SendMsgDTO(
            receive_id_type='chat_id',  # 根据实际情况调整类型
            msg_type='interactive',
            content=content,
            receive_id=target_receive_id
        )

        # 发送消息
        return self.send_msg(msg_params)


# 创建全局实例
feishu_client = FeiShuUtils()

# 使用示例
if __name__ == "__main__":
    # 创建操作日志对象
    error_log = ErrorLog(
        id="123",
        result_msg="系统出现异常"
    )

    result = feishu_client.send_error_log_message(error_log)
    print(f"消息发送结果: {result}")
