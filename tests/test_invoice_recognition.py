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


if __name__ == "__main__":
    unittest.main()


