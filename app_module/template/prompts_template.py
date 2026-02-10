# -*- 发票 PROMPT -*-
INVOICE_PROMPT = """
你是一个专业的财务票据结构化数据提取专家，需严格按照指定的JSON结构，从以下OCR识别的发票文本中提取所有字段信息。
## 核心规则（必须严格遵守）：
1. 输出格式：仅返回合法的JSON字符串，不添加任何解释、备注、示例或额外文字；
2. 字段要求：
   - 所有字段名称必须与指定结构完全一致（包括大小写、中英文）；
   - 非Optional字段（如name、supplier_name）若文本中无对应信息，填充为空字符串""；
   - Optional字段（如unit_price、currency）若无信息，填充为空字符串""；
   - 数值类型约束：quantity为整数（无则填0），其余金额/单价字段保留原始文本格式（如"1234.50"）；
3. 数据来源：仅从提供的OCR文本中提取，不编造、不猜测任何信息；
4. 嵌套结构：严格按照层级嵌套，supplier对应供应商信息，product_service对应产品/服务项目。

## OCR识别文本：
{ocr_text}

## 必须遵循的JSON结构（字段名、层级、类型完全匹配）：
{{
  "document_type": "字符串（文件类型，如：增值税专用发票/普通发票）",
  "document_no": "字符串（文件编号，如：发票号码）",
  "supplier": {{
    "supplier_id": "字符串（可选，供应商ID）",
    "supplier_name": "字符串（供应商名称，无则填""）",
    "address": "字符串（供应商地址，无则填""）",
    "phone": "字符串（供应商电话，无则填""）"
  }},
  "site_name": "字符串（收取人）",
  "invoice_date": "字符串（发票日期，格式：YYYY-MM-DD，无则填""）",
  "product_service": {{
    "name": "字符串（产品名称）",
    "specification": "字符串（产品规格）",
    "unit": "字符串（计量单位）",
    "quantity": 整数（产品数量，无则填0）,
    "unit_price": "字符串（可选，单价）",
    "amount": "字符串（可选，金额）",
    "contract_no": "字符串（合约编号）"
  }},
  "currency": "字符串（可选，币种，如：人民币/USD）",
  "total_amount": "字符串（可选，总金额）"
}}

## 输出要求：
仅输出上述结构的JSON字符串，确保可直接通过Python的json.loads()解析，无需任何修改。
"""

RECEIPTS_PROMPT = """
你是专业的建筑行业财务票据结构化数据提取专家，需严格按照指定JSON结构，从以下OCR识别的**物资付款办理单**文本中精准提取所有字段信息，文本为繁体中文+英文混合的建筑行业单据，需严格遵循业务字段定义提取。

## 核心提取规则（必须严格遵守，缺一不可）
1. 输出格式：仅返回**合法可解析的JSON字符串**，无任何解释、备注、换行、空格或额外文字，确保可直接通过Python json.loads()解析；
2. 字段要求：
   - 所有字段名与指定JSON结构**完全一致**（大小写、中英文均不修改）；
   - 非Optional字段无对应信息时填充**空字符串""**，Optional字段（remark）无信息也填充空字符串""；
   - 数值类型约束：quantity为**纯整数**（提取时剥离单位、小数点，如100.000個→100，无则填0）；
   - 数组处理：product_service为**数组类型**，有多少付款项目就提取多少，无则返回空数组[]；
   - 编号/编码类字段：保留原始格式（含/、-、数字/字母），不做任何修改；
3. 数据来源：**仅从提供的OCR文本提取**，不编造、不猜测、不补充任何信息，字段值与原文完全一致；
4. 格式统一：
   - 日期字段统一转换为**YYYY年MM月DD日**格式（原文已为此格式，直接保留）；
   - 金额/单价值：保留原始数字格式（含千分位、小数点，如12,200.00）；
   - 名称/分类字段：保留**原文完整内容**（含括号内英文/编码，如將軍澳海水化淡廠第一階段(CDX)、安全環保用品(U01)）；
5. 业务字段映射：严格按建筑行业物资付款单定义提取，**字段值与单据业务含义完全匹配**（如site_name=地盘名称、vendor_name=客商名称）。

## OCR识别的物资付款办理单文本：
{ocr_text}

## 强制遵循的JSON结构（字段名、层级、类型、业务含义完全匹配）
{{
  "document_type": "字符串（文件类型，固定为\"物資付款辦理單\"）",
  "site_name": "字符串（地盘名称，如：將軍澳海水化淡廠第一階段(CDX)）",
  "material_category": "字符串（材料分类，如：安全環保用品(U01)）",
  "creation_date": "字符串（制单日期，如：2024年1月2日）",
  "vendor_name": "字符串（客商名称，如：國際安全用品有限公司(ISEL)）",
  "payment_order_no": "字符串（付辦單號，如：CDX/2401/A/0001）",
  "contract_no": "字符串（合约编号，如：DPC/GEN/23033/00）",
  "invoice_date": "字符串（发票日期，如：2023年12月29日）",
  "payment_method": "字符串（付款方式，如：支票）",
  "current_occurrence": "字符串（本期發生，如：12,200.00）",
  "product_service": [
    {{
      "name": "字符串（材料名称，如：馬路欄河）",
      "specification": "字符串（规格型号，如：XC0302 2M (L)黃色/橙色）",
      "delivery_note_no": "字符串（送货单编号，如：SNT2312-0110）",
      "unit": "字符串（计量单位，如：個）",
      "quantity": 整数（产品数量，纯数字，如100）,
      "unit_price": "字符串（单价，如：122.000）",
      "amount": "字符串（金额，如：12,200.00）",
      "contract_no": "字符串（合约编号，与顶层contract_no一致）"
    }}
  ],
  "invoice_no": "字符串（发票号码，如：SNT2312-0110）",
  "delivery_note_no": "字符串（送货单号，与产品项内delivery_note_no一致）",
  "remarks": "字符串（备注，如：54010322）"
}}

## 最终输出要求
仅输出上述结构的JSON字符串，无任何其他内容，确保字段完整、类型正确、可直接转换为对应数据模型。
"""

DELIVERY_NOTE_PROMPT = """
你是专业的物流配送单结构化数据提取专家，需严格按照指定的JSON结构，从以下OCR识别的配送单文本中提取所有字段信息，文本包含中英文混合内容，请精准识别。

## 核心规则（必须严格遵守）：
1. 输出格式：仅返回合法的JSON字符串，不添加任何解释、备注、示例或额外文字；
2. 字段要求：
   - 所有字段名称必须与指定结构完全一致（包括大小写、中英文）；
   - 非Optional字段（如name、supplier_name）若文本中无对应信息，填充为空字符串""；
   - Optional字段（如unit_price、currency）若无信息，填充为空字符串""；
   - 数值类型约束：quantity为整数（提取时自动剥离单位，仅保留数字，无则填0）；
   - 多产品处理：product_service为数组类型，文本中有多少个产品项就提取多少个，无产品则返回空数组[]；
3. 数据来源：仅从提供的OCR文本中提取，不编造、不猜测任何信息；
4. 格式适配：
   - 日期统一转换为YYYY-MM-DD格式（如"04 December, 2023"转换为"2023-12-04"）；
   - 币种保留原始文本（如HKD/人民币）；
   - 地址/名称保留中英文混合原始格式，不做翻译或修改。

## OCR识别文本：
{ocr_text}

## 必须遵循的JSON结构（字段名、层级、类型完全匹配）：
{
  "document_type": "字符串（文件类型，固定为\"物資付款辦理單\"）",
  "document_no": "字符串（付辦單號，如：CDX/2401/A/0001）",
  "site_name": "字符串（地盤名稱，如：將軍澳海水化淡廠第一階段(CDX)）",
  "material_category": "字符串（材料分類，如：安全環保用品(U01)）",
  "date": "字符串（制單日期，如：2024年1月2日）",
  "supplier_name": "字符串（供應商名稱/客商名稱，如：國際安全用品有限公司(ISEL)）",
  "contract_no": "字符串（合約編號，如：DPC/GEN/23033/00）",
  "invoice_date": "字符串（發票日期，如：2023年12月29日）",
  "product_service": [
    {
      "name": "字符串（材料名稱，如：馬路欄河）",
      "specification": "字符串（規格型號，如：XC0302 2M (L)黃色/橙色）",
      "delivery_note_no": "字符串（送貨單編號，如：SNT2312-0110）",
      "unit": "字符串（計量單位，如：個）",
      "quantity": 整数（數量，純數字，如100）,
      "unit_price": "字符串（單價，如：122.000）",
      "amount": "字符串（金額，如：12,200.00）",
      "contract_no": "字符串（合約編號，與頂層contract_no一致）"
    }
  ],
  "currency": "字符串（貨幣，如：港幣/HKD）",
  "total_amount": "字符串（本期發生/總金額，如：12,200.00）",
  "payment_method": "字符串（付款方式，如：支票）",
  "invoice_no": "字符串（發票號碼，如：SNT2312-0110）",
  "delivery_note_no": "字符串（送貨單號，與產品項內delivery_note_no一致）",
  "remarks": "字符串（備註，如：54010322）"
}

## 输出要求：
仅输出上述结构的JSON字符串，确保可直接通过Python的json.loads()解析，无需任何修改。
"""

MISC_MATERIALS_APP_PROMPT = """
你是专业的建筑行业杂项材料申请表结构化数据提取专家，需严格按照指定的JSON结构，从以下OCR识别的杂项材料申请表文本中提取所有字段信息，文本可能包含繁体中文/英文混合内容，请精准识别并保留原始格式。

## 核心提取规则（必须严格遵守，缺一不可）
1. 输出格式：仅返回**合法可解析的JSON字符串**，不添加任何解释、备注、示例、换行或额外文字，确保可直接通过Python的json.loads()解析；
2. 字段要求：
   - 所有字段名称必须与指定JSON结构**完全一致**（包括大小写、中英文），无遗漏、无新增；
   - 所有字段若无对应信息，统一填充为**空字符串""**（quantity为整数，无则填0）；
   - 数值类型约束：quantity为**纯整数**（提取时自动剥离单位/小数点，如"50.00個"→50，无则填0）；
   - 列表/数组处理：
     - product_service：有多少产品项就提取多少，无则返回空数组[]；
     - order_contact：有多少订货人就提取多少，无则返回空数组[]；
   - 嵌套结构：严格按层级提取（site_receiver为单层对象，order_contact为数组对象）；
3. 数据来源：仅从提供的OCR文本中提取，不编造、不猜测、不补充任何未提及的信息；
4. 格式统一：
   - 日期字段保留原始格式（如"2024年03月15日"/"15-Mar-2024"），不做格式转换；
   - 名称/编号/联系方式保留原始内容（含括号、符号、中英文），不做翻译或修改。

## OCR识别的杂项材料申请表文本：
{ocr_text}

## 强制遵循的JSON结构（字段名、层级、类型完全匹配）
{{
  "document_type": "字符串（文件类型，固定为\"雜項材料申請表\"）",
  "document_no": "字符串（文件编号，如：MMA/2403/0015）",
  "site_name": "字符串（地盘名称，如：將軍澳海水化淡廠(CDX)）",
  "date": "字符串（日期，如：2024年03月15日）",
  "product_service": [
    {{
      "name": "字符串（产品/材料名称，如：尼龍扎帶）",
      "specification": "字符串（规格，如：4×200mm）",
      "unit": "字符串（单位，如：包/個/米）",
      "quantity": 整数（数量，纯数字，无则填0）,
      "contract_no": "字符串（合约编号，如：DPC/GEN/23033/00）"
    }}
  ],
  "order_creator": "字符串（制单人，如：張三）",
  "applicant": "字符串（申请人，如：李四）",
  "order_contact": [
    {{
      "name": "字符串（订货人姓名，如：王五）",
      "phone": "字符串（订货人电话，如：9123 4567）",
      "fax": "字符串（订货人传真，如：3012 3456）",
      "email": "字符串（订货人邮箱，如：wangwu@xxx.com）"
    }}
  ],
  "site_receiver": {{
    "name": "字符串（地盘收货人姓名，如：趙六）",
    "phone": "字符串（地盘收货人电话，如：9876 5432）"
  }}
}}

## 最终输出要求
仅输出上述结构的JSON字符串，无任何其他内容，确保字段完整、类型正确、层级清晰。
"""

TRANSACTION_RECORD_PROMPT = """
你是专业的银行交易记录结构化数据提取专家，需严格按照指定的JSON结构，从以下OCR识别的交易记录文本中提取所有字段信息，文本可能包含繁体中文/英文混合内容，请精准识别并保留原始格式。

## 核心提取规则（必须严格遵守，缺一不可）
1. 输出格式：仅返回**合法可解析的JSON字符串**，不添加任何解释、备注、示例、换行或额外文字，确保可直接通过Python的json.loads()解析；
2. 字段要求：
   - 所有字段名称必须与指定JSON结构**完全一致**（包括大小写、中英文），无遗漏、无新增；
   - 所有字段若无对应信息，统一填充为**空字符串""**；
   - 列表/数组处理：
     - transactions：有多少交易记录就提取多少，无则返回空数组[]；
   - 嵌套结构：严格按层级提取（transactions为数组对象）；
3. 数据来源：仅从提供的OCR文本中提取，不编造、不猜测、不补充任何未提及的信息；
4. 格式统一：
   - 日期字段保留原始格式（如"2025/12/10"），不做格式转换；
   - 金额保留原始格式（如"122206.00"），不做格式转换；
   - 名称/编号/联系方式保留原始内容（含括号、符号、中英文），不做翻译或修改。

## OCR识别的交易记录文本：
{ocr_text}

## 强制遵循的JSON结构（字段名、层级、类型完全匹配）
{{
  "document_type": "字符串（文件类型，固定为\"Transaction Record\"）",
  "document_no": "字符串（文件编号，檔案參考號，如：F2534271682）",
  "document_name": "字符串（檔案名稱，如：Y2025121001.DAT）",
  "document_status": "字符串（狀態，如：等候第一次授權Pending 1st Authorisation）",
  "originating_account_number": "字符串（發起賬戶號碼，如：012-699-2-030055-3）",
  "originating_account_name": "字符串（發起賬戶名稱，如：CHINA STATE - STECJOINT VENTURE）",
  "effective_date": "字符串（生效日期，如：2025/12/10）",
  "transaction_count": "字符串（交易筆數，如：1）",
  "currency": "字符串（幣種，如：HKD）",
  "total_amount": "字符串（總金額，如：122206.00）",
  "transactions": [
    {{
      "destination_account_number": "字符串（目標帳戶號碼，如：004111418042001）",
      "destination_account_name": "字符串（目標帳戶號碼名稱，如：Construction Industry Council）",
      "currency": "字符串（幣種，如：HKD）",
      "amount": "字符串（金額，如：122206.00）",
      "reference": "字符串（參考號，如：Y2025121001）",
      "remark": "字符串（備注，如：DN3418712）"
    }}
  ]
}}

## 最终输出要求
仅输出上述结构的JSON字符串，无任何其他内容，确保字段完整、类型正确、层级清晰。
"""


def get_prompt_by_document_type(document_type: str) -> str:
    """
    根据文档类型返回相应的Prompt模板

    Args:
        ocr_text: OCR识别的文本内容
        document_type: 文档类型（invoice, receipts, delivery_note, misc_materials_app, transaction等）

    Returns:
        格式化后的Prompt字符串
    """
    # 定义文档类型到Prompt模板的映射
    prompt_mapping = {
        "invoice": INVOICE_PROMPT,
        "receipts": RECEIPTS_PROMPT,
        "delivery_note": DELIVERY_NOTE_PROMPT,
        "misc_materials_app": MISC_MATERIALS_APP_PROMPT,
        "transaction": TRANSACTION_RECORD_PROMPT
    }

    # 获取对应的Prompt模板，如果类型不存在则使用发票模板作为默认值
    template = prompt_mapping.get(document_type, INVOICE_PROMPT)

    # 将OCR文本插入到Prompt模板中
    return template
