import unittest
from unittest.mock import patch

from app_module.services.document_type_recognizer import document_type_recognizer
from app_module.services.ocr_task_service import extract_receipt_data, extract_structured_data_from_ocr
from app_module.template.prompts_template import get_prompt_by_document_type


RECEIPT_TEXT_1 = """
盈信發展(香港)有限公司
Great Success Development (Hong Kong) Limited
寫字樓：香港灣仔告士打道151號資本中心7樓701室
電話：2892 1522　傳真：2833 5676
倉庫：新界屯門亦園村亦園路　電話：2472 0880　傳真：2472 0922

收據
No. 12060
客戶：中建（楊小）
日期：24/12/14
提單號碼：52611
車牌：7F84
貨品：螺紋鋼及鋼材

<table>
  <tr>
    <th>過磅費</th>
    <th colspan="4">吊機費</th>
  </tr>
  <tr>
    <th>花式</th>
    <th>金額</th>
    <th>花式及淨重</th>
    <th>單價</th>
    <th>金額</th>
  </tr>
  <tr>
    <td>12×200</td>
    <td>200</td>
    <td>Y12 6.15T</td>
    <td>$70</td>
    <td>431</td>
  </tr>
  <tr>
    <td></td>
    <td></td>
    <td>Y16 6.14T</td>
    <td>$70</td>
    <td>430</td>
  </tr>
  <tr>
    <td>總金額：</td>
    <td></td>
    <td></td>
    <td></td>
    <td>1061</td>
  </tr>
</table>

經手人：
"""


RECEIPT_TEXT_2 = """
盈信發展(香港)有限公司
Great Success Development (Hong Kong) Limited
寫字樓：香港灣仔告士打道151號資本中心7樓701室
電話：2892 1522　傳真：2833 5676
倉庫：新界屯門亦園村亦園路　電話：2472 0880　傳真：2472 0922

收據　No. 11127
客戶：中建　日期：31/5/22
提單號碼：F1399　車牌：

貨品：螺紋鋼及鋼材

<table>
  <tr>
    <th>過磅費</th>
    <th>吊機費</th>
  </tr>
  <tr>
    <th>花式</th>
    <th>金額</th>
    <th>花式及淨重</th>
    <th>單價</th>
    <th>金額</th>
  </tr>
  <tr>
    <td></td>
    <td>Y20</td>
    <td>30.184斤</td>
    <td>470</td>
    <td>2119</td>
  </tr>
  <tr>
    <td></td>
    <td></td>
    <td></td>
    <td></td>
    <td>2119</td>
  </tr>
</table>

管理費：

代客過磅費：

總金額：2119

經手人：
"""


class ReceiptSupportTests(unittest.TestCase):
    def test_recognize_receipt_by_no_and_business_fields(self):
        recognition = document_type_recognizer.recognize(RECEIPT_TEXT_1)
        self.assertEqual(recognition["document_type"], "receipt")

    def test_do_not_recognize_receipt_when_only_business_signals_exist_without_receipt_keyword(self):
        recognition = document_type_recognizer.recognize(
            "交客簽收單\n"
            "No. C2212049\n"
            "客戶：中國建築工程(香港)有限公司\n"
            "日期：23/12/2022\n"
            "工程名稱：海水化淡廠CDX\n"
        )
        self.assertNotEqual(recognition["document_type"], "receipt")
        self.assertEqual(recognition["document_type"], "unknown")

    def test_prompt_mapping_returns_receipt_prompt(self):
        prompt = get_prompt_by_document_type("receipt")
        self.assertIn('"document_type": "receipt"', prompt)
        self.assertIn('不要误提取 `提單號碼` 作为 `document_no`', prompt)
        self.assertIn('No. 12060', prompt)
        self.assertIn('"product_service_name": "吊機費"', prompt)
        self.assertIn('{ocr_text}', prompt)

    @patch("app_module.services.ocr_task_service.merge_structured_data_with_llm")
    def test_extract_receipt_data_seeds_header_fields_from_rules(self, mock_merge):
        mock_merge.side_effect = lambda regex_data, *_args, **_kwargs: (dict(regex_data), None)

        result = extract_receipt_data(RECEIPT_TEXT_1)
        structured = result["structured_data"]

        self.assertEqual(result["document_type"], "receipt")
        self.assertEqual(structured["document_no"], "12060")
        self.assertEqual(structured["license_plate"], "7F84")
        self.assertEqual(structured["customer_name"], "中建（楊小）")
        self.assertEqual(structured["supplier_name"], "Great Success Development (Hong Kong) Limited")
        self.assertEqual(structured["supplier_phone"], "2892 1522")
        self.assertEqual(structured["supplier_address"], "寫字樓：香港灣仔告士打道151號資本中心7樓701室")
        self.assertEqual(structured["currency"], "$")
        self.assertEqual(structured["total_amount"], "1061")
        self.assertEqual(structured["product_service"], [])

    @patch("app_module.services.ocr_task_service.merge_structured_data_with_llm")
    def test_extract_receipt_data_keeps_hard_product_rows_for_llm(self, mock_merge):
        mock_merge.side_effect = lambda regex_data, *_args, **_kwargs: (dict(regex_data), None)

        result = extract_receipt_data(RECEIPT_TEXT_2)
        structured = result["structured_data"]

        self.assertEqual(structured["document_no"], "11127")
        self.assertEqual(structured["customer_name"], "中建")
        self.assertEqual(structured["supplier_name"], "Great Success Development (Hong Kong) Limited")
        self.assertEqual(structured["supplier_phone"], "2892 1522")
        self.assertEqual(structured["total_amount"], "2119")
        self.assertEqual(structured["currency"], "")
        self.assertEqual(structured["product_service"], [])

    @patch("app_module.services.ocr_task_service.merge_structured_data_with_llm")
    def test_extract_structured_data_from_ocr_routes_to_receipt(self, mock_merge):
        mock_merge.side_effect = lambda regex_data, *_args, **_kwargs: (dict(regex_data), None)

        result = extract_structured_data_from_ocr(RECEIPT_TEXT_1)

        self.assertEqual(result["document_type"], "receipt")
        self.assertEqual(result["structured_data"]["document_no"], "12060")
        self.assertEqual(result["structured_data"]["currency"], "$")


if __name__ == "__main__":
    unittest.main()






