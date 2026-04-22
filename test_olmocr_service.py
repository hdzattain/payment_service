import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from app_module.olmocr_module import olmocr_service


class TestOlmOcrService(unittest.TestCase):
    def _create_temp_pdf(self) -> str:
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        temp_file.write(b"%PDF-1.4\n% test\n")
        temp_file.flush()
        temp_file.close()
        self.addCleanup(lambda: os.path.exists(temp_file.name) and os.remove(temp_file.name))
        return temp_file.name

    @patch("app_module.olmocr_module.olmocr_service.time.sleep")
    @patch("app_module.olmocr_module.olmocr_service.requests.post")
    def test_submit_ocr_request_retries_after_429(self, mock_post, mock_sleep):
        pdf_path = self._create_temp_pdf()

        rate_limited_response = MagicMock()
        rate_limited_response.status_code = 429
        rate_limited_response.headers = {"Retry-After": "0"}

        success_response = MagicMock()
        success_response.status_code = 200
        success_response.headers = {}
        success_response.json.return_value = {
            "task_id": "task-1",
            "check_status_url": "https://example.com/status/task-1",
            "download_url": "https://example.com/download/task-1"
        }

        mock_post.side_effect = [rate_limited_response, success_response]

        with patch.object(olmocr_service, "OCR_SUBMIT_MAX_RETRIES", 2), \
                patch.object(olmocr_service, "OCR_SUBMIT_MIN_INTERVAL_SECONDS", 0):
            data, error = olmocr_service._submit_ocr_request(pdf_path, os.path.basename(pdf_path))

        self.assertIsNone(error)
        self.assertEqual(data["task_id"], "task-1")
        self.assertEqual(mock_post.call_count, 2)
        mock_sleep.assert_called()

    @patch("app_module.olmocr_module.olmocr_service.time.sleep")
    @patch("app_module.olmocr_module.olmocr_service.requests.post")
    def test_submit_ocr_request_returns_429_when_retries_exhausted(self, mock_post, mock_sleep):
        pdf_path = self._create_temp_pdf()

        rate_limited_response = MagicMock()
        rate_limited_response.status_code = 429
        rate_limited_response.headers = {"Retry-After": "0"}
        mock_post.return_value = rate_limited_response

        with patch.object(olmocr_service, "OCR_SUBMIT_MAX_RETRIES", 1), \
                patch.object(olmocr_service, "OCR_SUBMIT_MIN_INTERVAL_SECONDS", 0):
            data, error = olmocr_service._submit_ocr_request(pdf_path, os.path.basename(pdf_path))

        self.assertIsNone(data)
        self.assertEqual(error["code"], 429)
        self.assertEqual(error["status_code"], 429)
        self.assertEqual(mock_post.call_count, 2)
        mock_sleep.assert_called()


if __name__ == "__main__":
    unittest.main()

