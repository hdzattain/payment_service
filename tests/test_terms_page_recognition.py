import unittest

from app_module.services.document_type_recognizer import document_type_recognizer


TERMS_PAGE_WITH_MARKDOWN_TITLES = """
# Page 3 of 3
# General Terms and Conditions
## Terms and Conditions of Sale
1. GENERAL
"""

TERMS_PAGE_WITH_PLAIN_LINES = """
Page 3 of 3
General Terms and Conditions
Terms and Conditions of Sale
1. GENERAL
"""


class TermsPageRecognitionTests(unittest.TestCase):
    def test_recognize_terms_page_with_markdown_titles_as_unknown(self):
        recognition = document_type_recognizer.recognize(TERMS_PAGE_WITH_MARKDOWN_TITLES)
        self.assertEqual(recognition["document_type"], "unknown")
        self.assertEqual(recognition["matched_by"], "strong_rule")
        self.assertIn("terms and conditions", recognition["reasons"][0])

    def test_recognize_terms_page_with_plain_titles_as_unknown(self):
        recognition = document_type_recognizer.recognize(TERMS_PAGE_WITH_PLAIN_LINES)
        self.assertEqual(recognition["document_type"], "unknown")
        self.assertEqual(recognition["matched_by"], "strong_rule")
        self.assertIn("terms and conditions", recognition["reasons"][0])


if __name__ == "__main__":
    unittest.main()

