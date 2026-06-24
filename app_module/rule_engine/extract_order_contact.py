from bs4 import BeautifulSoup
from typing import List, Optional, Dict
import re


def extract_order_contact_to_dict_list(html_text: str) -> List[Dict[str, Optional[str]]]:
    """
    通用化提取联系人信息，最终输出字典数组（无Pydantic依赖，纯字典格式）
    :param html_text: 包含表格的OCR原始文本
    :return: 联系人字典数组，每个字典包含name/phone/fax/email字段
    """
    # ===================== 步骤1：提取包含联系人信息的表格单元格纯文本 =====================
    soup = BeautifulSoup(html_text, 'html.parser')
    cell_tags = soup.find_all(['th', 'td'])
    if not cell_tags:
        return []

    # 寻找包含联系人信息的单元格（包含關鍵詞：聯絡人、電話、傳真等）
    target_cell = None
    contact_keywords = ["聯絡人", "聯繫人", "联系人", "電話", "电话", "傳真", "传真"]

    for tag in cell_tags:
        cell_text = tag.get_text(strip=True)
        if any(keyword in cell_text for keyword in contact_keywords):
            target_cell = tag
            break

    if not target_cell:
        return []

    # 提取目标单元格文本：保留所有内容，仅将换行/换行标签转为空格
    cell_text = target_cell.get_text(separator=" ", strip=True)
    # 移除地盤收貨人相关的信息，避免误匹配
    cell_text = re.sub(r'地盤收貨人:[^<>:\n\r]*?(?:電話|电话|Phone|Tel)[:：]\s*[0-9\s\-]+', '', cell_text)
    # 仅清洗明显的冗余字符（如末尾无意义的"電""："等）
    cell_text = re.sub(r"[^\w\s@.:-]$", "", cell_text).strip()
    cell_text = re.sub(r"\s+", " ", cell_text)  # 合并连续空格

    # ===================== 步骤2：使用更精确的正则模式提取字段 =====================
    # 修复：允许电话和传真包含空格的数字
    name_pattern = r'(?:聯絡人|聯繫人|联系人|Contact|Name)[:：]\s*([^\s<>:：]+)'
    phone_pattern = r'(?:電話|电话|Phone|Tel)[:：]\s*([0-9\s\-]+)'
    fax_pattern = r'(?:傳真|传真|Fax)[:：]\s*([0-9\s\-]+)'  # 允许数字、空格、连字符
    email_pattern = r'(?:Email|E-mail|邮箱|電子郵箱)[:：]\s*([^\s<>]+)'  # 邮箱可能包含更多字符

    names = re.findall(name_pattern, cell_text)
    phones = re.findall(phone_pattern, cell_text)
    faxes = re.findall(fax_pattern, cell_text)
    emails = re.findall(email_pattern, cell_text)

    # 清理提取到的数据（去除多余空格并确保不为空）
    names = [name.strip() for name in names if name.strip()]
    phones = [phone.strip() for phone in phones if phone.strip()]
    faxes = [fax.strip() for fax in faxes if fax.strip()]
    emails = [email.strip() for email in emails if email.strip()]

    # ===================== 步骤3：整理为字典数组 =====================
    contact_dict_list = []
    max_count = max(len(names), len(phones))

    for i in range(max_count):
        contact_dict = {
            "order_contact_name": names[i] if i < len(names) else None,
            "order_contact_phone": phones[i] if i < len(phones) else None,
            "order_contact_fax": faxes[0] if faxes else None,  # 传真通常是共享的
            "order_contact_email": emails[0] if emails else None  # 邮箱通常是共享的
        }
        contact_dict_list.append(contact_dict)

    # 兜底：若只有传真/Email无联系人，也生成一个空姓名的字典
    if not contact_dict_list and (faxes or emails):
        contact_dict_list.append({
            "order_contact_name": None,
            "order_contact_phone": None,
            "order_contact_fax": faxes[0] if faxes else None,
            "order_contact_email": emails[0] if emails else None
        })

    return contact_dict_list



# ===================== 测试：验证字典数组输出 =====================
if __name__ == '__main__':
    # 测试文本（包含多联系人、灵活格式）
    test_html = """中國建築工程(香港)有限公司

地盤零星材料申請表
地盤名稱: 將軍澳海水化淡廠第一階段(CDX)　日期: 14-Dec-23　編號: CDX3424

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
    <td>馬路欄河 2M (L)橙白色 XC0302</td>
    <td>個</td>
    <td>100</td>
    <td></td>
    <td>地盤21/12水務署Event用</td>
    <td>23033</td>
    <td>XC0302</td>
  </tr>
</table>

地盤負責人: 　　地盤內派/主管審核: 　　製單人: Jimmy
申請人: Laurence Wong

備註: 定點名冊材料申請表必須由物料控制員填寫“合約編號”及“項目”兩欄。

<table>
  <tr>
    <th>煩請訂貨<br>聯絡人: 卓生<br>電話: 9138 2007<br>聯絡人: 林生<br>電話: 9215 3007<br>傳真: 3010 8232<br>地盤收貨人: 馮生 電</th>
  </tr>
</table>"""

#     test_html = """地盤零星材料申請表
# 地盤名稱: 將軍澳海水化淡廠第一階段(CDX)　日期: 15-Aug-23　編號: CDX3070
#
# <table>
#   <tr>
#     <th>序號</th>
#     <th>材料名稱 & 規格</th>
#     <th>單位</th>
#     <th>數量</th>
#     <th>進貨日期</th>
#     <th>材料用途及使用位置</th>
#     <th>合約編號</th>
#     <th>項目</th>
#   </tr>
#   <tr>
#     <td>1</td>
#     <td>Yota Safety RHJ600/A 個人安全警報器 MD2402</td>
#     <td>個</td>
#     <td>8</td>
#     <td></td>
#     <td>密閉空間</td>
#     <td>23029</td>
#     <td>MD2402</td>
#   </tr>
# </table>
#
# 地盤負責人: 費　　地盤內派/主管審核: 世　　製單人: Jimmy　　申請人: 安全Ken
#
# 備註: 定點名冊材料申請表必須由物料控制員填寫“合約編號”及“項目”兩欄。
#
# <table>
#   <tr>
#     <th colspan="2">煩請訂貨<br>聯絡人: 卓生<br>電話: 9138 2007<br>聯絡人: 林生<br>電話: 9215 3007<br>傳真: 3010 8232<br>地盤收貨人: 謝生 電話:59629254</th>
#   </tr>
# </table>"""

    # 提取字典数组
    contact_dict_list = extract_order_contact_to_dict_list(test_html)

    # 打印结果（标准字典数组）
    print("=== 最终输出：联系人字典数组 ===")
    print(f"类型：{type(contact_dict_list)}")
    print(f"长度：{len(contact_dict_list)}")
    print("\n详细内容：")
    for idx, contact in enumerate(contact_dict_list, 1):
        print(f"  联系人{idx}：{contact}")

    # 可选：转为JSON格式（便于传输/存储）
    import json

    json_result = json.dumps(contact_dict_list, ensure_ascii=False, indent=2)
    print("\nJSON格式输出：")
    print(json_result)