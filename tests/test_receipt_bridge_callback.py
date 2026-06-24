import json
import unittest
from types import SimpleNamespace

from app_module.services.ocr_task_service import _select_callback_detail_for_pages


def make_detail(page_no: int, structured_data):
    raw = None if structured_data is None else json.dumps(structured_data, ensure_ascii=False)
    return SimpleNamespace(
        page_no=page_no,
        structured_data=raw,
        confidence=None,
        heuristic_confidence=None,
        create_datetime=None,
    )


class ReceiptBridgeCallbackTests(unittest.TestCase):
    def test_prefers_payment_request_form_page_for_bridge_callback_raw(self):
        detail_by_page = {
            1: make_detail(1, {"document_type": "payment_request_form_detail", "document_no": "R-001"}),
            2: make_detail(2, {"document_type": "payment_request_form", "document_no": "R-001", "total_amount": "100.00"}),
        }

        detail_info, selected_details = _select_callback_detail_for_pages([1, 2], detail_by_page)

        self.assertIsNotNone(detail_info)
        self.assertEqual(detail_info.page_no, 2)
        self.assertEqual([detail.page_no for detail in selected_details], [1, 2])

    def test_falls_back_to_first_detail_with_raw_when_no_primary_page_exists(self):
        detail_by_page = {
            3: make_detail(3, None),
            4: make_detail(4, {"document_type": "payment_request_form_detail", "document_no": "R-002"}),
        }

        detail_info, selected_details = _select_callback_detail_for_pages([3, 4], detail_by_page)

        self.assertIsNotNone(detail_info)
        self.assertEqual(detail_info.page_no, 4)
        self.assertEqual([detail.page_no for detail in selected_details], [3, 4])


if __name__ == "__main__":
    unittest.main()

