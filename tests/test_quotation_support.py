import unittest
from unittest.mock import patch

from app_module.services.document_type_recognizer import document_type_recognizer
from app_module.template.prompts_template import get_prompt_by_document_type
from app_module.services.ocr_task_service import extract_quotation_data, extract_structured_data_from_ocr
from app_module.utils.datetime_utils import normalize_quotation_date


QUOTATION_TEXT = """
# Quotation
Quotation No. : HQ22-0670
Quotation Date : 29 Apr 2022
Messrs. : CHINA STATE CONST. ENG'G (H.K.) LTD.
Site/Project : Contract No.: 12/WSD/17
Design, Build and Operate First Stage of Tseung Kwan O Desalination Plant
Net Amount : HK$ 0.00
"""


class QuotationSupportTests(unittest.TestCase):
    def test_normalize_quotation_date_from_utils(self):
        self.assertEqual(normalize_quotation_date("29 Apr 2022"), "2022-04-29")
        self.assertEqual(normalize_quotation_date("2023年12月29日"), "2023-12-29")

    def test_recognize_quotation_by_quotation_no_and_date(self):
        recognition = document_type_recognizer.recognize(
            "Quotation No. : HQ22-0670\nQuotation Date : 29 Apr 2022\n"
        )
        self.assertEqual(recognition["document_type"], "quotation")

    def test_prompt_mapping_returns_quotation_prompt(self):
        prompt = get_prompt_by_document_type("quotation")
        self.assertIn('"document_type": "quotation"', prompt)
        self.assertIn('quotation_date', prompt)
        self.assertIn('{ocr_text}', prompt)
        self.assertIn('`supplier_name` 优先取英文主名', prompt)
        self.assertIn('Calibration Services', prompt)
        self.assertIn('Other', prompt)
        self.assertIn('Net Amount', prompt)
        self.assertIn('"supplier_name": "HONG KONG TESTING CO., LTD."', prompt)
        self.assertIn('"product_service_specification": "CS1 : 2010 Vol. 1 App. A28"', prompt)
        self.assertIn('"product_service_name": "Sample collection charge"', prompt)

    @patch("app_module.services.ocr_task_service.merge_structured_data_with_llm")
    def test_extract_quotation_data_seeds_document_no_and_normalized_date(self, mock_merge):
        mock_merge.side_effect = lambda regex_data, *_args, **_kwargs: (dict(regex_data), None)

        result = extract_quotation_data(QUOTATION_TEXT)

        self.assertEqual(result["document_type"], "quotation")
        self.assertEqual(result["structured_data"]["document_no"], "HQ22-0670")
        self.assertEqual(result["structured_data"]["quotation_date"], "2022-04-29")
        self.assertEqual(result["structured_data"]["document_type"], "quotation")
        self.assertEqual(result["structured_data"]["customer_name"], "CHINA STATE CONST. ENG'G (H.K.) LTD.")
        self.assertIn("12/WSD/17", result["structured_data"]["project_name"])
        self.assertEqual(result["structured_data"]["currency"], "HK$")
        self.assertEqual(result["structured_data"]["total_amount"], "0.00")

    @patch("app_module.services.ocr_task_service.merge_structured_data_with_llm")
    def test_extract_structured_data_from_ocr_routes_to_quotation(self, mock_merge):
        mock_merge.side_effect = lambda regex_data, *_args, **_kwargs: (dict(regex_data), None)

        result = extract_structured_data_from_ocr(QUOTATION_TEXT)

        self.assertEqual(result["document_type"], "quotation")
        self.assertEqual(result["structured_data"]["document_no"], "HQ22-0670")
        self.assertEqual(result["structured_data"]["quotation_date"], "2022-04-29")


if __name__ == "__main__":
    unittest.main()



