import unittest
from unittest.mock import patch

from app_module.services.document_type_recognizer import document_type_recognizer
from app_module.services.ocr_task_service import extract_structured_data_from_ocr
from app_module.template.prompts_template import get_prompt_by_document_type


PAYMENT_REQUEST_FORM_TEXT = """
# 物資付款辦理單

地盤名稱：將軍澳海水化淡廠第一階段(CDX)
材料分類：小五金材料(M20)
制單日期：2023年12月6日
客商名稱：永新五金工程有限公司(WGS)
付辦單號：CDX/2312/A/0015
合約編號：DPC/GEN/23003/00
發票日期：2023年12月4日
幣種：港元
付款方式：支票

<table>
  <tr><th>本期發生</th></tr>
  <tr><td>19,216.00</td></tr>
</table>
"""

PAYMENT_REQUEST_FORM_DETAIL_TEXT = """
# 材料付办单附表－摘要明細

# CDX/2306/A/0008

| 費用類型 | 描述 | 數量 | 單價 | 金額 |
|---|---|---:|---:|---:|
| 服務費用 | Calibration service | 1.00項 | 160.000 | 160.00 |

- 合计：160.00
"""


class PaymentRequestFormSupportTests(unittest.TestCase):
    def test_recognize_payment_request_form(self):
        recognition = document_type_recognizer.recognize(PAYMENT_REQUEST_FORM_TEXT)

        self.assertEqual(recognition["document_type"], "payment_request_form")

    def test_recognize_payment_request_form_detail(self):
        recognition = document_type_recognizer.recognize(PAYMENT_REQUEST_FORM_DETAIL_TEXT)

        self.assertEqual(recognition["document_type"], "payment_request_form_detail")

    def test_prompt_mapping_returns_payment_request_form_prompt(self):
        prompt = get_prompt_by_document_type("payment_request_form")

        self.assertIn('"document_type": "payment_request_form"', prompt)
        self.assertIn('{ocr_text}', prompt)

    def test_prompt_mapping_returns_payment_request_form_detail_prompt(self):
        prompt = get_prompt_by_document_type("payment_request_form_detail")

        self.assertIn('"document_type": "payment_request_form_detail"', prompt)
        self.assertIn('{ocr_text}', prompt)

    def test_prompt_mapping_does_not_use_legacy_aliases(self):
        payment_request_form_prompt = get_prompt_by_document_type("payment_request_form")
        payment_request_form_detail_prompt = get_prompt_by_document_type("payment_request_form_detail")

        self.assertIn('"document_type": "payment_request_form"', payment_request_form_prompt)
        self.assertIn('"document_type": "payment_request_form_detail"', payment_request_form_detail_prompt)

    @patch("app_module.services.ocr_task_service.merge_structured_data_with_llm")
    def test_extract_structured_data_from_ocr_routes_to_payment_request_form(self, mock_merge):
        mock_merge.side_effect = lambda regex_data, *_args, **_kwargs: (dict(regex_data), None)

        result = extract_structured_data_from_ocr(PAYMENT_REQUEST_FORM_TEXT)

        self.assertEqual(result["document_type"], "payment_request_form")
        self.assertEqual(result["structured_data"]["document_type"], "payment_request_form")
        self.assertEqual(result["structured_data"]["document_no"], "CDX/2312/A/0015")

    @patch("app_module.services.ocr_task_service.merge_structured_data_with_llm")
    def test_extract_structured_data_from_ocr_routes_to_payment_request_form_detail(self, mock_merge):
        mock_merge.side_effect = lambda regex_data, *_args, **_kwargs: (dict(regex_data), None)

        result = extract_structured_data_from_ocr(PAYMENT_REQUEST_FORM_DETAIL_TEXT)

        self.assertEqual(result["document_type"], "payment_request_form_detail")
        self.assertEqual(result["structured_data"]["document_type"], "payment_request_form_detail")
        self.assertIn("product_service", result["structured_data"])


if __name__ == "__main__":
    unittest.main()





