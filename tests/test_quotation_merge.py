import asyncio
import unittest

from app_module.services.merge_service import MERGE_JSON_STRUCTURES, merge_quotation


class QuotationMergeTests(unittest.TestCase):
    def test_merge_json_structures_contains_quotation(self):
        self.assertIn("quotation", MERGE_JSON_STRUCTURES)
        self.assertIn('"document_type": "quotation"', MERGE_JSON_STRUCTURES["quotation"])

    def test_merge_quotation_combines_pages(self):
        group_pages = [
            {
                "page_no": 1,
                "structured_data": {
                    "document_type": "quotation",
                    "document_no": "HQ22-0670",
                    "quotation_date": "2022-04-29",
                    "customer_name": "CHINA STATE CONST. ENG'G (H.K.) LTD.",
                    "customer_address": "",
                    "project_name": "Project Alpha",
                    "supplier_id": "",
                    "supplier_name": "HONG KONG TESTING CO., LTD.",
                    "supplier_phone": "2692 2171",
                    "supplier_address": "Fanling, Hong Kong",
                    "product_service": [
                        {
                            "product_service_name": "Calibration Service A",
                            "product_service_specification": "",
                            "product_service_unit": "No.",
                            "product_service_quantity": 1,
                            "product_service_unit_price": "100.00",
                            "product_service_amount": "100.00",
                        }
                    ],
                    "currency": "HKD",
                    "total_amount": "300.00",
                },
            },
            {
                "page_no": 2,
                "structured_data": {
                    "document_type": "quotation",
                    "document_no": "HQ22-0670",
                    "quotation_date": "",
                    "customer_name": "",
                    "customer_address": "29/F, China Overseas Building",
                    "project_name": "",
                    "supplier_id": "",
                    "supplier_name": "",
                    "supplier_phone": "",
                    "supplier_address": "",
                    "product_service": [
                        {
                            "product_service_name": "Calibration Service B",
                            "product_service_specification": "",
                            "product_service_unit": "No.",
                            "product_service_quantity": 2,
                            "product_service_unit_price": "100.00",
                            "product_service_amount": "200.00",
                        }
                    ],
                    "currency": "",
                    "total_amount": "",
                },
            },
        ]

        merged = asyncio.run(merge_quotation(group_pages))

        self.assertEqual(merged["document_type"], "quotation")
        self.assertEqual(merged["document_no"], "HQ22-0670")
        self.assertEqual(merged["quotation_date"], "2022-04-29")
        self.assertEqual(merged["customer_name"], "CHINA STATE CONST. ENG'G (H.K.) LTD.")
        self.assertEqual(merged["customer_address"], "29/F, China Overseas Building")
        self.assertEqual(merged["project_name"], "Project Alpha")
        self.assertEqual(merged["supplier_name"], "HONG KONG TESTING CO., LTD.")
        self.assertEqual(merged["currency"], "HKD")
        self.assertEqual(merged["total_amount"], "300.0")
        self.assertEqual(len(merged["product_service"]), 2)


if __name__ == "__main__":
    unittest.main()

