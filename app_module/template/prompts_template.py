# -*- 发票 PROMPT -*-
INVOICE_PROMPT = """
你是一个专业的财务票据结构化数据提取专家，需严格按照指定的JSON结构，从以下OCR识别的发票文本中提取所有字段信息。
## 核心规则（必须严格遵守）：
1. 输出格式：仅返回合法的JSON字符串，不添加任何解释、备注、示例或额外文字；
2. 字段要求：
   - 所有字段名称必须与指定结构完全一致（包括大小写、中英文）；
   - 非Optional字段（如product_service_name、supplier_name）若文本中无对应信息，填充为空字符串""；
   - Optional字段（如product_service_unit_price、currency）若无信息，填充为空字符串""；
   - 数值类型约束：product_service_quantity 保留数字格式（无则留空）；
   - 日期字段统一转换为**yyyy-MM-dd**格式；
   - 时间字段统一转换为**yyyy-MM-dd HH:mm:ss**格式；
   - 金额/单价值：保留数字格式（含小数点，如12200.00）；
3. 数据来源：仅从提供的OCR文本中提取，不编造、不猜测任何信息；
4. 嵌套结构：严格按照层级嵌套，product_service对应产品/服务项目；supplier_id、supplier_name、supplier_address、supplier_phone为顶层字段。
5. 币种归一化规则：
   - 识别到「港币、HKD、HK.Dollars、港币/HKD」等表示港币的文本，统一归一化为 "HKD"
   - 识别到「美元、USD、US Dollars、美金」等表示美元的文本，统一归一化为 "USA"
   - 识别到「人民币、CNY、RMB」等表示人民币的文本，统一归一化为 "CNY"
   - 识别到「澳币、MOP」等表示澳币的文本，统一归一化为 "MOP"
   - 不在上述范围内的币种，按原文提取

## 示例案例（帮助理解任务）
### 案例 1：
#### 输入：
# 永新五金工程有限公司
WING SUN METAL & ENGINEERING CO., LTD
九龍旺角豉油街10號B地下
10B, SOY STREET, G/F., SUN MAN LEE BLDG., MONGKOK, KOWLOON.
TEL: (852) 2396 7088(5線)　FAX: (852) 2396 7512
工程部: 廣東省東莞厚街鎮下汴工業管理區　電話: 8559 1345
E-mail: wsmetal8@netvigator.com

**MESSRS.** 中國建築工程(香港)有限公司(海水化淡廠)

| 項目 | 內容 |
|---|---|
| 客戶代號 | 中國CDX |
| 參考編號 | DPC/GEN/23003 |
| INVOICE NO. | 23/005012 |
| PAGE | 3 / 3 |
| Date | 2023/12/04 |

## 發 INVOICE 票

| 貨名 / DESCRIPTION | 數量 / QUANTITY | 單價 / UNIT PRICE | 金額 / AMOUNT |
|---|---:|---:|---:|
| 025 菊花牌膠手套(中碼) 黃色 | 4對 | 26.0000 | 104.00 |
| 026 36" X 48" 黑色垃圾袋100個/包 厚身 | 3包 | 250.0000 | 750.00 |
| 027 水鞋(38碼) | 1對 | 68.0000 | 68.00 |
| 028 透明即棄膠手套(100只/盒)(白色M碼) | 11盒 | 100.0000 | 1,100.00 |
| 029 大垃圾桶連蓋16" X 17" X 24" (45L) 脚踏灰色 | 4個 | 180.0000 | 720.00 |

**CDX-3383**
將軍澳海水化淡廠 137 堆填區, 翠谷　卓生 9138 2007 / 林生 9215 3007 / 謝生 5962 9254

**TOTAL** HKD 18,891.00

#### 输出：
{{
    "document_type": "invoice",
    "product_service": [
        {{
            "product_service_name": "025 菊花牌膠手套(中碼) 黃色",
            "product_service_unit_price": "26.0000",
            "product_service_unit": "對",
            "product_service_quantity": "4",
            "product_service_amount": "104.00"
        }},
        {{
            "product_service_name": "026 36\" X 48\" 黑色垃圾袋100個/包 厚身",
            "product_service_unit_price": "250.0000",
            "product_service_unit": "包",
            "product_service_quantity": "3",
            "product_service_amount": "750.00"
        }},
        {{
            "product_service_name": "027 水鞋(38碼)",
            "product_service_unit_price": "68.0000",
            "product_service_quantity": "1",
            "product_service_amount": "68.00"
        }},
        {{
            "product_service_name": "028 透明即棄膠手套(100只/盒)(白色M碼)",
            "product_service_unit_price": "100.0000",
            "product_service_unit": "盒",   
            "product_service_quantity": "11",
            "product_service_amount": "1100.00"
        }},
        {{
            "product_service_name": "029 大垃圾桶連蓋16\" X 17\" X 24\" (45L) 腳踏灰色",
            "product_service_unit_price": "180.0000",
            "product_service_unit": "個",
            "product_service_quantity": "4",
            "product_service_amount": "720.00"
        }}
    ],
    "order_contact": [],
    "currency": "HKD",
    "total_amount": "18891.00",
    "document_no": "23/005012",
    "invoice_date": "2023-12-04",
    "supplier_id": "",
    "supplier_name": "永新五金工程有限公司",
    "supplier_address": "九龍旺角豉油街10號B地下",
    "supplier_phone": "(852) 2396 7088(5線)",
    "site_name": "中國建築工程(香港)有限公司(海水化淡廠)"
}}

### 案例 2：
#### 输入：
# 海興材料有限公司 Hoi Hing Building Materials Co. Limited

Hoi Hing Building Materials

新界葵涌貨櫃碼頭路71-75號鐘意恆勝中心3樓306室  
Rm 306, 3F, Join-In Hang Sing Centre,  
71-75 Container Port Road, Kwai Chung, NT, HK  
Tel: 2536 2900 | 2388 0263  Fax: 2770 4137

ISO 9001 : 2015  
Certificate No.: CC 1993

# 發票 INVOICE

## To

- TO：中國建築工程(香港)有限公司
- 項目：CDX 將軍澳海水化淡廠第一期 - 安全鞋
- ATTN：卓先生
- TEL NO.：9138 2007
- SITE CODE：

## 發票資料

- QTN NO.：
- SO No.：
- Cust PR.：CDX3776
- Cust PO.：
- Contract No.：DPC/GEN/24023/00
- 發票編號 Inv No.：HH24-023292
- 日期 Date：31-08-2024
- 銷售員 Sales：Alin Xu
- 客戶編碼 Cust No.：800008-00041-06
- 頁數 Pages：1/1

## 明細

| No. | Item Code | 產品明細 Description | D.N. No. | Quantity | Unit Price | Amount |
|---:|---|---|---|---:|---:|---:|
| 1 | MD0226 | ^ 石星KC-9920 安全鞋 #39<br>-馮靜雯 | HD24-045113 | 1對 | 350.00 | 350.00 |
| 2 | MD0226 | ^ 石星KC-9920 安全鞋 #41<br>-工程辛嘉彤 |  | 1對 | 350.00 | 350.00 |
| 3 | MD0226 | ^ 石星KC-9920 安全鞋 #44<br>-梁倚惠<br>CDX3776 |  | 1對 | 350.00 | 350.00 |

**TOTAL  HK$1,050.00**

## 收件章 / 簽收

- 收發票日期：10 SEP 2024
- By: __________

（頁面下方有藍色收章，內容部分模糊）

## 頁腳

- Confirmation and received by
- For and on Behalf of
- Authorised Signature & Co. Chop
- QR#11-2
- E.&O.E
- Authorised Signature

#### 输出：
{{
    "document_type": "invoice",
    "product_service": [
        {{
            "product_service_name": "^ 石星KC-9920 安全鞋 #39 -馮靜雯",
            "product_service_quantity": "1",
            "product_service_unit": "對",
            "product_service_unit_price": "350.00",
            "product_service_amount": "350.00"
        }},
        {{
            "product_service_name": "^ 石星KC-9920 安全鞋 #41 -工程辛嘉彤",
            "product_service_quantity": "1",
            "product_service_unit": "對",
            "product_service_unit_price": "350.00",
            "product_service_amount": "350.00"
        }},
        {{
            "product_service_name": "^ 石星KC-9920 安全鞋 #44 -梁倚惠 CDX3776",
            "product_service_quantity": "1",
            "product_service_unit": "對",
            "product_service_unit_price": "350.00",
            "product_service_amount": "350.00"
        }}
    ],
    "order_contact": [],
    "document_no": "HH24-023292",
    "invoice_date": "2024-08-31",
    "site_name": "中國建築工程(香港)有限公司 CDX 將軍澳海水化淡廠第一期 - 安全鞋",
    "currency": "HKD",                               
    "total_amount": "1050.00",
    "supplier_id": "",
    "supplier_name": "海興材料有限公司 Hoi Hing Building Materials Co. Limited",
    "supplier_address": "新界葵涌貨櫃碼頭路71-75號鐘意恆勝中心3樓306室",
    "supplier_phone": "2536 2900 | 2388 0263"
}}

### 案例 3：
#### 输入：
# **starcard**
# CALTEX

# 交易概要 Transaction Summary

**發票編號 Document No** 0054532622
**頁數 Page** 3/12
**結算期 Billing Period** 01/07/2024 - 31/07/2024
**賬戶編號 Account No** 0700030073

| 內容 Description | 產品 Product | 數量 Quantity | 金額 Amount HKD |
| :--- | :--- | :--- | :--- |
| 789655******6652 | Gold w Techron | 402.38 | 6,512.74 |
| | | 402.38 | 6,512.74 |
| 789655******6660 | Gold w Techron | 88.23 | 1,430.33 |
| | | 88.23 | 1,430.33 |
| 789655******7512 | Gold w Techron | 153.82 | 2,493.20 |
| | Lubricants | 1.00 | 50.40 |
| | | 153.82 | 2,543.60 |
| 789655******8612 | Diesel w Techron D | 55.97 | 473.99 |
| | | 55.97 | 473.99 |
| 789655******8620 | Diesel w Techron D | 129.75 | 1,099.05 |
| | | 129.75 | 1,099.05 |
| 789655******9460 | Gold w Techron | 280.18 | 4,533.17 |
| | | 280.18 | 4,533.17 |

- 查詢熱線 Enquiry Hotline: 2582 6288;失咭熱線 Lost Card Hotline: 2582 6270.
- 電郵地址 E-mail Address: starcard-hk@chevron.com

#### 输出：
{{
    "document_type": "invoice",
    "product_service": [
        {{
            "product_service_name": "Gold w Techron",
            "product_service_specification": "",
            "product_service_unit": "",
            "product_service_quantity": "402.38",
            "product_service_unit_price": "",
            "product_service_amount": "6512.74",
            "product_service_contract_no": ""
        }},
        {{
            "product_service_name": "Gold w Techron",
            "product_service_specification": "",
            "product_service_unit": "",
            "product_service_quantity": "88.23",
            "product_service_unit_price": "",
            "product_service_amount": "1430.33",
            "product_service_contract_no": ""
        }},
        {{
            "product_service_name": "Gold w Techron",
            "product_service_specification": "",
            "product_service_unit": "",
            "product_service_quantity": "153.82",
            "product_service_unit_price": "",
            "product_service_amount": "2493.20",
            "product_service_contract_no": ""
        }},
        {{
            "product_service_name": "Lubricants",
            "product_service_specification": "",
            "product_service_unit": "",
            "product_service_quantity": "1.00",
            "product_service_unit_price": "",
            "product_service_amount": "50.40",
            "product_service_contract_no": ""
        }},
        {{
            "product_service_name": "Diesel w Techron D",
            "product_service_specification": "",
            "product_service_unit": "",
            "product_service_quantity": "55.97",
            "product_service_unit_price": "",
            "product_service_amount": "473.99",
            "product_service_contract_no": ""
        }},
        {{
            "product_service_name": "Diesel w Techron D",
            "product_service_specification": "",
            "product_service_unit": "",
            "product_service_quantity": "129.75",
            "product_service_unit_price": "",
            "product_service_amount": "1099.05",
            "product_service_contract_no": ""
        }},
        {{
            "product_service_name": "Gold w Techron",
            "product_service_specification": "",
            "product_service_unit": "",
            "product_service_quantity": "280.18",
            "product_service_unit_price": "",
            "product_service_amount": "4533.17",
            "product_service_contract_no": ""
        }}
    ],
    "order_contact": [],
    "document_no": "0054532622",
    "invoice_date": "",
    "site_name": "",
    "currency": "HKD",                               
    "total_amount": "",
    "supplier_id": "",
    "supplier_name": "",
    "supplier_address": "",
    "supplier_phone": ""
}}


## OCR识别文本：
{ocr_text}

## 必须遵循的JSON结构（字段名、层级、类型完全匹配）：
{{
  "document_type": "字符串（文件类型，固定为\"invoice\"）",
  "document_no": "字符串（文件编号，如：发票号码）",
  "supplier_id": "字符串（可选，供应商ID）",
  "supplier_name": "字符串（供应商名称，无则填""）",
  "supplier_address": "字符串（供应商地址，无则填""）",
  "supplier_phone": "字符串（供应商电话，无则填""）",
  "site_name": "字符串（收取人）",
  "invoice_date": "字符串（发票日期，格式：YYYY-MM-DD，无则填""）",
  "product_service": {{
    "product_service_name": "字符串（产品名称）",
    "product_service_specification": "字符串（产品规格）",
    "product_service_unit": "字符串（计量单位）",
    "product_service_quantity": 數字格式（产品数量，无则填0）,
    "product_service_unit_price": "字符串（可选，单价）",
    "product_service_amount": "字符串（可选，金额）",
    "product_service_contract_no": "字符串（合约编号）"
  }},
  "currency": "字符串（可选，币种，归一化为：HKD/USA/CNY/MOP，其他按原文，无则填""）",
  "total_amount": "字符串（可选，总金额）"
}}

## 输出要求：
仅输出上述结构的JSON字符串，确保可直接通过Python的json.loads()解析，无需任何修改。
"""

PAYMENT_REQUEST_FORM_PROMPT = """
你是专业的建筑行业财务票据结构化数据提取专家，需严格按照指定JSON结构，从以下OCR识别的**物资付款办理单**文本中精准提取所有字段信息，文本为繁体中文+英文混合的建筑行业单据，需严格遵循业务字段定义提取。

## 核心提取规则（必须严格遵守，缺一不可）
1. 输出格式：仅返回**合法可解析的JSON字符串**，无任何解释、备注、换行、空格或额外文字，确保可直接通过Python json.loads()解析；
2. 字段要求：
   - 所有字段名与指定JSON结构**完全一致**（大小写、中英文均不修改）；
   - 非Optional字段无对应信息时填充**空字符串""**，Optional字段（remark）无信息也填充空字符串""；
   - 数值类型约束：quantity 保留数字格式（提取时剥离单位，如100.000個→100.000，无则填0）；；
   - 数组处理：product_service为数组类型，提取【摘要】与【費用類型】两个表格的行项目；忽略金额为0或空、且名称/描述也为空的占位空行，仅提取有实际业务发生的有效行，无则返回空数组[]；
   - 编号/编码类字段：保留原始格式（含/、-、数字/字母），不做任何修改；
3. 数据来源：**仅从提供的OCR文本提取**，不编造、不猜测、不补充任何信息，字段值与原文完全一致；
4. 格式统一：
   - 日期字段统一转换为**yyyy-MM-dd**格式；
   - 时间字段统一转换为**yyyy-MM-dd HH:mm:ss**格式；
   - 金额/单价值：保留数字格式（含小数点，如12200.00）；
   - 名称/分类字段：保留**原文完整内容**（含括号内英文/编码，如將軍澳海水化淡廠第一階段(CDX)、安全環保用品(U01)）；
5. 业务字段映射：严格按建筑行业物资付款单定义提取，**字段值与单据业务含义完全匹配**（如site_name=地盘名称、vendor_name=客商名称）。
6. 币种归一化规则：
   - 识别到「港币、HKD、HK.Dollars、港币/HKD」等表示港币的文本，统一归一化为 "HKD"
   - 识别到「美元、USD、US Dollars、美金」等表示美元的文本，统一归一化为 "USA"
   - 识别到「人民币、CNY、RMB」等表示人民币的文本，统一归一化为 "CNY"
   - 识别到「澳币、MOP」等表示澳币的文本，统一归一化为 "MOP"
   - 不在上述范围内的币种，按原文提取

## 示例案例（帮助理解任务）
### 案例 1：
#### 输入：
# 中國建築工程(香港)有限公司

## 物資付款辦理單

| 欄位 | 內容 |
|---|---|
| 地盤名稱 | 將軍澳海水化淡廠第一階段(CDX) |
| 材料分類 | 小五金材料(M20) |
| 制單日期 | 2023年12月6日 |
| 客商名稱 | 永新五金工程有限公司(WGS) |
| 扣保固金比例 | 0.00% |
| 付辦單號 | CDX/2312/A/0015 |
| 合約編號 | DPC/GEN/23003/00 |
| 發票日期 | 2023年12月4日 |
| 收發票日期 | 2023年12月6日 |
| 幣種 | 港元 |
| 是否代購 | 否 |
| 付款方式 | 支票 |
| 附單數 | 4 |

### 合約金額彙總

| 項目 | 合約總額 | 上期累計 | 本期發生 | 本期累計 | 超合約額比例 |
|---|---:|---:|---:|---:|---:|
| DPC/GEN/23003總計 | 0.00 | 393,601.38 | 19,216.00 | 412,817.38 |  |
| 材料款 | 0.00 | 393,601.38 | 19,216.00 | 412,817.38 | - |
| 費用 | 0.00 | 0.00 | 0.00 | 0.00 | - |
| 預付款 | - | 0.00 | 0.00 | 0.00 | - |
| 保固金 | - | 0.00 | 0.00 | 0.00 | - |
| DPC/GEN/23003/0合計 | 0.00 | 393,601.38 | 19,216.00 | 412,817.38 | - |

### 摘要

| 材料名稱 | 規格型號 | 數量 | 單價 | 金額 |
|---|---|---:|---:|---:|
| 鐵咀大介刀(PJ3123) |  | 12.000把 | 6.000 | 72.00 |
| 普通電池(PL7004) | AA，勁量牌，4粒/排 | 10.000排 | 12.650 | 126.50 |
| 普通電池(PL7005) | AAA，勁量牌，4粒/排 | 10.000排 | 12.650 | 126.50 |
| 工具,小五金,零星電器(PR0100) | 大垃圾桶連蓋16\"X17\"X24\"(45L)腳踏灰色 | 4.000個 | 180.000 | 720.00 |
| 工具,小五金,零星電器(PR0100) | 藥水膠布100片/盒 | 2.000盒 | 18.000 | 36.00 |

### 費用類型

| 費用類型 | 描述 | 數量 | 單價 | 金額 |
|---|---|---:|---:|---:|
|  |  | 0.000 | 0.000 | 0.00 |

### 發票號碼 / 送貨單號

| 項目 | 內容 |
|---|---|
| 發票號碼 | 23/005008, 23/005012 |
| 送貨單號 | D23/005008, D23/005012 |

### 備註

| 項目 | 內容 |
|---|---|
| 備註 | 54010102 |

### 簽核欄

- 地盤製表/複核：______________
- 財務部簽收：______________
- 物資部簽收：______________
- 地盤經理：______________
- 總經理：______________
- 董事長：______________
- 物資部：______________
- 分管領導：______________
- 財務部：______________

Print Date: 2023-12-06 13:55

#### 输出：
{{
    "document_type": "payment_request_form",
    "product_service": [
        {{
            "product_service_name": "鐵咀大介刀(PJ3123)",
            "product_service_specification": "",
            "product_service_unit": "把",
            "product_service_quantity": "12.000",
            "product_service_unit_price": "6.000",
            "product_service_amount": "72.00"
        }},
        {{
            "product_service_name": "普通電池(PL7004)",
            "product_service_specification": "AA，勁量牌，4粒/排",
            "product_service_unit": "排",
            "product_service_quantity": "10.000",
            "product_service_unit_price": "12.650",
            "product_service_amount": "126.50"
        }},
        {{
            "product_service_name": "普通電池(PL7005)",
            "product_service_specification": "AAA，勁量牌，4粒/排",
            "product_service_unit": "排",
            "product_service_quantity": "10.000",
            "product_service_unit_price": "12.650",
            "product_service_amount": "126.50"
        }},
        {{
            "product_service_name": "工具,小五金,零星電器(PR0100)",
            "product_service_specification": "大垃圾桶連蓋16\"X17\"X24\"(45L)腳踏灰色",
            "product_service_unit": "個",
            "product_service_quantity": "4.000",
            "product_service_unit_price": "180.000",
            "product_service_amount": "720.00"
        }},
        {{
            "product_service_name": "工具,小五金,零星電器(PR0100)",
            "product_service_specification": "藥水膠布100片/盒",
            "product_service_unit": "個",
            "product_service_quantity": "2.000",
            "product_service_unit_price": "18.000",
            "product_service_amount": "36.00"
        }}
    ],
    "site_name": "將軍澳海水化淡廠第一階段(CDX)",
    "material_category": "小五金材料(M20)",
    "date": "2023-12-06",
    "supplier_name": "永新五金工程有限公司(WGS)",
    "document_no": "CDX/2312/A/0015",
    "contract_no": "DPC/GEN/23003/00",
    "invoice_date": "2023-12-04",
    "payment_method": "支票",
    "total_amount": "19216.00",
    "currency": "HKD",
    "delivery_note_no": "",
    "invoice_no": "23/005008，23/005012",
    "remarks": "54010102"
}}


## OCR识别的物资付款办理单文本：
{ocr_text}

## 强制遵循的JSON结构（字段名、层级、类型完全匹配）
{{
  "document_type": "字符串（文件类型，固定为\"payment_request_form\"）",
  "site_name": "字符串（地盘名称，如未出现则填\"\"）",
  "material_category": "字符串（材料分类，如未出现则填\"\"）",
  "date": "字符串（制单日期，如未出现则填\"\"）",
  "supplier_name": "字符串（供应商名称、客商名称，如未出现则填\"\"）",
  "document_no": "字符串（付辦單號，如：CDX/2401/A/0001）",
  "contract_no": "字符串（合约编号，如未出现则填\"\"）",
  "invoice_date": "字符串（发票日期，如未出现则填\"\"）",
  "payment_method": "字符串（付款方式，如未出现则填\"\"）",
  "total_amount": "字符串（合计金额，如：29900.00）",
  "currency": "字符串（可选，币种，归一化为：HKD/USA/CNY/MOP，其他按原文，无则填""）",
  "product_service": [
    {{
	  "product_service_name": "字符串（摘要表取【材料名稱】列，费用类型表取【費用類型】列）",
      "product_service_specification": "字符串（摘要表取【規格型號】列，费用类型表取【描述】列）",
      "product_service_delivery_note_no": "字符串（送货单编号，如：SNT2312-0110）",
      "product_service_unit": "字符串（计量单位，如：個、項、次）",
      "product_service_quantity": 數字格式（产品数量，如100、10.12）,
      "product_service_unit_price": "字符串（单价，如：122.000、160.000）",
      "product_service_amount": "字符串（金额，如：12200.00、1600.00）"
    }}
  ],
  "invoice_no": "字符串（发票号码，如未出现则填\"\"）",
  "delivery_note_no": "字符串（送货单号，如未出现则填\"\"）",
  "remarks": "字符串（备注，如未出现则填\"\"）"
}}

## 最终输出要求
仅输出上述结构的JSON字符串，无任何其他内容，确保字段完整、类型正确、可直接转换为对应数据模型。
"""

PAYMENT_REQUEST_FORM_DETAIL_PROMPT = """
你是专业的建筑行业财务票据结构化数据提取专家，需严格按照指定JSON结构，从以下OCR识别的**材料付办单附表－摘要明細**文本中精准提取所有字段信息。

## 核心提取规则（必须严格遵守）
1. 输出格式：仅返回合法可解析的JSON字符串，不添加任何解释、备注、换行或额外文字；
2. 字段要求：
   - 字段结构与 `payment_request_form` 类型完全一致，但 `document_type` 固定输出为 `payment_request_form_detail`；
   - 文本中未出现的字段统一填充为空字符串 `""`，数组无数据则返回 `[]`；
   - `product_service` 为数组，有多少条费用/材料明细就提取多少条；
   - **禁止漏项**：表格中每一行费用/材料明细都必须输出为一条 `product_service` 记录，不能只提取前几条；
   - 数量保留数字格式，需剥离单位，如 `10.00項 -> 10.00`、`1.00次 -> 1.00`；
   - 金额/单价保留数字格式，不保留千分位逗号；
3. 数据来源：仅从OCR文本提取，不编造、不猜测；
4. 字段理解要求：
   - `document_no` 优先提取标题下方单号，如 `CDX/2306/A/0008`；
   - 若表头为“材料名稱 / 規格型號 / 數量 / 單價 / 金額”，则 `product_service_name -> 材料名稱`，`product_service_specification -> 規格型號`；
   - 若表头为“費用類型 / 描述 / 數量 / 單價 / 金額”，则 `product_service_name -> 費用類型`，`product_service_specification -> 描述`；
   - 费用表场景下，**不得**把“描述”错误填入 `product_service_name`；
   - `product_service_unit` 从数量中的单位提取，如 `項`、`次`；
   - `total_amount` 提取“合计”；
   - 若文本中同时存在表格明细与“合计”，`total_amount` 应与全部 `product_service_amount` 汇总一致，不得因漏项导致不一致；
   - 其他如 `site_name`、`supplier_name`、`invoice_no`、`delivery_note_no` 等若未出现则留空；
5. 币种归一化规则：
   - 识别到「港币、HKD、HK.Dollars、港币/HKD」等表示港币的文本，统一归一化为 `HKD`
   - 识别到「美元、USD、US Dollars、美金」等表示美元的文本，统一归一化为 `USA`
   - 识别到「人民币、CNY、RMB」等表示人民币的文本，统一归一化为 `CNY`
   - 识别到「澳币、MOP」等表示澳币的文本，统一归一化为 `MOP`
   - 未出现币种时填空字符串

## 示例案例
### 输入：
# 材料付办单附表－摘要明細

# CDX/2306/A/0008

**费用：**

| 費用類型 | 描述 | 數量 | 單價 | 金額 |
| :--- | :--- | :--- | :--- | :--- |
| 服務費用 | Calibration of 100mm cube mould | 10.00項 | 160.000 | 1,600.00 |
| 服務費用 | Calibration of 100mm cube mould with HOKLAS certificate | 40.00項 | 160.000 | 6,400.00 |
| 服務費用 | Calibration of compacting bar | 1.00項 | 150.000 | 150.00 |
| 服務費用 | Calibration of compacting bar with HOKLAS certificate | 1.00項 | 150.000 | 150.00 |
| 服務費用 | Calibration of slump cone | 1.00項 | 450.000 | 450.00 |
| 服務費用 | Calibration of slump cone set with HOKLAS certificate | 1.00項 | 450.000 | 450.00 |
| 服務費用 | Calibration of steel ruler | 1.00項 | 420.000 | 420.00 |
| 服務費用 | Calibration of temperature | 1.00項 | 630.000 | 630.00 |
| 服務費用 | Temperature distribution & circulation of curing tank | 4.00項 | 1,800.000 | 7,200.00 |
| 服務費用 | Provision and calibration of thermometer | 5.00項 | 850.000 | 4,250.00 |
| 服務費用 | Sample collection /return fee | 1.00次 | 500.000 | 500.00 |
| 服務費用 | Sample collection fee | 1.00次 | 500.000 | 500.00 |
| 服務費用 | Temperature Distribution & circulation of Curing Tank | 4.00項 | 1,800.000 | 7,200.00 |

- 合计：29,900.00

- Print Date: 2023-06-02 10:25
- Page: 3

### 输出：
{{
  "document_type": "payment_request_form_detail",
  "site_name": "",
  "material_category": "",
  "date": "",
  "supplier_name": "",
  "document_no": "CDX/2306/A/0008",
  "contract_no": "",
  "invoice_date": "",
  "payment_method": "",
  "total_amount": "29900.00",
  "currency": "",
  "product_service": [
    {{
      "product_service_name": "服務費用",
      "product_service_specification": "Calibration of 100mm cube mould",
      "product_service_delivery_note_no": "",
      "product_service_unit": "項",
      "product_service_quantity": "10.00",
      "product_service_unit_price": "160.000",
      "product_service_amount": "1600.00"
    }},
    {{
      "product_service_name": "服務費用",
      "product_service_specification": "Calibration of 100mm cube mould with HOKLAS certificate",
      "product_service_delivery_note_no": "",
      "product_service_unit": "項",
      "product_service_quantity": "40.00",
      "product_service_unit_price": "160.000",
      "product_service_amount": "6400.00"
    }},
    {{
      "product_service_name": "服務費用",
      "product_service_specification": "Calibration of compacting bar",
      "product_service_delivery_note_no": "",
      "product_service_unit": "項",
      "product_service_quantity": "1.00",
      "product_service_unit_price": "150.000",
      "product_service_amount": "150.00"
    }},
    {{
      "product_service_name": "服務費用",
      "product_service_specification": "Calibration of compacting bar with HOKLAS certificate",
      "product_service_delivery_note_no": "",
      "product_service_unit": "項",
      "product_service_quantity": "1.00",
      "product_service_unit_price": "150.000",
      "product_service_amount": "150.00"
    }},
    {{
      "product_service_name": "服務費用",
      "product_service_specification": "Calibration of slump cone",
      "product_service_delivery_note_no": "",
      "product_service_unit": "項",
      "product_service_quantity": "1.00",
      "product_service_unit_price": "450.000",
      "product_service_amount": "450.00"
    }},
    {{
      "product_service_name": "服務費用",
      "product_service_specification": "Calibration of slump cone set with HOKLAS certificate",
      "product_service_delivery_note_no": "",
      "product_service_unit": "項",
      "product_service_quantity": "1.00",
      "product_service_unit_price": "450.000",
      "product_service_amount": "450.00"
    }},
    {{
      "product_service_name": "服務費用",
      "product_service_specification": "Calibration of steel ruler",
      "product_service_delivery_note_no": "",
      "product_service_unit": "項",
      "product_service_quantity": "1.00",
      "product_service_unit_price": "420.000",
      "product_service_amount": "420.00"
    }},
    {{
      "product_service_name": "服務費用",
      "product_service_specification": "Calibration of temperature",
      "product_service_delivery_note_no": "",
      "product_service_unit": "項",
      "product_service_quantity": "1.00",
      "product_service_unit_price": "630.000",
      "product_service_amount": "630.00"
    }},
    {{
      "product_service_name": "服務費用",
      "product_service_specification": "Temperature distribution & circulation of curing tank",
      "product_service_delivery_note_no": "",
      "product_service_unit": "項",
      "product_service_quantity": "4.00",
      "product_service_unit_price": "1800.000",
      "product_service_amount": "7200.00"
    }},
    {{
      "product_service_name": "服務費用",
      "product_service_specification": "Provision and calibration of thermometer",
      "product_service_delivery_note_no": "",
      "product_service_unit": "項",
      "product_service_quantity": "5.00",
      "product_service_unit_price": "850.000",
      "product_service_amount": "4250.00"
    }},
    {{
      "product_service_name": "服務費用",
      "product_service_specification": "Sample collection /return fee",
      "product_service_delivery_note_no": "",
      "product_service_unit": "次",
      "product_service_quantity": "1.00",
      "product_service_unit_price": "500.000",
      "product_service_amount": "500.00"
    }},
    {{
      "product_service_name": "服務費用",
      "product_service_specification": "Sample collection fee",
      "product_service_delivery_note_no": "",
      "product_service_unit": "次",
      "product_service_quantity": "1.00",
      "product_service_unit_price": "500.000",
      "product_service_amount": "500.00"
    }},
    {{
      "product_service_name": "服務費用",
      "product_service_specification": "Temperature Distribution & circulation of Curing Tank",
      "product_service_delivery_note_no": "",
      "product_service_unit": "項",
      "product_service_quantity": "4.00",
      "product_service_unit_price": "1800.000",
      "product_service_amount": "7200.00"
    }}
  ],
  "invoice_no": "",
  "delivery_note_no": "",
  "remarks": ""
}}

## OCR识别的材料付办单附表文本：
{ocr_text}

## 强制遵循的JSON结构（字段名、层级、类型完全匹配）
{{
  "document_type": "字符串（文件类型，固定为\"payment_request_form_detail\"）",
  "site_name": "字符串（地盘名称，如：將軍澳海水化淡廠第一階段(CDX)）",
  "material_category": "字符串（材料分类，如：安全環保用品(U01)）",
  "date": "字符串（制单日期，如：2024-01-02）",
  "supplier_name": "字符串（供应商名称、客商名称，如：國際安全用品有限公司(ISEL)，无则填""）",
  "document_no": "字符串（付辦單號，如：CDX/2401/A/0001）",
  "contract_no": "字符串（合约编号，如：DPC/GEN/23033/00）",
  "invoice_date": "字符串（发票日期，如：2023-12-29）",
  "payment_method": "字符串（付款方式，如：支票）",
  "total_amount": "字符串（本期發生，如：12200.00）",
  "currency": "字符串（可选，币种，归一化为：HKD/USA/CNY/MOP，其他按原文，无则填""）",
  "product_service": [
    {{
      "product_service_name": "字符串（材料名称/费用类型，如：馬路欄河）",
      "product_service_specification": "字符串（规格型号/描述，如：XC0302 2M (L)黃色/橙色）",
      "product_service_delivery_note_no": "字符串（送货单编号，如：SNT2312-0110）",
      "product_service_unit": "字符串（计量单位，如：個）",
      "product_service_quantity": 數字格式（产品数量，數字格式，如100、10.12）,
      "product_service_unit_price": "字符串（单价，如：122.000）",
      "product_service_amount": "字符串（金额，如：12200.00）"
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
   - 数值类型约束：quantity 保留数字格式（提取时自动剥离单位，仅保留数字部分，如1,0000.45升 -> 10000.45，无则填0）；
   - 多产品处理：product_service为数组类型，文本中有多少个产品项就提取多少个，无产品则返回空数组[]；
   - 日期字段统一转换为**yyyy-MM-dd**格式；
   - 时间字段统一转换为**yyyy-MM-dd HH:mm:ss**格式；
   - 金额/单价值：保留数字格式（含小数点，如12200.00）；
3. 数据来源：仅从提供的OCR文本中提取，不编造、不猜测任何信息；
4. 格式适配：
   - 日期统一转换为yyyy-MM-dd格式（如"04 December, 2023"转换为"2023-12-04"）；
   - 地址/名称保留中英文混合原始格式，不做翻译或修改。
5. 币种归一化规则：
   - 识别到「港币、HKD、HK.Dollars、港币/HKD」等表示港币的文本，统一归一化为 "HKD"
   - 识别到「美元、USD、US Dollars、美金」等表示美元的文本，统一归一化为 "USA"
   - 识别到「人民币、CNY、RMB」等表示人民币的文本，统一归一化为 "CNY"
   - 识别到「澳币、MOP」等表示澳币的文本，统一归一化为 "MOP"
   - 不在上述范围内的币种，按原文提取
   
## 示例案例（帮助理解任务）
### 案例 1：
#### 输入：
# 永新五金工程有限公司
WING SUN METAL & ENGINEERING CO. LTD.
九龍旺角豉油街10號B地下
10B, SOY STREET, G/F., SUN MAN LEE BLDG., MONGKOK, KOWLOON.
TEL: 2396 7088 (5線)　FAX: 2396 7512
E-mail: wsmetal8@netvigator.com

## Delivery Note

| ID | 中國CDX / 4224 |
|---|---|
| Customer | 中國建築工程(香港)有限公司(海水化淡廠) |
| 客戶 |  |
| Attention | 卓生 |
| Phone | 9138 2007 |
| Reference | DPC/GEN/23003 |
| Fax | 3010 8232 |

| Delivery Note # | D23/005012 |
|---|---|
| Date | 04 December, 2023 |
| Page | 1 of 2 |
| Salesperson | CHOW |

| To | 將軍澳海水化淡廠 |
|---|---|
| Ship To | 將軍澳海水化淡廠 137 堆填區, 翠谷<br>卓生 9138 2007 / 林生 9215 3007 / 謝生 5962 9254 |

| Delivery | 04 December, 2023 |
| Payment | 月結 |
| Currency | HKD |
| Shipped | FOB |

| # | Description | Quantity |
|---:|---|---:|
| 001 | 維達三摺式抹手紙(16包/箱) | 30箱 |
| 002 | 維達廁紙 藍色 | 60條 |
| 003 | 維達面紙(60盒/箱) | 6箱 |
| 004 | 汽車香座香片 | 6個 |

**to be Continued**

#### 输出：
{{
  "document_type": "delivery_note",
  "document_no": "D23/005012",
  "supplier_id": "",
  "supplier_name": "永新五金工程有限公司 WING SUN METAL & ENGINEERING CO. LTD.",
  "supplier_address": "九龍旺角豉油街10號B地下",
  "supplier_phone": "2396 7088 (5線)",
  "site_name": "將軍澳海水化淡廠",
  "delivery_date": "2023-12-04",
  "product_service": [
    {{
      "product_service_name": "維達三摺式抹手紙(16包/箱)",
      "product_service_specification": "",
      "product_service_unit": "箱",
      "product_service_quantity": 30,
      "product_service_unit_price": "",
      "product_service_amount": ""
    }},
    {{
      "product_service_name": "維達廁紙 藍色",
      "product_service_specification": "",
      "product_service_unit": "條",
      "product_service_quantity": 60,
      "product_service_unit_price": "",
      "product_service_amount": ""
    }},
    {{
      "product_service_name": "維達面紙(60盒/箱)",
      "product_service_specification": "",
      "product_service_unit": "箱",
      "product_service_quantity": 6,
      "product_service_unit_price": "",
      "product_service_amount": ""
    }},
    {{
      "product_service_name": "汽車香座香片",
      "product_service_specification": "",
      "product_service_unit": "個",
      "product_service_quantity": 6,
      "product_service_unit_price": "",
      "product_service_amount": ""
    }}
  ],
  "currency": "HKD",
  "total_amount": "",
  "payment_method": "月結",
  "remarks": ""
}}

## OCR识别文本：
{ocr_text}

## 必须遵循的JSON结构（字段名、层级、类型完全匹配）：
{{
  "document_type": "字符串（文件类型，固定为\"delivery_note\"）",
  "document_no": "字符串（送貨單編號，如：D22-72035）",
  "supplier_id": "字符串（供應商ID，如：未提供則留空）",
  "supplier_name": "字符串（供應商名稱，如：民光電器行 MAN KWONG ELECTRIC CO.）",
  "supplier_address": "字符串（供應商地址，未提供則留空）",
  "supplier_phone": "字符串（供應商電話，未提供則留空）",
  "site_name": "字符串（送貨單收取人，如：中國建築工程(香港)有限公司(1511052-05)CDX 將軍澳海水化淡廠第一期(施工)）",
  "delivery_date": "字符串（送貨單日期，如：30/11/2022）",
  "product_service": [
    {{
      "product_service_name": "字符串（產品名稱，如：大尼龍袋）",
      "product_service_specification": "字符串（產品規格，如：PB1013）",
      "product_service_unit": "字符串（計量單位，如：個）",
      "product_service_quantity": 數字格式（產品數量，如：6000、10.91）,
      "product_service_unit_price": "字符串（單價，如：未提供則留空）",
      "product_service_amount": "字符串（金額，如：未提供則留空）"
    }}
  ],
  "currency": "字符串（可选，币种，归一化为：HKD/USA/CNY/MOP，其他按原文，无则填""）",
  "total_amount": "字符串（送貨單總金額，如：未提供則留空）"
}}


## 输出要求：
仅输出上述结构的JSON字符串，确保可直接通过Python的json.loads()解析，无需任何修改。
"""

QUOTATION_PROMPT = """
你是专业的报价单结构化数据提取专家，需严格按照指定JSON结构，从以下OCR识别的**报价单 / Quotation**文本中精准提取所有字段信息。

## 核心提取规则（必须严格遵守）
1. 输出格式：仅返回**合法可解析的JSON字符串**，不添加任何解释、备注、示例或额外文字；
2. 字段要求：
   - 所有字段名与指定JSON结构**完全一致**；
   - 未出现的信息统一填充为空字符串 `""`；
   - `product_service` 为数组，有多少条有效明细就输出多少条，无明细则返回 `[]`；
   - `product_service_quantity` 保留数字格式；
   - `product_service_unit_price`、`product_service_amount` 仅保留数字格式，不保留千分位逗号；
   - 日期字段统一转换为**yyyy-MM-dd**格式；
   - 时间字段统一转换为**yyyy-MM-dd HH:mm:ss**格式；
   - 金额/单价值：保留原文数字格式并移除币种符号与千分位逗号，如 `HK$ 1,800.00` → `1800.00`、`1800` → `1800`；
3. 数据来源：仅从OCR文本中提取，不编造、不猜测；
4. 字段理解：
   - `document_no` 报价单编号；
   - `quotation_date` 报价单日期，优先从 `Quotation Date` / `Quotation Date.` 提取；
   - `customer_name` 客户名称，优先从 `Messrs` / `Messers` 提取；
   - `project_name` 地盘名称，优先从 `Site` / `Project` / `Site/Project` 提取；
   - `supplier_name`、`supplier_address`、`supplier_phone` 优先从页首供应商抬头信息提取，其中 `supplier_name` 优先取英文主名，若无英文主名再取中文或原文拼接；
   - 明细若跨多行，首行主内容放入 `product_service_name`，后续标准/方法/规格说明放入 `product_service_specification`；
   - `currency` 需归一化为 `HKD/USA/CNY/MOP`，其他币种按原文；
5. 若当前页是续页且缺少主字段（如 `document_no`、`quotation_date`），则保持为空，不要臆造。
6. 币种归一化规则：
   - 识别到「港币、HKD、HK.Dollars、港币/HKD」等表示港币的文本，统一归一化为 "HKD"
   - 识别到「美元、USD、US Dollars、美金」等表示美元的文本，统一归一化为 "USA"
   - 识别到「人民币、CNY、RMB」等表示人民币的文本，统一归一化为 "CNY"
   - 识别到「澳币、MOP」等表示澳币的文本，统一归一化为 "MOP"
   - 不在上述范围内的币种，按原文提取

## 示例案例
### 案例 1：
#### 输入：
---
# Alchmex – Paul Y Joint Venture
Central Kowloon Route Contract No. HY/2018/02 – Kai Tak East
# 中九龍幹線 – 啟德東工程

# Quotation

**Quotation No. :** APYJV-CDU-24-007

**Messers :** China State Construction Engineering (Hong Kong) Limited
**Quotation Date :** 30-Jul-2022

**Site :** CDX - 將軍澳海水化淡廠

| Item | Description | Unit | Qty | Rate | Amount |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | 吊臂連 Winch | nos | 3 | HK$ 600.00 | HK$1,800.00 |
| | | | | | |
| | | | | | |
| | | | | | |
| | | | | | |

**Total :** HK$ 1,800.00

**Note :** Payment Term is 60 days from the date of Invoice.

Interest will be charged on overdue accounts at the rate 2% per month.

**For and on behalf of**
**Alchmex - Paul Y Joint Venture**

[Stamp: Alchmex-Paul Y Joint Venture 愛銘-保華聯營 中九龍幹線 啟德東工程 * HY/2018/02 *]

Authorized Signatiure

[Stamp: CHINA STATE CONST. ENG. (H.K.) LTD. 訂貨專用 中國建築工程(香港)有限公司 將軍澳海水化淡廠 第一階段 * 13/WSD/17 *]

#### 输出：
{{
  "document_type": "quotation",
  "document_no": "APYJV-CDU-24-007",
  "quotation_date": "2022-07-30",
  "customer_name": "China State Construction Engineering (Hong Kong) Limited",
  "customer_address": "",
  "project_name": "CDX - 將軍澳海水化淡廠",
  "supplier_id": "",
  "supplier_name": "Alchmex – Paul Y Joint Venture",
  "supplier_phone": "",
  "supplier_address": "",
  "product_service": [
    {{
      "product_service_name": "吊臂連 Winch",
      "product_service_specification": "",
      "product_service_unit": "nos",
      "product_service_quantity": 3,
      "product_service_unit_price": "600.00",
      "product_service_amount": "1800.00"
    }}
  ],
  "currency": "HKD",
  "total_amount": "1800.00"
}}

### 案例 2：
#### 输入：
---
# 香港試驗有限公司
# HONG KONG TESTING CO., LTD.
Rm. G04, G/F., & Rm. 205, 2/F., Fuk Shing Comm. Bldg., 28 On Lok Mun St., On Lok Tsuen, Fanling, N.T. Hong Kong.
- Tel: (852) 2692 2171 Fax: (852) 2691 4874 Email: info@hktesting.com.hk
- Website : www.hktesting.com.hk
香港新界粉嶺安樂村安樂門街28號福成商業大廈地下G04室及二樓205室 電話：(852) 2692 2171 傳真：(852) 2691 4874

## Quotation

**Messrs.** : CHINA STATE CONST. ENG'G (H.K.) LTD.
29/F., China Overseas Building,
139 Hennessy Road.,
H.K.

**Attn.** : Steven Lai
**Site/Project** : Contract No.: 12/WSD/17
Design, Build and Operate First Stage of Tseung Kwan O Desalination Plant

**Quotation**: HQ22-0670
**Quotation Date** : 29 Apr 2022
**Customer** : C0279
**Tel** : 5169 7261
**Email** : singfun_lai@cohl.com

P. 1 of 2

| Item | Product Description | Qty. | Unit | Price HK$ | Amount HK$ |
| :--- | :--- | :--- | :--- | :--- | :--- |
| | **Calibration Services** | | | | |
| 1) | Calibration of Temperature Distribution & Circulation of Curing Tank
- CS1 : 2010 Vol. 1 App. A28 | 0 | No. | 1,800 | 0.00 |
| 2) | Calibration of 100mm Cube Mould
- CS1 : 2010 Vol. 1 App. A25 | 0 | No. | 160 | 0.00 |
| 3) | Calibration of Slump Cone - Including Tamping Rod
- CS1 : 2010 Vol. 1 App. A5 & A6 | 0 | No. | 450 | 0.00 |
| 4) | Calibration of Compacting Bar
- CS1 : 2010 Vol. 1 App. A10 | 0 | No. | 150 | 0.00 |
| 5) | Calibration of Temperature (0, 10 to 180°C) - 3 points check
In-House Method (HOKLAS) | 0 | No. | 630 | 0.00 |
| 6) | Calibration of Steel Ruler (up to 300mm)
In-House Method (HOKLAS) | 0 | No. | 420 | 0.00 |
| | **Other** | | | | |
| 7) | Sample collection charge | 0 | Trip | 500 | 0.00 |
| | **Net Amount** | | | **HK$** | **0.00** |

**Trade Terms** :
1. This quotation is valid for 30 days.
2. Rates are based on normal working hours 09:00 to 17:00, Monday to Saturday (excluding Public Holidays & lunch hour). Waiting time and overtime work instructed shall be charged for additional HK$200.00/man/hour.
3. Rates include 1 original of test report.
4. Additional copy will be charged at HK$10.00 per sheet without photo & HK$15.00 per sheet with photo. The minimum charge is HK$300.00.
5. Certified true copy or Amendment of test report due to incorrect information provided by customer will be levied at HK$30.00/sheet. The minimum charge is HK$300.00.
6. Water, electricity, scaffolding, working platform, gondola & safety facilities should be provided by customer.
7. All our test reports & relevant data may be inspected by local Government Authorities during their surveillance visits.
8. All the information obtained or created during the performance of laboratory activities will be kept confidential. They will only be released as required by law.

Cont. on page 2

#### 输出：
{{
  "document_type": "quotation",
  "document_no": "HQ22-0670",
  "quotation_date": "2022-04-29",
  "customer_name": "CHINA STATE CONST. ENG'G (H.K.) LTD.",
  "customer_address": "29/F., China Overseas Building, 139 Hennessy Road., H.K.",
  "project_name": "Contract No.: 12/WSD/17 Design, Build and Operate First Stage of Tseung Kwan O Desalination Plant",
  "supplier_id": "",
  "supplier_name": "HONG KONG TESTING CO., LTD.",
  "supplier_phone": "(852) 2692 2171",
  "supplier_address": "Rm. G04, G/F., & Rm. 205, 2/F., Fuk Shing Comm. Bldg., 28 On Lok Mun St., On Lok Tsuen, Fanling, N.T. Hong Kong.",
  "product_service": [
    {{
      "product_service_name": "Calibration of Temperature Distribution & Circulation of Curing Tank",
      "product_service_specification": "CS1 : 2010 Vol. 1 App. A28",
      "product_service_unit": "No.",
      "product_service_quantity": 0,
      "product_service_unit_price": "1800",
      "product_service_amount": "0.00"
    }},
    {{
      "product_service_name": "Calibration of 100mm Cube Mould",
      "product_service_specification": "CS1 : 2010 Vol. 1 App. A25",
      "product_service_unit": "No.",
      "product_service_quantity": 0,
      "product_service_unit_price": "160",
      "product_service_amount": "0.00"
    }},
    {{
      "product_service_name": "Calibration of Slump Cone - Including Tamping Rod",
      "product_service_specification": "CS1 : 2010 Vol. 1 App. A5 & A6",
      "product_service_unit": "No.",
      "product_service_quantity": 0,
      "product_service_unit_price": "450",
      "product_service_amount": "0.00"
    }},
    {{
      "product_service_name": "Calibration of Compacting Bar",
      "product_service_specification": "CS1 : 2010 Vol. 1 App. A10",
      "product_service_unit": "No.",
      "product_service_quantity": 0,
      "product_service_unit_price": "150",
      "product_service_amount": "0.00"
    }},
    {{
      "product_service_name": "Calibration of Temperature (0, 10 to 180°C) - 3 points check",
      "product_service_specification": "In-House Method (HOKLAS)",
      "product_service_unit": "No.",
      "product_service_quantity": 0,
      "product_service_unit_price": "630",
      "product_service_amount": "0.00"
    }},
    {{
      "product_service_name": "Calibration of Steel Ruler (up to 300mm)",
      "product_service_specification": "In-House Method (HOKLAS)",
      "product_service_unit": "No.",
      "product_service_quantity": 0,
      "product_service_unit_price": "420",
      "product_service_amount": "0.00"
    }},
    {{
      "product_service_name": "Sample collection charge",
      "product_service_specification": "",
      "product_service_unit": "Trip",
      "product_service_quantity": 0,
      "product_service_unit_price": "500",
      "product_service_amount": "0.00"
    }}
  ],
  "currency": "HKD",
  "total_amount": "0.00"
}}

## OCR识别的报价单文本：
{ocr_text}

## 强制遵循的JSON结构（字段名、层级、类型完全匹配）
{{
  "document_type": "字符串（文件类型，固定为\"quotation\"）",
  "document_no": "字符串（报价单编号，如：CDX/2312/A/0090）",
  "quotation_date": "字符串（报价单日期，格式：YYYY-MM-DD）",
  "customer_name": "字符串（客户名称）",
  "customer_address": "字符串（客户地址）",
  "project_name": "字符串（项目名称）",
  "supplier_id": "字符串（供应商ID，无则填\"\"）",
  "supplier_name": "字符串（供应商名称，无则填\"\"）",
  "supplier_phone": "字符串（供应商电话，无则填\"\"）",
  "supplier_address": "字符串（供应商地址，无则填\"\"）",
  "product_service": [
    {{
      "product_service_name": "字符串（产品或服务名称）",
      "product_service_specification": "字符串（规格型号）",
      "product_service_unit": "字符串（单位）",
      "product_service_quantity": "数字格式（数量）",
      "product_service_unit_price": "字符串（单价）",
      "product_service_amount": "字符串（金額）"
    }}
  ],
  "currency": "字符串（币种，归一化为 HKD/USA/CNY/MOP，其他按原文）",
  "total_amount": "字符串（总金额）"
}}

## 最终输出要求
仅输出上述结构的JSON字符串，无任何其他内容，确保字段完整、类型正确、可直接转换为对应数据模型。
"""

RECEIPT_PROMPT = """
你是专业的收据结构化数据提取专家，需严格按照指定JSON结构，从以下OCR识别的**收據 / 收据 / Receipt**文本中精准提取所有字段信息。

## 核心提取规则（必须严格遵守）
1. 输出格式：仅返回**合法可解析的JSON字符串**，不添加任何解释、备注、示例或额外文字；
2. 字段要求：
   - 所有字段名与指定JSON结构**完全一致**；
   - 未出现的信息统一填充为空字符串 `""`；
   - `product_service` 为数组，有多少条有效收费明细就输出多少条，无明细则返回 `[]`；
   - `product_service_quantity` 保留数字格式；
   - `product_service_unit_price`、`product_service_amount` 仅保留数字格式，不保留千分位逗号或币种符号；
3. 数据来源：仅从OCR文本中提取，不编造、不猜测；
4. 字段理解：
   - `document_type` 固定输出 `receipt`；
   - `document_no` 取收据号，不要误提取 `提單號碼` 作为 `document_no`；
   - `license_plate` 取 `車牌` / `车牌`；
   - `customer_address` 仅在明确出现客户地址时提取；
   - `project_name` 仅在明确出现 `Site` / `Project` / `地盤` / `工程` 时提取；`貨品` 不是 `project_name`；
   - `supplier_name`、`supplier_address`、`supplier_phone` 优先从页首供应商抬头提取，其中 `supplier_name` 优先取英文主名，若无英文主名再取中文或原文；
5. 明细表规则：
   - 若同一物理表格行同时包含 `過磅費` 与 `吊機費` 两类收费，允许拆成两条 `product_service`；
   - `過磅費` / `吊機費` 等栏目标题可作为 `product_service_name`；
   - 如 `Y12 6.15T`、`Y20 30.184斤` 这类文本，型号编号放入 `product_service_specification`，数量与单位拆到 `product_service_quantity`、`product_service_unit`；
   - `管理費`、`代客過磅費` 若没有金额，不得输出为明细；若有金额，可单独输出为一条明细；
   - `總金額` / `总金额` 行是汇总信息，不得写入 `product_service`；
   - 全空行、占位行、签名行（如 `經手人`）不得写入 `product_service`；
6. 币种归一化规则：
   - 识别到「港币、HKD、HK.Dollars、港币/HKD」等表示港币的文本，统一归一化为 "HKD"
   - 识别到「美元、USD、US Dollars、美金」等表示美元的文本，统一归一化为 "USA"
   - 识别到「人民币、CNY、RMB」等表示人民币的文本，统一归一化为 "CNY"
   - 识别到「澳币、MOP」等表示澳币的文本，统一归一化为 "MOP"
   - 不在上述范围内的币种，按原文提取

## 示例案例
### 案例 1：
#### 输入：
盈信發展(香港)有限公司
Great Success Development (Hong Kong) Limited
寫字樓：香港灣仔告士打道151號資本中心7樓701室
電話：2892 1522　傳真：2833 5676

收據
No. 12060
客戶：中建（楊小）
日期：24/12/14
提單號碼：52611
車牌：7F84
貨品：螺紋鋼及鋼材

<table>
  <tr><th>過磅費</th><th colspan="4">吊機費</th></tr>
  <tr><th>花式</th><th>金額</th><th>花式及淨重</th><th>單價</th><th>金額</th></tr>
  <tr><td>12×200</td><td>200</td><td>Y12 6.15T</td><td>$70</td><td>431</td></tr>
  <tr><td></td><td></td><td>Y16 6.14T</td><td>$70</td><td>430</td></tr>
  <tr><td>總金額：</td><td></td><td></td><td></td><td>1061</td></tr>
</table>

#### 输出：
{{
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
    {{
      "product_service_name": "過磅費",
      "product_service_specification": "12×200",
      "product_service_unit": "",
      "product_service_quantity": 0,
      "product_service_unit_price": "",
      "product_service_amount": "200"
    }},
    {{
      "product_service_name": "吊機費",
      "product_service_specification": "Y12",
      "product_service_unit": "T",
      "product_service_quantity": 6.15,
      "product_service_unit_price": "70",
      "product_service_amount": "431"
    }},
    {{
      "product_service_name": "吊機費",
      "product_service_specification": "Y16",
      "product_service_unit": "T",
      "product_service_quantity": 6.14,
      "product_service_unit_price": "70",
      "product_service_amount": "430"
    }}
  ],
  "currency": "HKD",
  "total_amount": "1061"
}}

## OCR识别的收据文本：
{ocr_text}

## 强制遵循的JSON结构（字段名、层级、类型完全匹配）
{{
  "document_type": "字符串（文件类型，固定为\"receipt\"）",
  "document_no": "字符串（收据编号，如：12060）",
  "license_plate": "字符串（车牌号码）",
  "customer_name": "字符串（客户名称）",
  "customer_address": "字符串（客户地址，无则填\"\"）",
  "project_name": "字符串（项目名称/地盘名称，无则填\"\"）",
  "supplier_id": "字符串（供应商ID，无则填\"\"）",
  "supplier_name": "字符串（供应商名称，无则填\"\"）",
  "supplier_phone": "字符串（供应商电话，无则填\"\"）",
  "supplier_address": "字符串（供应商地址，无则填\"\"）",
  "product_service": [
    {{
      "product_service_name": "字符串（收费项目名称，如：過磅費、吊機費）",
      "product_service_specification": "字符串（规格/花式/型号）",
      "product_service_unit": "字符串（单位，如：T、斤）",
      "product_service_quantity": "数字格式（数量）",
      "product_service_unit_price": "字符串（单价）",
      "product_service_amount": "字符串（金額）"
    }}
  ],
  "currency": "字符串（币种，归一化为 HKD/USA/CNY/MOP，其他按原文）",
  "total_amount": "字符串（总金额）"
}}

## 最终输出要求
仅输出上述结构的JSON字符串，无任何其他内容，确保字段完整、类型正确、可直接转换为对应数据模型。
"""

MISC_MATERIALS_APP_PROMPT = """
你是专业的建筑行业杂项材料申请表结构化数据提取专家，需严格按照指定的JSON结构，从以下OCR识别的杂项材料申请表文本中提取所有字段信息，文本可能包含繁体中文/英文混合内容，请精准识别并保留原始格式。

## 核心提取规则（必须严格遵守，缺一不可）
1. 输出格式：仅返回**合法可解析的JSON字符串**，不添加任何解释、备注、示例、换行或额外文字，确保可直接通过Python的json.loads()解析；
2. 字段要求：
   - 所有字段名称必须与指定JSON结构**完全一致**（包括大小写、中英文），无遗漏、无新增；
   - 所有字段若无对应信息，统一填充为**空字符串""**（无则填0）；
   - 数值类型约束：quantity 保留数字格式（提取时自动剥离单位，如"50.00個"→50.00，无则填0）；
   - 列表/数组处理：
     - product_service：有多少产品项就提取多少，无则返回空数组[]；
     - order_contact：有多少订货人就提取多少，无则返回空数组[]；
   - 日期字段统一转换为**yyyy-MM-dd**格式；
   - 时间字段统一转换为**yyyy-MM-dd HH:mm:ss**格式；
   - 金额/单价值：保留数字格式（含小数点，如12200.00）；
   - 嵌套结构：严格按层级提取（site_receiver为单层对象，order_contact为数组对象）；
3. 数据来源：仅从提供的OCR文本中提取，不编造、不猜测、不补充任何未提及的信息；
4. 格式统一：
   - 日期字段统一转换为**yyyy-MM-dd**格式；
   - 时间字段统一转换为**yyyy-MM-dd HH:mm:ss**格式；
   - 名称/编号/联系方式保留原始内容（含括号、符号、中英文），不做翻译或修改。
   
## 示例案例（帮助理解任务）
### 案例 1：
#### 输入：
# 中國建築工程(香港)有限公司

# 地盤零星材料申請表

**地盤名稱：** 將軍澳海水化淡廠第一階段(CDX)  
**日期：** 2-Aug-24  
**編號：** CDX3798

| 序號 | 材料名稱 & 規格 | 單位 | 數量 | 進貨日期 | 材料用途及使用位置 | 合約編號 | 項目 |
|---|---|---|---:|---|---|---|---|
| 1 | 石星KC-9920安全鞋 #39<br>MD0226 | 對 | 1 |  | RE order : RF265 | MD0226 | 24023 |
| 2 | 石星KC-9920安全鞋 #41<br>MD0226 | 對 | 1 |  | RE order : RF265 | MD0226 | 24023 |
| 3 | 石星KC-9920安全鞋 #42<br>MD0226 | 對 | 1 |  | RE order : RF265 | MD0226 | 24023 |
| 4 | 石星KC-9920安全鞋 #43<br>MD0226 | 對 | 1 |  | RE order : RF265 | MD0226 | 24023 |
| 5 | 石星Smaat SFC210 安全鞋（短）#42 MD0223 | 對 | 1 |  | RE order : RF265 | MD0223 | 24023 |

## 簽署

**地盤負責人：** （簽署）  
**地盤內派主管審核：** （簽署，旁註似為「301」）  
**製單人：** 凡  
**申請人：** RE MAY SO

右下有紫色圓形公司章，內容可辨識為：  
CHINA STATE CONST. ENG. (H.K.) LTD.  
中國建築工程(香港)有限公司  
將軍澳海水化淡廠  
第一階段  
13/WSD/17

## 備註

備註: 定點名冊材料申請表必須由物料控制員填寫「合約編號」及「項目」兩欄。

## 聯絡資料框

**煩請訂貨**

聯絡人: 卓生  
電話: 9138 2007

聯絡人: 林生  
電話: 9215 3007

傳真: 3010 8232

地盤收貨人: 馮生  電話: 9249 9108

#### 输出：
{{
    "document_type": "misc_materials_app",
    "product_service": [
        {{
            "product_service_name": "石星KC-9920安全鞋",
            "product_service_specification": "#39 MD0226",
            "product_service_unit": "對",
            "product_service_quantity": "1",
            "product_service_contract_no": "MD0226"
        }},
        {{
            "product_service_name": "石星KC-9920安全鞋",
            "product_service_specification": "#41 MD0226",
            "product_service_unit": "對",
            "product_service_quantity": "1",
            "product_service_contract_no": "MD0226"
        }},
        {{
            "product_service_name": "石星KC-9920安全鞋",
            "product_service_specification": "#42 MD0226",
            "product_service_unit": "對",
            "product_service_quantity": "1",
            "product_service_contract_no": "MD0226"
        }},
        {{
            "product_service_name": "石星KC-9920安全鞋",
            "product_service_specification": "#43 MD0226",
            "product_service_unit": "對",
            "product_service_quantity": "1",
            "product_service_contract_no": "MD0226"
        }},
        {{
            "product_service_name": "石星Smaat SFC210 安全鞋（短）",
            "product_service_specification": "#42 MD0223",
            "product_service_unit": "對",
            "product_service_quantity": "1",
            "product_service_contract_no": "MD0223"
        }},
    ],
    "order_contact": [
        {{
            "order_contact_name": "卓生",
            "order_contact_phone": "9138 2007",
            "order_contact_fax": null,
            "order_contact_email": null
        }},
        {{
            "order_contact_name": "林生",
            "order_contact_phone": "9215 3007",
            "order_contact_fax": "3010 8232",
            "order_contact_email": null
        }}
    ],
    "document_no": "CDX3817",
    "site_name": "將軍澳海水化淡廠第一階段(CDX)",
    "date": "2024-08-20",
    "order_creator": "凡",
    "applicant": "RE MAY SO",
    "site_receiver": {{
        "site_receiver_name": "馮生",
        "site_receiver_phone": "9249 9108"
    }}
}}

## OCR识别的地盤零星材料申請表文本：
{ocr_text}

## 强制遵循的JSON结构（字段名、层级、类型完全匹配）
{{
  "document_type": "字符串（文件类型，固定为\"misc_materials_app\"）",
  "document_no": "字符串（文件编号，如：MMA/2403/0015）",
  "site_name": "字符串（地盘名称，如：將軍澳海水化淡廠(CDX)）",
  "date": "字符串（日期，如：2024-03-15）",
  "product_service": [
    {{
      "product_service_name": "字符串（产品/材料名称，如：尼龍扎帶）",
      "product_service_specification": "字符串（规格，如：4×200mm）",
      "product_service_unit": "字符串（单位，如：包/個/米）",
      "product_service_quantity": 數字格式（数量，如100、100.19，无则填0）,
      "product_service_contract_no": "字符串（合约编号，如：DPC/GEN/23033/00）"
    }}
  ],
  "order_creator": "字符串（制单人，如：張三）",
  "applicant": "字符串（申请人，如：李四）",
  "order_contact": [
    {{
      "order_contact_name": "字符串（订货人姓名，如：王五）",
      "order_contact_phone": "字符串（订货人电话，如：9123 4567）",
      "order_contact_fax": "字符串（订货人传真，如：3012 3456）",
      "order_contact_email": "字符串（订货人邮箱，如：wangwu@xxx.com）"
    }}
  ],
  "site_receiver": {{
    "site_receiver_name": "字符串（地盘收货人姓名，如：趙六）",
    "site_receiver_phone": "字符串（地盘收货人电话，如：9876 5432）"
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
   - 补充：document_no 字段优先填充「檔案參考號、File Reference」；若无可提取的檔案參考號，則用「iGTB 參考號 iGTB Reference」填充；两者均无则填 ""；
3. 数据来源：仅从提供的OCR文本中提取，不编造、不猜测、不补充任何未提及的信息；
4. 格式统一：
   - 名称/编号/联系方式保留原始内容（含括号、符号、中英文），不做翻译或修改。
   - 日期字段统一转换为**yyyy-MM-dd**格式；
   - 时间字段统一转换为**yyyy-MM-dd HH:mm:ss**格式；
   - 金额/单价值：保留数字格式（含小数点，如12200.00）；
5. 币种归一化规则：
   - 识别到「港币、HKD、HK.Dollars、港币/HKD」等表示港币的文本，统一归一化为 "HKD"
   - 识别到「美元、USD、US Dollars、美金」等表示美元的文本，统一归一化为 "USA"
   - 识别到「人民币、CNY、RMB」等表示人民币的文本，统一归一化为 "CNY"
   - 识别到「澳币、MOP」等表示澳币的文本，统一归一化为 "MOP"
   - 不在上述范围内的币种，按原文提取
   
## 示例案例（帮助理解任务）
### 案例 1：
#### 输入：
# 中國銀行(香港) iGTB
# BANK OF CHINA (HONG KONG)

- 參考號 Request ID:25342047714
- 列印人員 Request User ID:YAN
製作日 For Date / Request Date & Time:8 Dec 2025 12:43

# iGTB 012-875-68-29941-5>工作列Work Queue >檔案指令報告File Instruction Report

## 檔案詳情 File Detail
- 更新於 Refreshed as at:8 Dec 2025 12:43

- 檔案名稱File Name: Y2025121001.DAT
- 檔案參考號File Reference: F2534271682
- 狀態 Status: 等候第一次授權Pending 1st Authorisation
- iGTB參考號 iGTB Reference: 02121750335
- 指示類型Instruction Type: ACH 支付文件上載ACH Payment File Upload
- 最後跟進Last Action: 8 Dec 2025 12:42 GMT+08:00 by YEUNG SZE MAN

## 交易詳情Transaction Detail

- 發起賬戶號碼Originating Account Number: 012-699-2-030055-3
- 發起賬戶名稱Originating Account Name: CHINA STATE - STEC JOINT VENTURE
- 生效日期 Effective Date: 2025/12/10
- 交易筆數 Transaction Count: 1
- 總金額 Total Amount: HKD 122206.00

| 編號 No. | 目標賬戶號碼 Destination A/C | 目標賬戶名稱 Destination A/C Name | 貨幣 Currency | 金額 Amount | 參考號 Reference | 備註 Remark |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | 004111418042001 | Construction Industry Council | HKD | 122206.00 | Y2025121001 | DN3418712 |

iGTB 012-875-68-29941-5>工作列Work Queue >檔案指令報告File Instruction Report
Y2025121001.DAT F2534271682
Page 1 of 2

Scanned with
CamScanner

#### 输出：
{{
    "document_type": "transaction",
    "document_no": "F2534271682",
    "document_name": "Y2025121001.DAT",
    "document_status": "等候第一次授權Pending 1st Authorisation",
    "igbt_reference": "02121750335",
    "originating_account_number": "012-699-2-030055-3",
    "originating_account_name": "CHINA STATE - STEC JOINT VENTURE",
    "effective_date": "2025-12-10",
    "transaction_count": "1",
    "currency": "HKD",
    "total_amount": "122206.00",
    "transactions": [
        {{
            "transactions_destination_account_number": "004111418042001",
            "transactions_destination_account_name": "Construction Industry Council",
            "transactions_currency": "HKD",
            "transactions_amount": "122206.00",
            "transactions_reference": "Y2025121001",
            "transactions_remark": "DN3418712"
        }}
    ]
}}

### 案例 2：
#### 输入：
# 中國銀行(香港) iGTB

# 工作列 查詢 信息管理 支付 環球貿易業務 收款 財資 流動性管理 本港特色服務 列印

# 交易詳情

< 返回 記錄和評論

## 繳付賬單
* 標記第一次存檔

**iGTB參考號**
02127063960

**交易日期和時間**
2025年12月12日 15:11 GMT+08:00

**經辦人員**
AGNES

**由***
CHINA STATE - STEC JOINT VENTURE
012-699-2-030055-3
中國香港 港元儲蓄賬戶

**至***
環境保護署
01 - 化學廢物繳費單
035047011

**支付金額**
HKD 6,754.00

## 交易詳情

**金額**
支付金額*
HKD 6,754.00

## 支付時間表

**支付時間表***
即時遞交

## 補充資料

**內部支付備忘**
035047011

**客戶參考號**
035047011

版權條款 | 重要聲明及私隱政策聲明 | 保安資訊 | 超連結政策 | 系統升級時間表 | 表格和申請 | 企業電子及線上服務條款

Scanned with
CamScanner

#### 输出：
{{
    "document_type": "transaction",
    "document_no": "02127063960",
    "document_name": "",
    "document_status": "",
    “igbt_reference": "02127063960",
    "originating_account_number": "012499-2-020951-3",
    "originating_account_name": "CHINA STATE - STEC JOINT VENTURE",
    "effective_date": "2025-12-12",
    "transaction_count": "",
    "currency": "HKD",
    "total_amount": "6754.00",
    "transactions": [
        {{
            "transactions_destination_account_number": "",
            "transactions_destination_account_name": "環境保護號: 01-小額付款賬單",
            "transactions_currency": "HKD",
            "transactions_amount": "6754.00",
            "transactions_reference": "035047011",
            "transactions_remark": "035047011"
        }}
    ],
}}

### 案例 3：
#### 输入：
# 中國銀行(香港)有限公司
**BANK OF CHINA (HONG KONG) LIMITED**

灣仔中國海外大廈分行：香港灣仔軒尼詩道139號中國海外大廈地下C舖
Wan Chai (China Overseas Building) Branch
Shop C, G/F, China Overseas Building, 139 Hennessy Road, Wan Chai, Hong Kong.

**04**     **12**      **2025**
日 DAY      月 MONTH      年 YEAR

祈付
PAY **中華電力有限公司**  或指定人
OR ORDER

港  幣
H.K. DOLLARS **柒万叁仟叁佰柒拾肆元整** &......

⑈000086⑈ 012⑉699⑆ 20300566⑈

Scanned with
CamScanner


#### 输出：
{{
    "document_type": "transaction",
    "document_no": "00008601269920300566",
    "document_name": "",
    "document_status": "",
    "igbt_reference": "",
    "originating_account_number": "",
    "originating_account_name": "CHINA STATE - STEC JOINT VENTURE",
    "effective_date": "2025-12-04",
    "transaction_count": "1",
    "currency": "HKD",
    "total_amount": "73374.00",
    "transactions": [
        {{
            "transactions_destination_account_number": "",
            "transactions_destination_account_name": "中華電力有限公司",
            "transactions_currency": "HKD",
            "transactions_amount": "73374.00",
            "transactions_reference": "",
            "transactions_remark": ""
        }}
    ]
}}


## OCR识别的交易记录文本：
{ocr_text}

## 强制遵循的JSON结构（字段名、层级、类型完全匹配）
{{
  "document_type": "字符串（文件类型，固定为\"transaction\"）",
  "document_no": "字符串（文件编号，檔案參考號，如：F2534271682，优先填檔案參考號，无则填 iGTB 參考號，均无则填""）",
  "document_name": "字符串（檔案名稱，如：Y2025121001.DAT）",
  "document_status": "字符串（狀態，如：等候第一次授權Pending 1st Authorisation）",
  "igbt_reference": "字符串（IGBT编号，如：02121750335）",
  "originating_account_number": "字符串（發起賬戶號碼，如：012-699-2-030055-3）",
  "originating_account_name": "字符串（發起賬戶名稱，如：CHINA STATE - STECJOINT VENTURE）",
  "effective_date": "字符串（生效日期，如：2025-12-10）",
  "transaction_count": "字符串（交易筆數，如：1）",
  "currency": "字符串（可选，幣種，归一化为：HKD/USA/CNY/MOP，其他按原文，无则填""）",
  "total_amount": "字符串（總金額，如：122206.00）",
  "cheque_number": "字符串（支票號碼）",
  "transactions": [
    {{
      "transactions_destination_account_number": "字符串（目標帳戶號碼，如：004111418042001）",
      "transactions_destination_account_name": "字符串（目標帳戶號碼名稱，如：Construction Industry Council）",
      "transactions_currency": "字符串（可选，幣種，归一化为：HKD/USA/CNY/MOP，其他按原文，无则填""）",
      "transactions_amount": "字符串（金額，如：122206.00）",
      "transactions_reference": "字符串（參考號，如：Y2025121001）",
      "transactions_remark": "字符串（備注，如：DN3418712）"
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
        document_type: 文档类型（invoice, payment_request_form, payment_request_form_detail, delivery_note, misc_materials_app, transaction等）

    Returns:
        格式化后的Prompt字符串
    """
    # 定义文档类型到Prompt模板的映射
    prompt_mapping = {
        "invoice": INVOICE_PROMPT,
        "quotation": QUOTATION_PROMPT,
        "receipt": RECEIPT_PROMPT,
        "payment_request_form": PAYMENT_REQUEST_FORM_PROMPT,
        "payment_request_form_detail": PAYMENT_REQUEST_FORM_DETAIL_PROMPT,
        "delivery_note": DELIVERY_NOTE_PROMPT,
        "misc_materials_app": MISC_MATERIALS_APP_PROMPT,
        "transaction": TRANSACTION_RECORD_PROMPT
    }


    # 获取对应的Prompt模板，如果类型不存在则使用发票模板作为默认值
    template = prompt_mapping.get(document_type, INVOICE_PROMPT)

    # 将OCR文本插入到Prompt模板中
    return template
