import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app_module.api.task import ocr_api

ROOT = Path('/root/service')
SAMPLE_PDF = ROOT / 'benchmark/samples/transaction/transaction_record_1.pdf'


class CreateOcrTaskPageTotalTests(unittest.TestCase):
    def test_create_task_returns_page_total_and_persists_file_page(self):
        queue_manager = SimpleNamespace(submit_task=AsyncMock(return_value=True))
        request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(ocr_task_queue=queue_manager)))
        param = ocr_api.CreateOCRRequest(
            file_url='https://example.test/sample.pdf',
            foreign_id='tracstrack_001',
            callback_url='https://example.test/callback',
            merge_mode=True,
        )
        created_tasks = []

        def create_task(task_data):
            created_tasks.append(dict(task_data))

        with tempfile.TemporaryDirectory() as td:
            downloaded_pdf = Path(td) / 'sample.pdf'
            downloaded_pdf.write_bytes(SAMPLE_PDF.read_bytes())

            with patch.object(ocr_api, 'download_file_from_url', AsyncMock(return_value=str(downloaded_pdf))):
                with patch.object(ocr_api, 'OcrTaskMapper') as mapper_cls:
                    mapper = mapper_cls.return_value
                    mapper.create_task.side_effect = create_task
                    response = asyncio.run(ocr_api.create_ocr_task(param, request, object()))

        self.assertEqual(response.status_code, 200)
        body = json.loads(response.body.decode('utf-8'))
        self.assertEqual(body['code'], 200)
        self.assertEqual(body['data']['page_total'], 3)
        self.assertRegex(body['data']['task_id'], r'^ocr_\d{14}_[0-9a-f-]{8}$')
        self.assertEqual(created_tasks[0]['file_page'], 3)
        queue_manager.submit_task.assert_awaited_once()


if __name__ == '__main__':
    unittest.main()
