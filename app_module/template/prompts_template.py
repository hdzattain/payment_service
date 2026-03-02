# -*- 发票 PROMPT -*-
INVOICE_PROMPT = """
你是一个专业的财务票据结构化数据提取专家，需严格按照指定的JSON结构，从以下OCR识别的发票文本中提取所有字段信息。
## 核心规则（必须严格遵守）：
1. 输出格式：仅返回合法的JSON字符串，不添加任何解释、备注、示例或额外文字；
2. 字段要求：
   - 所有字段名称必须与指定结构完全一致（包括大小写、中英文）；
   - 非Optional字段（如name、supplier_name）若文本中无对应信息，填充为空字符串""；
   - Optional字段（如unit_price、currency）若无信息，填充为空字符串""；
   - 数值类型约束：quantity为整数（无则留空）；
   - 日期字段统一转换为**yyyy-MM-dd**格式；
   - 时间字段统一转换为**yyyy-MM-dd HH:mm:ss**格式；
   - 金额/单价值：保留数字格式（含小数点，如12200.00）；
3. 数据来源：仅从提供的OCR文本中提取，不编造、不猜测任何信息；
4. 嵌套结构：严格按照层级嵌套，supplier对应供应商信息，product_service对应产品/服务项目。

## 示例案例（帮助理解任务）
### 案例 1：
#### 输入：
MESSRS.: 中國建築工程(香港)有限公司(海水化淡廠)

發 INVOICE 票

<table>
  <tr>
    <th>貨名<br>DESCRIPTION</th>
    <th>數量<br>QUANTITY</th>
    <th>單價<br>UNIT PRICE</th>
    <th>金額<br>AMOUNT</th>
  </tr>
  <tr>
    <td>025 菊花牌膠手套(中碼) 黃色</td>
    <td>4 對</td>
    <td>26.0000</td>
    <td>104.00</td>
  </tr>
  <tr>
    <td>026 36" X 48" 黑色垃圾袋100個/包 厚身</td>
    <td>3 包</td>
    <td>250.0000</td>
    <td>750.00</td>
  </tr>
  <tr>
    <td>027 水鞋(38碼)</td>
    <td>1 對</td>
    <td>68.0000</td>
    <td>68.00</td>
  </tr>
  <tr>
    <td>028 透明即棄膠手套(100只/盒)(白色M碼)</td>
    <td>11 盒</td>
    <td>100.0000</td>
    <td>1,100.00</td>
  </tr>
  <tr>
    <td>029 大垃圾桶連蓋16" X 17" X 24" (45L) 腳踏灰色</td>
    <td>4 個</td>
    <td>180.0000</td>
    <td>720.00</td>
  </tr>
</table>

TOTAL HKD 18,891.00

#### 输出：
{{
    "document_type": "invoice",
    "product_service": [
        {{
            "name": "025 菊花牌膠手套(中碼) 黃色",
            "unit_price": "26.0000",
            "unit": "對",
            "quantity": "4",
            "amount": "104.00"
        }},
        {{
            "name": "026 36\" X 48\" 黑色垃圾袋100個/包 厚身",
            "unit_price": "250.0000",
            "unit": "包",
            "quantity": "3",
            "amount": "750.00"
        }},
        {{
            "name": "027 水鞋(38碼)",
            "unit_price": "68.0000",
            "quantity": "1 對",
            "amount": "68.00"
        }},
        {{
            "name": "028 透明即棄膠手套(100只/盒)(白色M碼)",
            "unit_price": "100.0000",
            "unit": "盒",   
            "quantity": "11",
            "amount": "1100.00"
        }},
        {{
            "name": "029 大垃圾桶連蓋16\" X 17\" X 24\" (45L) 腳踏灰色",
            "unit_price": "180.0000",
            "unit": "個",
            "quantity": "4",
            "amount": "720.00"
        }}
    ],
    "order_contact": [],
    "currency": "HKD",
    "total_amount": "18891.00",
    "document_no": "",
    "invoice_date": "",
    "site_name": "中國建築工程(香港)有限公司(海水化淡廠)",
    "supplier": {{
        "supplier_id": "",
        "supplier_name": "",
        "address": "",
        "phone": ""
    }}
}}

### 案例 2：
#### 输入：
Hoi Hing Building Materials Co. Limited
ROOM 306, 3/F., JOIN IN HANG SING CENTRE, 71-75 CONTAINER PORT ROAD, KWAI CHUNG, N.T., HONG KONG
TEL: 2388 0263, 2536 2900   FAX: 2770 4137
門市部：九龍旺角甘霖街22號地下
G/F., 22 KAM LAM STREET, MONGKOK, KOWLOON, H.K.
TEL: 2398 8902

TO: 中國建築工程(香港)有限公司(1511052-05)
CDX 將軍澳海水化淡廠第一期(施工)

ATTN: 卓先生
TEL NO.: 9138 2007
FAX NO.: 

發票
INVOICE

發票編號
INVOICE NO.: H2239266
日期
DATE: 30/11/2022
客戶訂單編號
P.O. NO.: 
營業員
SALES: SAMMI
客戶編號
CUSTOMER CODE: 1511052-05
頁數
PAGE NO.: 1

<table>
  <tr>
    <th>ITEM</th>
    <th>摘要<br>Description</th>
    <th>送貨單編號<br>D.N. NO.</th>
    <th>數量<br>Quantity</th>
    <th>單價<br>Unit Price</th>
    <th>金額<br>Amount</th>
  </tr>
  <tr>
    <td>PG0801</td>
    <td>DPC/GEN/22068/00<br>~ 3/4" 黃風喉 PG0801</td>
    <td>D22-72035</td>
    <td>3 卷</td>
    <td>580.00</td>
    <td>1,740.00</td>
  </tr>
  <tr>
    <td>PG0803</td>
    <td>~ 1" 黃風喉PG0803<br>編號(CDX2324)</td>
    <td></td>
    <td>3 卷</td>
    <td>840.00</td>
    <td>2,520.00</td>
  </tr>
  <tr>
    <td>PG0401</td>
    <td>^220V 1" 1/8HP 鶴見牌 水泵<br>Model: Family12(PG0401)<br>編號: CDX2347</td>
    <td>D22-74883</td>
    <td>2 台</td>
    <td>680.00</td>
    <td>1,360.00</td>
  </tr>
  <tr>
    <td>PG0803</td>
    <td>^ 1" 黃風喉 PG0803<br>編號: CDX2378</td>
    <td>D22-77756</td>
    <td>3 卷</td>
    <td>840.00</td>
    <td>2,520.00</td>
  </tr>
</table>

收發票日期
28 DEC 2022
By: ____________

Total: HK$ 8,140.00

#### 输出：
{{
    "document_type": "invoice",
    "product_service": [
        {{
            "name": "DPC/GEN/22068/00 ~ 3/4\" 黃風喉 PG0801",
            "quantity": "3",
            "unit": "卷",
            "unit_price": "580.00",
            "amount": "1740.00"
        }},
        {{
            "name": "~ 1\" 黃風喉PG0803編號(CDX2324)",
            "quantity": "3",
            "unit": "卷",
            "unit_price": "840.00",
            "amount": "2520.00"
        }},
        {{
            "name": "^220V 1\" 1/8HP 鶴見牌 水泵Model: Family12(PG0401)編號: CDX2347",
            "quantity": "2",
            "unit": "台",
            "unit_price": "680.00",
            "amount": "1360.00"
        }},
        {{
            "name": "^ 1\" 黃風喉 PG0803編號: CDX2378",
            "quantity": "3",
            "unit": "卷",
            "unit_price": "840.00",
            "amount": "2520.00"
        }}
    ],
    "order_contact": [],
    "document_no": "H2239266",
    "invoice_date": "2022-12-28",
    "site_name": "中國建築工程(香港)有限公司(1511052-05) CDX 將軍澳海水化淡廠第一期(施工)",
    "currency": "HKD",                               
    "total_amount": "8140.00",
    "supplier": {{
        "supplier_id": "",
        "supplier_name": "Hoi Hing Building Materials Co. Limited",
        "address": "ROOM 306, 3/F., JOIN IN HANG SING CENTRE, 71-75 CONTAINER PORT ROAD, KWAI CHUNG, N.T., HONG KONG",
        "phone": "2388 0263, 2536 2900"
    }}
}}

## OCR识别文本：
{ocr_text}

## 必须遵循的JSON结构（字段名、层级、类型完全匹配）：
{{
  "document_type": "字符串（文件类型，固定为\"invoice\"）",
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
   - 日期字段统一转换为**yyyy-MM-dd**格式；
   - 时间字段统一转换为**yyyy-MM-dd HH:mm:ss**格式；
   - 金额/单价值：保留数字格式（含小数点，如12200.00）；
   - 名称/分类字段：保留**原文完整内容**（含括号内英文/编码，如將軍澳海水化淡廠第一階段(CDX)、安全環保用品(U01)）；
5. 业务字段映射：严格按建筑行业物资付款单定义提取，**字段值与单据业务含义完全匹配**（如site_name=地盘名称、vendor_name=客商名称）。

## 示例案例（帮助理解任务）
### 案例 1：
#### 输入：
中國建築工程(香港)有限公司
物資付款辦理單

地盤名稱： 將軍澳海水化淡廠第一階段(CDX)        材料分類： 小五金材料(M20)        制單日期： 2023年12月6日
客商名稱： 永新五金工程有限公司(WGS)        扣保固金比例： 0.00%        付辦單號： CDX/2312/A/0015
合約編號： DPC/GEN/23003/00        發票日期： 2023年12月4日        收發票日期： 2023年12月6日
幣種： 港元        是否代購： 否        付款方式： 支票        附單數： 4

<table>
  <tr>
    <th>項目</th>
    <th>合約總額</th>
    <th>上期累計</th>
    <th>本期發生</th>
    <th>本期累計</th>
    <th>超合約額比例</th>
  </tr>
  <tr>
    <td>DPC/GEN/23003總計</td>
    <td>0.00</td>
    <td>393,601.38</td>
    <td>19,216.00</td>
    <td>412,817.38</td>
    <td></td>
  </tr>
  <tr>
    <td rowspan="4">合約款</td>
    <td>材料款</td>
    <td>0.00</td>
    <td>393,601.38</td>
    <td>19,216.00</td>
    <td>412,817.38</td>
    <td>-</td>
  </tr>
  <tr>
    <td>費用</td>
    <td>0.00</td>
    <td>0.00</td>
    <td>0.00</td>
    <td>0.00</td>
    <td>-</td>
  </tr>
  <tr>
    <td>預付款</td>
    <td>-</td>
    <td>0.00</td>
    <td>0.00</td>
    <td>0.00</td>
    <td>-</td>
  </tr>
  <tr>
    <td>保固金</td>
    <td>-</td>
    <td>0.00</td>
    <td>0.00</td>
    <td>0.00</td>
    <td>-</td>
  </tr>
  <tr>
    <td>DPC/GEN/23003/0合計</td>
    <td>0.00</td>
    <td>393,601.38</td>
    <td>19,216.00</td>
    <td>412,817.38</td>
    <td>-</td>
  </tr>
</table>

<table>
  <tr>
    <th>材料名稱</th>
    <th>規格型號</th>
    <th>數量</th>
    <th>單價</th>
    <th>金額</th>
  </tr>
  <tr>
    <td>鐵咀大介刀(PJ3123)</td>
    <td></td>
    <td>12.000把</td>
    <td>6.000</td>
    <td>72.00</td>
  </tr>
  <tr>
    <td>普通電池(PL7004)</td>
    <td>AA，勁量牌，4粒/排</td>
    <td>10.000排</td>
    <td>12.650</td>
    <td>126.50</td>
  </tr>
  <tr>
    <td>普通電池(PL7005)</td>
    <td>AAA，勁量牌，4粒/排</td>
    <td>10.000排</td>
    <td>12.650</td>
    <td>126.50</td>
  </tr>
  <tr>
    <td>工具,小五金,零星電器(PR0100)</td>
    <td>大垃圾桶連蓋16"X17"X24"(45L)腳踏灰色</td>
    <td>4.000個</td>
    <td>180.000</td>
    <td>720.00</td>
  </tr>
  <tr>
    <td>工具,小五金,零星電器(PR0100)</td>
    <td>藥水膠布100片/盒</td>
    <td>2.000盒</td>
    <td>18.000</td>
    <td>36.00</td>
  </tr>
</table>

<table>
  <tr>
    <th>费用类型</th>
    <th>描述</th>
    <th>數量</th>
    <th>單價</th>
    <th>金額</th>
  </tr>
  <tr>
    <td></td>
    <td></td>
    <td>0.000</td>
    <td>0.000</td>
    <td>0.00</td>
  </tr>
</table>

<table>
  <tr>
    <th>發票號碼</th>
    <th>送貨單號</th>
    <th>發票號碼</th>
    <th>送貨單號</th>
  </tr>
  <tr>
    <td>23/005008，23/005012</td>
    <td></td>
    <td>D23/005008，D23/005012</td>
    <td></td>
  </tr>
</table>

備註：54010102

#### 输出：
{{
    "document_type": "receipts",
    "product_service": [
        {{
            "name": "鐵咀大介刀(PJ3123)",
            "specification": "",
            "unit": "把",
            "quantity": "12",
            "unit_price": "6.000",
            "amount": "72.00"
        }},
        {{
            "name": "普通電池(PL7004)",
            "specification": "AA，勁量牌，4粒/排",
            "unit": "排",
            "quantity": "10",
            "unit_price": "12.650",
            "amount": "126.50"
        }},
        {{
            "name": "普通電池(PL7005)",
            "specification": "AAA，勁量牌，4粒/排",
            "unit": "排",
            "quantity": "10",
            "unit_price": "12.650",
            "amount": "126.50"
        }},
        {{
            "name": "工具,小五金,零星電器(PR0100)",
            "specification": "大垃圾桶連蓋16\"X17\"X24\"(45L)腳踏灰色",
            "unit": "個",
            "quantity": "4",
            "unit_price": "180.000",
            "amount": "720.00"
        }},
        {{
            "name": "工具,小五金,零星電器(PR0100)",
            "specification": "藥水膠布100片/盒",
            "unit": "個",
            "quantity": "2",
            "unit_price": "18.000",
            "amount": "36.00"
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
    "currency": "港元",
    "delivery_note_no": "",
    "invoice_no": "23/005008，23/005012",
    "remarks": "54010102"
}}


## OCR识别的物资付款办理单文本：
{ocr_text}

## 强制遵循的JSON结构（字段名、层级、类型、业务含义完全匹配）
{{
  "document_type": "字符串（文件类型，固定为\"receipts\"）",
  "site_name": "字符串（地盘名称，如：將軍澳海水化淡廠第一階段(CDX)）",
  "material_category": "字符串（材料分类，如：安全環保用品(U01)）",
  "creation_date": "字符串（制单日期，如：2024-01-02）",
  "vendor_name": "字符串（客商名称，如：國際安全用品有限公司(ISEL)）",
  "payment_order_no": "字符串（付辦單號，如：CDX/2401/A/0001）",
  "contract_no": "字符串（合约编号，如：DPC/GEN/23033/00）",
  "invoice_date": "字符串（发票日期，如：2023-12-29）",
  "payment_method": "字符串（付款方式，如：支票）",
  "current_occurrence": "字符串（本期發生，如：12200.00）",
  "product_service": [
    {{
      "name": "字符串（材料名称，如：馬路欄河）",
      "specification": "字符串（规格型号，如：XC0302 2M (L)黃色/橙色）",
      "delivery_note_no": "字符串（送货单编号，如：SNT2312-0110）",
      "unit": "字符串（计量单位，如：個）",
      "quantity": 整数（产品数量，纯数字，如100）,
      "unit_price": "字符串（单价，如：122.000）",
      "amount": "字符串（金额，如：12200.00）",
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
   - 日期字段统一转换为**yyyy-MM-dd**格式；
   - 时间字段统一转换为**yyyy-MM-dd HH:mm:ss**格式；
   - 金额/单价值：保留数字格式（含小数点，如12200.00）；
3. 数据来源：仅从提供的OCR文本中提取，不编造、不猜测任何信息；
4. 格式适配：
   - 日期统一转换为yyyy-MM-dd格式（如"04 December, 2023"转换为"2023-12-04"）；
   - 币种保留原始文本（如HKD/人民币）；
   - 地址/名称保留中英文混合原始格式，不做翻译或修改。
   
## 示例案例（帮助理解任务）
### 案例 1：
#### 输入：
Delivery Note

ID：中國CDX / 4224
Customer 中國建築工程(香港)有限公司(海水化淡廠)
客戶：
Attention 卓生 Phone : 9138 2007
Reference DPC/GEN/23003 Fax : 3010 8232

Delivery Note # D23/005012
Date：04 December, 2023
Page：1 of 2
Salesperson CHOW

To：將軍澳海水化淡廠
Ship To：將軍澳海水化淡廠 137 堆填區，翠谷
卓生 9138 2007 / 林生 9215 3007 / 謝生 5962 9254

Delivery 04 December, 2023
Payment 月結
Currency HKD
Shipped FOB

<table>
  <tr>
    <th>#</th>
    <th>Description</th>
    <th>Quantity</th>
  </tr>
  <tr><td>001</td><td>維達三摺式抹手紙(16包/箱)</td><td>30 箱</td></tr>
  <tr><td>002</td><td>維達廁紙 藍色</td><td>60 條</td></tr>
  <tr><td>003</td><td>維達面紙(60盒/箱)</td><td>6 箱</td></tr>
  <tr><td>004</td><td>汽車香座香片</td><td>6 個</td></tr>
</table>

to be Continued

#### 输出：
{{
  "document_type": "delivery_note",
  "document_no": "D23/005012",
  "supplier": {{
    "supplier_id": "",
    "supplier_name": "",
    "address": "",
    "phone": ""
  }},
  "site_name": "將軍澳海水化淡廠",
  "delivery_date": "2023-12-04",
  "product_service": [
    {{
      "name": "維達三摺式抹手紙(16包/箱)",
      "specification": "",
      "unit": "箱",
      "quantity": 30,
      "unit_price": "",
      "amount": ""
    }},
    {{
      "name": "維達廁紙 藍色",
      "specification": "",
      "unit": "條",
      "quantity": 60,
      "unit_price": "",
      "amount": ""
    }},
    {{
      "name": "維達面紙(60盒/箱)",
      "specification": "",
      "unit": "箱",
      "quantity": 6,
      "unit_price": "",
      "amount": ""
    }},
    {{
      "name": "汽車香座香片",
      "specification": "",
      "unit": "個",
      "quantity": 6,
      "unit_price": "",
      "amount": ""
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
## 必须遵循的JSON结构（字段名、层级、类型完全匹配）：
{{
  "document_type": "字符串（文件类型，固定为\"delivery_note\"）",
  "document_no": "字符串（送貨單編號，如：D22-72035）",
  "supplier": {{
    "supplier_id": "字符串（供應商ID，如：未提供則留空）",
    "supplier_name": "字符串（供應商名稱，如：民光電器行 MAN KWONG ELECTRIC CO.）",
    "address": "字符串（供應商地址，如：九龍上海街269地下 G/F,269 SHANGHAI ST, KOWLOON, HONG KONG）",
    "phone": "字符串（供應商電話，如：23852973）"
  }},
  "site_name": "字符串（送貨單收取人，如：中國建築工程(香港)有限公司(1511052-05)CDX 將軍澳海水化淡廠第一期(施工)）",
  "delivery_date": "字符串（送貨單日期，如：30/11/2022）",
  "product_service": [
    {{
      "name": "字符串（產品名稱，如：大尼龍袋）",
      "specification": "字符串（產品規格，如：PB1013）",
      "unit": "字符串（計量單位，如：個）",
      "quantity": 整数（產品數量，如：6000）,
      "unit_price": "字符串（單價，如：未提供則留空）",
      "amount": "字符串（金額，如：未提供則留空）"
    }}
  ],
  "currency": "字符串（幣種，如：未提供則留空）",
  "total_amount": "字符串（送貨單總金額，如：未提供則留空）"
}}


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
地盤零星材料申請表
地盤名稱: 將軍澳海水化淡廠第一階段(CD)日期: 26-Jul-24 編號: CDX3784

<table>
  <tr>
    <th>序號</th>
    <th>材料名稱 & 規格</th>
    <th>單位</th>
    <th>數量</th>
    <th>進貨日期</th>
    <th>材料用途及使用位置</th>
    <th>合約編號</th>
    <th>項目</th>
  </tr>
  <tr>
    <td>1</td>
    <td>M10 x 70mm 拉爆螺絲 (@70粒/盒) PD3502</td>
    <td>盒</td>
    <td>2</td>
    <td></td>
    <td>地盤備用</td>
    <td>PD3502</td>
    <td>24001</td>
  </tr>
  <tr>
    <td>2</td>
    <td>M12 x 75mm 拉爆螺絲 (@40粒/盒) PD3505</td>
    <td>盒</td>
    <td>2</td>
    <td></td>
    <td>地盤備用</td>
    <td>PD3505</td>
    <td>24001</td>
  </tr>
  <tr>
    <td>3</td>
    <td>玻璃膠槍 PJ6902</td>
    <td>支</td>
    <td>5</td>
    <td></td>
    <td>地盤備用</td>
    <td>PJ6902</td>
    <td>24001</td>
  </tr>
</table>

地盤負責人: 孟 地盤內派/主管審核: 孫柏 製單人: 凡
申請人: 布國強

備 註: 定點名冊材料申請表必須由物料控制員填寫“合約編號”及“項目”兩欄。

<table>
  <tr>
    <th>煩請訂貨<br>聯絡人 : 卓生<br>電話 : 9138 2007<br>聯絡人: 林生<br>電話: 9215 3007<br>傳真 : 3010 8232<br>地盤收貨人: 馮生 電話:9249 9108</th>
  </tr>
</table>

#### 输出：
{{
    "document_type": "misc_materials_app",
    "product_service": [
        {{
            "name": "M10 x 70mm 拉爆螺絲 (@70粒/盒) PD3502",
            "specification": "M10 x 70mm",
            "unit": "盒",
            "quantity": "2",
            "contract_no": "PD3502"
        }},
        {{
            "name": "M12 x 75mm 拉爆螺絲 (@40粒/盒) PD3505",
            "specification": "M12 x 75mm",
            "unit": "盒",
            "quantity": "2",
            "contract_no": "PD3505"
        }},
        {{
            "name": "玻璃膠槍 PJ6902",
            "specification": "",
            "unit": "支",
            "quantity": "5",
            "contract_no": "PJ6902"
        }}
    ],
    "order_contact": [
        {{
            "name": "卓生",
            "phone": "9138 2007",
            "fax": null,
            "email": null
        }},
        {{
            "name": "林生",
            "phone": "9215 3007",
            "fax": "3010 8232",
            "email": null
        }}
    ],
    "document_no": "CDX3784",
    "site_name": "將軍澳海水化淡廠第一階段(CD)",
    "date": "2024-07-26",
    "order_creator": "凡",
    "applicant": "布國強",
    "site_receiver": {{
        "name": "馮生",
        "phone": "9249 9108"
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
   - 名称/编号/联系方式保留原始内容（含括号、符号、中英文），不做翻译或修改。
   - 日期字段统一转换为**yyyy-MM-dd**格式；
   - 时间字段统一转换为**yyyy-MM-dd HH:mm:ss**格式；
   - 金额/单价值：保留数字格式（含小数点，如12200.00）；
   
## 示例案例（帮助理解任务）
### 案例 1：
#### 输入：
iGTB 012-875-68-29941-5>工作列Work Queue >檔案指令報告File Instruction Report

檔案詳情 File Detail
檔案名稱File Name: Y2025121001.DAT
狀態 Status: 等候第一次授權Pending 1st Authorisation
指示類型Instruction Type: ACH 支付文件上載ACH Payment File Upload
最後跟進Last Action: 8 Dec 2025 12:42 GMT+08:00 by YEUNG SZE MAN
檔案參考號File Reference: F2534271682
iGTB參考號 iGTB Reference: 02121750335
更新於 Refreshed as at: 8 Dec 2025 12:43

交易詳情Transaction Detail
發起賬戶號碼Originating Account Number: 012-699-2-030055-3
生效日期 Effective Date: 2025/12/10
交易筆數 Transaction Count: 1
發起賬戶名稱Originating Account Name: CHINA STATE - STEC JOINT VENTURE
總金額 Total Amount: HKD 122206.00

<table>
  <tr>
    <th>編號 No.</th>
    <th>目標賬戶號碼 Destination A/C</th>
    <th>目標賬戶名稱 Destination A/C Name</th>
    <th>貨幣 Currency</th>
    <th>金額 Amount</th>
    <th>參考號 Reference</th>
    <th>備註 Remark</th>
  </tr>
  <tr>
    <td>1</td>
    <td>004111418042001</td>
    <td>Construction Industry Council</td>
    <td>HKD</td>
    <td>122206.00</td>
    <td>Y2025121001</td>
    <td>DN3418712</td>
  </tr>
</table>

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
            "destination_account_number": "004111418042001",
            "destination_account_name": "Construction Industry Council",
            "currency": "HKD",
            "amount": "122206.00",
            "reference": "Y2025121001",
            "remark": "DN3418712"
        }}
    ]
}}

### 案例 2：
#### 输入：
交易詳情

繳付賬單
• 檢查一次密碼

GTB卡號
02127063960

經辦人員
AGNES

交易日期和時間
2025年12月12日15:11 GMT+08:00

由*
CHINA STATE - STEC JOINT VENTURE
012499-2-020951-3
中國省港
美元/港幣帳戶

至*
環境保護號:
01-小額付款賬單,
035047011

支付金額
HKD 6,754.00

交易詳情
金額
支付金額*
HKD 6,754.00

支付時間表
支付狀態*
即時遞交

補充資料
內部支付備忘
035047011

客戶參考號
035047011

#### 输出：
{{
    "document_type": "transaction",
    "document_no": "",
    "document_name": "",
    "document_status": "",
    "igbt_reference": "02127063960",
    "originating_account_number": "012499-2-020951-3",
    "originating_account_name": "CHINA STATE - STEC JOINT VENTURE",
    "effective_date": "2025-12-12 15:11:00",
    "transaction_count": "",
    "currency": "HKD",
    "total_amount": "6754.00",
    "transactions": [
        {{
            "destination_account_number": "035047011",
            "destination_account_name": "環境保護號: 01-小額付款賬單",
            "currency": "HKD",
            "amount": "6754.00",
            "reference": "035047011",
            "remark": "035047011"
        }}
    ],
}}

### 案例 3：
#### 输入：
中國銀行(香港)有限公司
BANK OF CHINA (HONG KONG) LIMITED
灣仔中環海外大廈分行：香港灣仔軒尼詩道139號中環海外大廈地下C鋪
Wan Chai (China Overseas Building) Branch
Shop C, G/F, China Overseas Building, 139 Hennessy Road, Wan Chai, Hong Kong.

PAY 中華電力有限公司

港幣
H.K. DOLLARS 柒万叁仟叁佰柒拾肆元整

HK $73,374.00

CHINA STATE - STEC JOINT VENTURE

#### 输出：
{{
    "document_type": "transaction",
    "document_no": "",
    "document_name": "",
    "document_status": "",
    "igbt_reference": "",
    "originating_account_number": "",
    "originating_account_name": "CHINA STATE - STEC JOINT VENTURE",
    "effective_date": "",
    "transaction_count": "",
    "currency": "HKD",
    "total_amount": "73374.00",
    "transactions": [
        {{
            "destination_account_number": "",
            "destination_account_name": "中華電力有限公司",
            "currency": "HKD",
            "amount": "73374.00",
            "reference": "",
            "remark": ""
        }}
    ]
}}


## OCR识别的交易记录文本：
{ocr_text}

## 强制遵循的JSON结构（字段名、层级、类型完全匹配）
{{
  "document_type": "字符串（文件类型，固定为\"transaction\"）",
  "document_no": "字符串（文件编号，檔案參考號，如：F2534271682）",
  "document_name": "字符串（檔案名稱，如：Y2025121001.DAT）",
  "document_status": "字符串（狀態，如：等候第一次授權Pending 1st Authorisation）",
  "igbt_reference": "字符串（IGBT编号，如：02121750335）",
  "originating_account_number": "字符串（發起賬戶號碼，如：012-699-2-030055-3）",
  "originating_account_name": "字符串（發起賬戶名稱，如：CHINA STATE - STECJOINT VENTURE）",
  "effective_date": "字符串（生效日期，如：2025-12-10）",
  "transaction_count": "字符串（交易筆數，如：1）",
  "currency": "字符串（幣種，如：HKD）",
  "total_amount": "字符串（總金額，如：122206.00）",
  "cheque_number": "字符串（支票號碼）",
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

    print(f"Document type: {document_type}")

    # 获取对应的Prompt模板，如果类型不存在则使用发票模板作为默认值
    template = prompt_mapping.get(document_type, INVOICE_PROMPT)

    # 将OCR文本插入到Prompt模板中
    return template
