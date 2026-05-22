import unittest

from app_module.services.document_type_recognizer import document_type_recognizer


INVOICE_LIKE_TEXT_WITH_CHINESE_KEYWORD = """
楊水搬運有限公司
YEUNG SUI TRANSPORTATION COMPANY LIMITED

To:
中國建築工程(香港)有限公司

Date: 28/12/2022
Description: 2022年12月份送鐵運費單
Debit Note No: 71559

Total Amount: 1,516.70
收發票日期
31 DEC 2022
"""

INVOICE_TEXT_WITH_MIXED_TITLE_AND_TRADITIONAL_NUMBER = """
劉祥利鑄造廠有限公司
商戶：中國建築工程(香港)有限公司
發票號：20624
發 INVOICE 票
日期：09-05-2024
"""

INVOICE_TEXT_WITH_MIXED_TITLE_AND_SIMPLIFIED_NUMBER = """
上海供應商有限公司
客户：测试项目部
发票号：INV-2026-001
发INVOICE票
日期：2026-05-22
"""

INVOICE_MIXED_TITLE_VARIANTS = [
    "發invoice票",
    "發 invoice 票",
    "发 invoice 票",
    "发invoice票",
]


class InvoiceRecognitionTests(unittest.TestCase):
    def test_recognize_invoice_when_markdown_title_contains_english_keyword(self):
        recognition = document_type_recognizer.recognize("# Tax Invoice\nInvoice No: INV-001\n")
        self.assertEqual(recognition["document_type"], "invoice")
        self.assertEqual(recognition["matched_by"], "strong_rule")

    def test_recognize_invoice_when_markdown_title_contains_chinese_keyword(self):
        recognition = document_type_recognizer.recognize("# 供應商發票\n日期：2026-05-20\n")
        self.assertEqual(recognition["document_type"], "invoice")
        self.assertEqual(recognition["matched_by"], "strong_rule")

    def test_recognize_invoice_when_chinese_invoice_keyword_exists(self):
        recognition = document_type_recognizer.recognize(INVOICE_LIKE_TEXT_WITH_CHINESE_KEYWORD)
        self.assertEqual(recognition["document_type"], "invoice")
        self.assertEqual(recognition["matched_by"], "score")

    def test_recognize_invoice_when_mixed_title_and_traditional_invoice_number_exist(self):
        recognition = document_type_recognizer.recognize(INVOICE_TEXT_WITH_MIXED_TITLE_AND_TRADITIONAL_NUMBER)
        self.assertEqual(recognition["document_type"], "invoice")
        self.assertEqual(recognition["matched_by"], "strong_rule")
        self.assertEqual(recognition["scores"]["invoice"], 100)

    def test_recognize_invoice_when_mixed_title_and_simplified_invoice_number_exist(self):
        recognition = document_type_recognizer.recognize(INVOICE_TEXT_WITH_MIXED_TITLE_AND_SIMPLIFIED_NUMBER)
        self.assertEqual(recognition["document_type"], "invoice")
        self.assertEqual(recognition["matched_by"], "strong_rule")
        self.assertEqual(recognition["scores"]["invoice"], 100)

    def test_recognize_invoice_when_requested_mixed_title_variants_exist(self):
        for mixed_title in INVOICE_MIXED_TITLE_VARIANTS:
            with self.subTest(mixed_title=mixed_title):
                recognition = document_type_recognizer.recognize(
                    f"供应商\n发票号：INV-001\n{mixed_title}\n日期：2026-05-22\n"
                )
                self.assertEqual(recognition["document_type"], "invoice")
                self.assertEqual(recognition["matched_by"], "strong_rule")
                self.assertEqual(recognition["scores"]["invoice"], 100)


if __name__ == "__main__":
    unittest.main()


