import unittest
from unittest.mock import Mock, call, patch

import requests

from app_module.utils.llm_utils import call_deepseek_api


class LlmUtilsRetryTests(unittest.TestCase):
    @patch("app_module.utils.llm_utils.time.sleep", return_value=None)
    @patch("app_module.utils.llm_utils.DeepSeekAPI.chat_completion")
    def test_call_deepseek_api_retries_retryable_connection_error_then_succeeds(self, mock_chat_completion, mock_sleep):
        mock_chat_completion.side_effect = [
            requests.exceptions.ConnectionError("connection aborted"),
            requests.exceptions.ConnectionError("connection aborted again"),
            {"choices": [{"message": {"content": '{"ok": true}'}}]},
        ]

        result = call_deepseek_api(
            messages=[{"role": "user", "content": "hello"}],
            api_key="test-key",
            model="test-model",
        )

        self.assertEqual(result, '{"ok": true}')
        self.assertEqual(mock_chat_completion.call_count, 3)
        mock_sleep.assert_has_calls([call(1), call(2)])

    @patch("app_module.utils.llm_utils.time.sleep", return_value=None)
    @patch("app_module.utils.llm_utils.DeepSeekAPI.chat_completion")
    def test_call_deepseek_api_does_not_retry_non_retryable_error(self, mock_chat_completion, mock_sleep):
        mock_chat_completion.side_effect = ValueError("bad prompt")

        result = call_deepseek_api(
            messages=[{"role": "user", "content": "hello"}],
            api_key="test-key",
            model="test-model",
        )

        self.assertIsNone(result)
        self.assertEqual(mock_chat_completion.call_count, 1)
        mock_sleep.assert_not_called()

    @patch("app_module.utils.llm_utils.time.sleep", return_value=None)
    @patch("app_module.utils.llm_utils.DeepSeekAPI.chat_completion")
    def test_call_deepseek_api_retries_http_503_and_returns_none_after_exhausted(self, mock_chat_completion, mock_sleep):
        http_error = requests.HTTPError("service unavailable")
        http_error.response = Mock(status_code=503)
        mock_chat_completion.side_effect = [http_error, http_error, http_error]

        result = call_deepseek_api(
            messages=[{"role": "user", "content": "hello"}],
            api_key="test-key",
            model="test-model",
        )

        self.assertIsNone(result)
        self.assertEqual(mock_chat_completion.call_count, 3)
        mock_sleep.assert_has_calls([call(1), call(2)])


if __name__ == "__main__":
    unittest.main()

