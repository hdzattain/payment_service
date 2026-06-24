import asyncio
import unittest

from app_module.services.merge_service import MERGE_JSON_STRUCTURES, merge_receipt


class ReceiptMergeTests(unittest.TestCase):
    def test_merge_json_structures_contains_receipt(self):
        self.assertIn("receipt", MERGE_JSON_STRUCTURES)
        self.assertIn('"document_type": "receipt"', MERGE_JSON_STRUCTURES["receipt"])

    def test_merge_receipt_combines_pages(self):
        group_pages = [
            {
                "page_no": 1,
                "structured_data": {
                    "document_type": "receipt",
                    "document_no": "12060",
                    "license_plate": "7F84",
                    "customer_name": "中建（楊小）",
                    "customer_address": "",
                    "project_name": "",
                    "supplier_id": "",
                    "supplier_name": "Great Success Development (Hong Kong) Limited",
                    "supplier_phone": "2892 1522",
                    "supplier_address": "寫字樓：香港灣仔告士打道151號資本中心7樓701室",
                    "product_service": [
                        {
                            "product_service_name": "過磅費",
                            "product_service_specification": "12×200",
                            "product_service_unit": "",
                            "product_service_quantity": 0,
                            "product_service_unit_price": "",
                            "product_service_amount": "200",
                        }
                    ],
                    "currency": "HKD",
                    "total_amount": "1061",
                },
            },
            {
                "page_no": 2,
                "structured_data": {
                    "document_type": "receipt",
                    "document_no": "12060",
                    "license_plate": "",
                    "customer_name": "",
                    "customer_address": "",
                    "project_name": "",
                    "supplier_id": "",
                    "supplier_name": "",
                    "supplier_phone": "",
                    "supplier_address": "倉庫：新界屯門亦園村亦園路",
                    "product_service": [
                        {
                            "product_service_name": "吊機費",
                            "product_service_specification": "Y12",
                            "product_service_unit": "T",
                            "product_service_quantity": 6.15,
                            "product_service_unit_price": "70",
                            "product_service_amount": "431",
                        }
                    ],
                    "currency": "",
                    "total_amount": "",
                },
            },
        ]

        merged = asyncio.run(merge_receipt(group_pages))

        self.assertEqual(merged["document_type"], "receipt")
        self.assertEqual(merged["document_no"], "12060")
        self.assertEqual(merged["license_plate"], "7F84")
        self.assertEqual(merged["customer_name"], "中建（楊小）")
        self.assertEqual(merged["supplier_name"], "Great Success Development (Hong Kong) Limited")
        self.assertEqual(merged["supplier_address"], "寫字樓：香港灣仔告士打道151號資本中心7樓701室")
        self.assertEqual(merged["currency"], "HKD")
        self.assertEqual(merged["total_amount"], "1061.0")
        self.assertEqual(len(merged["product_service"]), 2)


if __name__ == "__main__":
    unittest.main()
