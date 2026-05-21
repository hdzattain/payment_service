import re
from dataclasses import dataclass
from typing import Any

from app_module.logger.logger_config import setup_logger

logger = setup_logger("document_type_recognizer")


@dataclass(frozen=True)
class _TextProfile:
    raw_text: str
    text_lower: str
    text_no_space: str
    text_lower_no_space: str
    lines: list[str]
    markdown_title_lines: list[str]
    markdown_title_lines_lower: list[str]
    markdown_title_lines_no_space: list[str]
    top_lines: list[str]
    top_text: str
    top_text_lower: str
    top_text_no_space: str
    top_text_lower_no_space: str


class DocumentTypeRecognizer:
    """基于强规则 + 打分式的票据类型识别器。"""

    MIN_SCORE = 8
    MIN_SCORE_GAP = 3

    RECEIPT_DETAIL_KEYWORDS = [
        "材料付办单附表－摘要明細",
        "材料付辦單附表－摘要明細",
        "材料付办单附表-摘要明細",
        "材料付辦單附表-摘要明細",
        "材料付办单附表－摘要明细",
        "材料付辦單附表－摘要明细",
        "材料付办单附表-摘要明细",
        "材料付辦單附表-摘要明细",
        "材料付办单附表摘要明細",
        "材料付辦單附表摘要明細",
        "材料付办单附表摘要明细",
        "材料付辦單附表摘要明细",
        "材料付款办理单附表－摘要明细",
        "材料付款办理单附表－摘要明細",
        "材料付款辦理單附表－摘要明細",
        "材料付款辦理單附表－摘要明细",
        "材料付款办理单附表-摘要明細",
        "材料付款辦理單附表-摘要明細",
        "材料付款辦理單附表-摘要明细",
        "材料付款办理单附表摘要明细",
        "材料付款办理单附表摘要明細",
        "材料付款辦理單附表摘要明細",
        "材料付款辦理單附表摘要明细",
    ]

    RECEIPTS_KEYWORDS = [
        "物資付款辦理單",
        "物资付款办理单",
        "物料付款辦理單",
        "物料付款办理单",
    ]

    DELIVERY_NOTE_KEYWORDS = [
        "delivery note",
        "delivery order",
        "送貨簽收單",
        "送貨單",
        "交貨單",
        "送货签收单",
        "送货单",
        "交货单",
    ]

    QUOTATION_KEYWORDS = ["quotation", "報價單", "报价单"]
    QUOTATION_NO_FIELD_KEYWORDS = ["quotation no", "quotation no."]
    QUOTATION_DATE_FIELD_KEYWORDS = ["quotation date", "quotation date."]
    RECEIPT_NO_PATTERNS = [
        re.compile(r"(?:收據|收据|receipt)\s*(?:no\.?|#)\s*([a-z0-9\-/]+)", re.IGNORECASE),
        re.compile(r"\bno\.?\s*([a-z0-9\-/]{3,})\b", re.IGNORECASE),
    ]

    MISC_MATERIALS_KEYWORDS = ["地盤零星材料申請表", "地盘零星材料申请表"]

    TRANSACTION_KEYWORDS = [
        "transaction record",
        "transaction detail",
        "轉帳記錄",
        "交易記錄",
        "交易詳情",
        "转账记录",
        "交易记录",
        "交易详情",
        "igbt",
        "祈付",
        "or order",
    ]

    RECEIPT_GENERIC_KEYWORDS = ["receipt", "收據", "收据"]
    INVOICE_KEYWORDS = ["invoice", "發票", "发票"]

    def recognize(self, ocr_text: str) -> dict[str, Any]:
        profile = self._build_text_profile(ocr_text)
        if not profile.raw_text.strip():
            return self._build_result("unknown", "empty", {}, ["empty text"])

        strong_result = self._match_strong_rules(profile)
        if strong_result is not None:
            return strong_result

        scores: dict[str, int] = {
            "receipt_detail": 0,
            "receipts": 0,
            "delivery_note": 0,
            "quotation": 0,
            "receipt": 0,
            "invoice": 0,
            "misc_materials_app": 0,
            "transaction": 0,
        }
        reasons: dict[str, list[str]] = {document_type: [] for document_type in scores}

        self._score_receipt_detail(profile, scores, reasons)
        self._score_receipts(profile, scores, reasons)
        self._score_delivery_note(profile, scores, reasons)
        self._score_quotation(profile, scores, reasons)
        self._score_receipt_generic(profile, scores, reasons)
        self._score_invoice(profile, scores, reasons)
        self._score_misc_materials(profile, scores, reasons)
        self._score_transaction(profile, scores, reasons)
        self._apply_conflict_penalties(profile, scores, reasons)

        return self._select_best_result(scores, reasons)

    def _build_text_profile(self, ocr_text: str) -> _TextProfile:
        raw_text = ocr_text or ""
        text_lower = raw_text.lower()
        text_no_space = re.sub(r"\s+", "", raw_text)
        text_lower_no_space = text_no_space.lower()
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        markdown_title_lines = [line for line in lines if line.lstrip().startswith("#")]
        markdown_title_lines_lower = [line.lower() for line in markdown_title_lines]
        markdown_title_lines_no_space = [re.sub(r"\s+", "", line) for line in markdown_title_lines]
        top_lines = lines[:25]
        top_text = "\n".join(top_lines)
        top_text_lower = top_text.lower()
        top_text_no_space = re.sub(r"\s+", "", top_text)
        top_text_lower_no_space = top_text_no_space.lower()
        return _TextProfile(
            raw_text=raw_text,
            text_lower=text_lower,
            text_no_space=text_no_space,
            text_lower_no_space=text_lower_no_space,
            lines=lines,
            markdown_title_lines=markdown_title_lines,
            markdown_title_lines_lower=markdown_title_lines_lower,
            markdown_title_lines_no_space=markdown_title_lines_no_space,
            top_lines=top_lines,
            top_text=top_text,
            top_text_lower=top_text_lower,
            top_text_no_space=top_text_no_space,
            top_text_lower_no_space=top_text_lower_no_space,
        )

    def _match_strong_rules(self, profile: _TextProfile) -> dict[str, Any] | None:
        if self._markdown_title_contains_any(profile, self.RECEIPT_DETAIL_KEYWORDS, ignore_case=False, ignore_space=True):
            return self._build_result(
                "receipt_detail",
                "strong_rule",
                {"receipt_detail": 100},
                ["matched receipt_detail markdown title"],
            )

        if self._markdown_title_contains_any(profile, self.RECEIPTS_KEYWORDS):
            return self._build_result(
                "receipts",
                "strong_rule",
                {"receipts": 100},
                ["matched receipts markdown title"],
            )

        if self._markdown_title_contains_any(profile, self.MISC_MATERIALS_KEYWORDS):
            return self._build_result(
                "misc_materials_app",
                "strong_rule",
                {"misc_materials_app": 100},
                ["matched misc materials markdown title"],
            )

        if self._markdown_title_contains_any(profile, ["quotation"], ignore_case=True) or self._markdown_title_contains_any(
            profile, ["報價單", "报价单"]
        ):
            return self._build_result(
                "quotation",
                "strong_rule",
                {"quotation": 100},
                ["matched quotation markdown title"],
            )

        if self._markdown_title_contains_any(profile, ["delivery note", "delivery order"], ignore_case=True) or self._markdown_title_contains_any(
            profile, ["送貨簽收單", "送貨單", "交貨單", "送货签收单", "送货单", "交货单"]
        ):
            return self._build_result(
                "delivery_note",
                "strong_rule",
                {"delivery_note": 100},
                ["matched delivery note markdown title"],
            )

        if self._markdown_title_contains_any(profile, self.INVOICE_KEYWORDS, ignore_case=True):
            return self._build_result(
                "invoice",
                "strong_rule",
                {"invoice": 100},
                ["matched invoice keyword in markdown title"],
            )

        if self._markdown_title_contains_any(profile, ["transaction record", "transaction detail", "igbt"], ignore_case=True) or self._markdown_title_contains_any(
            profile, ["轉帳記錄", "交易記錄", "交易詳情", "转账记录", "交易记录", "交易详情", "祈付"]
        ):
            return self._build_result(
                "transaction",
                "strong_rule",
                {"transaction": 100},
                ["matched transaction markdown title"],
            )

        if any(keyword in profile.text_no_space for keyword in self.RECEIPT_DETAIL_KEYWORDS):
            return self._build_result(
                "receipt_detail",
                "strong_rule",
                {"receipt_detail": 100},
                ["matched receipt_detail title keyword"],
            )

        if any(keyword in profile.top_text for keyword in self.RECEIPTS_KEYWORDS) or any(
            keyword in profile.raw_text for keyword in self.RECEIPTS_KEYWORDS
        ):
            return self._build_result(
                "receipts",
                "strong_rule",
                {"receipts": 100},
                ["matched receipts title keyword"],
            )

        if any(keyword in profile.top_text for keyword in self.MISC_MATERIALS_KEYWORDS):
            return self._build_result(
                "misc_materials_app",
                "strong_rule",
                {"misc_materials_app": 100},
                ["matched misc materials title keyword"],
            )

        if any(keyword in profile.top_text_lower for keyword in ("quotation",)) or any(
            keyword in profile.top_text for keyword in ("報價單", "报价单")
        ):
            return self._build_result(
                "quotation",
                "strong_rule",
                {"quotation": 100},
                ["matched quotation title keyword"],
            )

        quotation_field_signals = self._count_quotation_field_signals(profile)
        if quotation_field_signals >= 2:
            return self._build_result(
                "quotation",
                "strong_rule",
                {"quotation": 100},
                ["matched quotation no/date fields"],
            )

        if self._contains_any(profile.top_text_lower, ["receipt"]) or any(keyword in profile.top_text for keyword in ("收據", "收据")):
            return self._build_result(
                "receipt",
                "strong_rule",
                {"receipt": 100},
                ["matched receipt title keyword in top area"],
            )

        if self._has_delivery_note_title(profile):
            return self._build_result(
                "delivery_note",
                "strong_rule",
                {"delivery_note": 100},
                ["matched delivery note title keyword"],
            )

        invoice_signals = 0
        invoice_reasons: list[str] = []
        if self._markdown_title_contains_any(profile, self.INVOICE_KEYWORDS, ignore_case=True):
            invoice_signals += 2
            invoice_reasons.append("matched invoice keyword in markdown title")
        if self._contains_any(profile.top_text_lower, ["invoice no", "invoice no."]):
            invoice_signals += 1
            invoice_reasons.append("matched invoice no field")
        if "invoice date" in profile.top_text_lower:
            invoice_signals += 1
            invoice_reasons.append("matched invoice date field")
        if "bill to" in profile.top_text_lower:
            invoice_signals += 1
            invoice_reasons.append("matched bill to field")
        if invoice_signals >= 2:
            return self._build_result(
                "invoice",
                "strong_rule",
                {"invoice": 100},
                invoice_reasons,
            )

        if self._contains_any(profile.top_text_lower, ["transaction record", "transaction detail", "igbt"]) or any(
            keyword in profile.top_text for keyword in ("轉帳記錄", "交易記錄", "交易詳情", "转账记录", "交易记录", "交易详情", "祈付")
        ):
            return self._build_result(
                "transaction",
                "strong_rule",
                {"transaction": 100},
                ["matched transaction title keyword"],
            )

        return None

    def _score_receipt_detail(self, profile: _TextProfile, scores: dict[str, int], reasons: dict[str, list[str]]) -> None:
        if not self._text_contains_any(profile, self.RECEIPT_DETAIL_KEYWORDS, ignore_space=True):
            return

        if self._contains_any(profile.text_lower_no_space, ["摘要明細", "摘要明细"]):
            scores["receipt_detail"] += 4
            reasons["receipt_detail"].append("matched detail summary wording")
        detail_table_hits = sum(
            1 for keyword in ["費用類型", "费用类型", "描述", "數量", "数量", "單價", "单价", "金額", "金额"]
            if keyword in profile.raw_text
        )
        if detail_table_hits >= 4:
            scores["receipt_detail"] += 8
            reasons["receipt_detail"].append("matched receipt_detail table structure")

    def _score_receipts(self, profile: _TextProfile, scores: dict[str, int], reasons: dict[str, list[str]]) -> None:
        if not self._text_contains_any(profile, self.RECEIPTS_KEYWORDS):
            return

        hits = sum(1 for keyword in self.RECEIPTS_KEYWORDS if keyword in profile.raw_text)
        if hits:
            scores["receipts"] += hits * 20
            reasons["receipts"].append("matched receipts title wording")
        field_hits = sum(
            1 for keyword in ["payment method", "invoice no", "delivery note no", "remarks", "contract no"]
            if keyword in profile.text_lower
        )
        if field_hits >= 2:
            scores["receipts"] += 6
            reasons["receipts"].append("matched receipts-like business fields")

    def _score_delivery_note(self, profile: _TextProfile, scores: dict[str, int], reasons: dict[str, list[str]]) -> None:
        if not self._text_contains_any(profile, self.DELIVERY_NOTE_KEYWORDS, ignore_case=True):
            return

        hits = sum(1 for keyword in self.DELIVERY_NOTE_KEYWORDS if keyword in profile.text_lower or keyword in profile.raw_text)
        if hits:
            scores["delivery_note"] += hits * 8
            reasons["delivery_note"].append("matched delivery note keywords")

    def _score_quotation(self, profile: _TextProfile, scores: dict[str, int], reasons: dict[str, list[str]]) -> None:
        if not self._text_contains_any(profile, self.QUOTATION_KEYWORDS, ignore_case=True):
            return

        hits = sum(1 for keyword in self.QUOTATION_KEYWORDS if keyword in profile.text_lower or keyword in profile.raw_text)
        if hits:
            scores["quotation"] += hits * 8
            reasons["quotation"].append("matched quotation keywords")

        quotation_field_signals = self._count_quotation_field_signals(profile)
        if quotation_field_signals:
            scores["quotation"] += quotation_field_signals * 12
            reasons["quotation"].append("matched quotation no/date fields")

    def _score_receipt_generic(self, profile: _TextProfile, scores: dict[str, int], reasons: dict[str, list[str]]) -> None:
        if not self._text_contains_any(profile, self.RECEIPT_GENERIC_KEYWORDS, ignore_case=True):
            return

        hits = sum(1 for keyword in self.RECEIPT_GENERIC_KEYWORDS if keyword in profile.text_lower or keyword in profile.raw_text)
        if hits:
            scores["receipt"] += min(hits, 2) * 3
            reasons["receipt"].append("matched generic receipt wording")

        receipt_field_signals = self._count_receipt_field_signals(profile)
        if receipt_field_signals:
            scores["receipt"] += receipt_field_signals * 4
            reasons["receipt"].append("matched receipt business fields")

    def _score_invoice(self, profile: _TextProfile, scores: dict[str, int], reasons: dict[str, list[str]]) -> None:
        if not self._text_contains_any(profile, self.INVOICE_KEYWORDS, ignore_case=True):
            return

        if self._markdown_title_contains_any(profile, self.INVOICE_KEYWORDS, ignore_case=True):
            scores["invoice"] += 30
            reasons["invoice"].append("matched invoice keyword in markdown title")
        if self._contains_any(profile.text_lower, ["invoice no", "invoice no."]):
            scores["invoice"] += 12
            reasons["invoice"].append("matched invoice no")
        if "invoice date" in profile.text_lower:
            scores["invoice"] += 10
            reasons["invoice"].append("matched invoice date")
        if "bill to" in profile.text_lower:
            scores["invoice"] += 8
            reasons["invoice"].append("matched bill to")
        if "deliver to" in profile.text_lower:
            scores["invoice"] += 6
            reasons["invoice"].append("matched deliver to")
        invoice_table_hits = sum(
            1 for keyword in ["description", "qty", "unit rate", "amount", "total"] if keyword in profile.text_lower
        )
        if invoice_table_hits >= 3:
            scores["invoice"] += 8
            reasons["invoice"].append("matched invoice table structure")

    def _score_misc_materials(self, profile: _TextProfile, scores: dict[str, int], reasons: dict[str, list[str]]) -> None:
        if not self._text_contains_any(profile, self.MISC_MATERIALS_KEYWORDS):
            return

        hits = sum(1 for keyword in self.MISC_MATERIALS_KEYWORDS if keyword in profile.raw_text)
        if hits:
            scores["misc_materials_app"] += hits * 15
            reasons["misc_materials_app"].append("matched misc materials keywords")

    def _score_transaction(self, profile: _TextProfile, scores: dict[str, int], reasons: dict[str, list[str]]) -> None:
        if not self._text_contains_any(profile, self.TRANSACTION_KEYWORDS, ignore_case=True):
            return

        hits = sum(1 for keyword in self.TRANSACTION_KEYWORDS if keyword in profile.text_lower or keyword in profile.raw_text)
        if hits:
            scores["transaction"] += hits * 8
            reasons["transaction"].append("matched transaction keywords")

    def _apply_conflict_penalties(self, profile: _TextProfile, scores: dict[str, int], reasons: dict[str, list[str]]) -> None:
        invoice_signals = sum(
            1 for condition in [
                self._markdown_title_contains_any(profile, self.INVOICE_KEYWORDS, ignore_case=True),
                self._contains_any(profile.text_lower, ["invoice no", "invoice no."]),
                "invoice date" in profile.text_lower,
                "bill to" in profile.text_lower,
            ] if condition
        )
        if invoice_signals >= 2:
            scores["receipt"] -= 4
            scores["receipts"] -= 3
            reasons["invoice"].append("penalized receipt-like candidates by invoice signals")

        if any(keyword in profile.raw_text for keyword in self.RECEIPTS_KEYWORDS):
            scores["invoice"] -= 6
            scores["receipt"] -= 2
            reasons["receipts"].append("penalized invoice by receipts title")

        if any(keyword in profile.text_no_space for keyword in self.RECEIPT_DETAIL_KEYWORDS):
            scores["invoice"] -= 8
            scores["receipt"] -= 4
            reasons["receipt_detail"].append("penalized non-detail candidates by receipt_detail title")

        quotation_field_signals = self._count_quotation_field_signals(profile)
        if quotation_field_signals >= 2:
            scores["invoice"] -= 6
            scores["receipt"] -= 3
            scores["receipts"] -= 3
            reasons["quotation"].append("penalized non-quotation candidates by quotation no/date fields")

        if any(keyword in profile.raw_text for keyword in self.RECEIPTS_KEYWORDS):
            scores["receipt"] -= 4
            reasons["receipts"].append("penalized generic receipt by receipts title")

    def _select_best_result(self, scores: dict[str, int], reasons: dict[str, list[str]]) -> dict[str, Any]:
        ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        best_type, best_score = ranked[0]
        second_score = ranked[1][1] if len(ranked) > 1 else 0

        if best_score < self.MIN_SCORE:
            return self._build_result("unknown", "score", scores, ["no document type reached score threshold"])

        if best_score - second_score < self.MIN_SCORE_GAP:
            return self._build_result(
                "unknown",
                "score",
                scores,
                [f"top score gap too small: best={best_score}, second={second_score}"],
            )

        return self._build_result(best_type, "score", scores, reasons.get(best_type, []))

    def _has_delivery_note_title(self, profile: _TextProfile) -> bool:
        return self._contains_any(profile.top_text_lower, ["delivery note", "delivery order"]) or any(
            keyword in profile.top_text for keyword in ["送貨簽收單", "送貨單", "交貨單", "送货签收单", "送货单", "交货单"]
        )

    def _count_quotation_field_signals(self, profile: _TextProfile) -> int:
        signal_count = 0
        if self._contains_any(profile.top_text_lower, self.QUOTATION_NO_FIELD_KEYWORDS):
            signal_count += 1
        if self._contains_any(profile.top_text_lower, self.QUOTATION_DATE_FIELD_KEYWORDS):
            signal_count += 1
        return signal_count

    def _count_receipt_field_signals(self, profile: _TextProfile) -> int:
        signal_count = 0
        if any(pattern.search(profile.top_text_lower) for pattern in self.RECEIPT_NO_PATTERNS):
            signal_count += 1
        if any(keyword in profile.top_text for keyword in ("日期",)):
            signal_count += 1
        if any(keyword in profile.top_text for keyword in ("提單號碼", "提单号码")):
            signal_count += 1
        if any(keyword in profile.top_text for keyword in ("車牌", "车牌")):
            signal_count += 1
        if any(keyword in profile.top_text for keyword in ("貨品", "货品")):
            signal_count += 1
        if any(keyword in profile.top_text for keyword in ("客戶", "客户")):
            signal_count += 1
        return signal_count

    @staticmethod
    def _text_contains_any(
        profile: _TextProfile,
        keywords: list[str],
        *,
        ignore_case: bool = False,
        ignore_space: bool = False,
    ) -> bool:
        if ignore_space:
            text = profile.text_no_space
            candidate_keywords = [re.sub(r"\s+", "", keyword) for keyword in keywords]
            if ignore_case:
                text = text.lower()
                candidate_keywords = [keyword.lower() for keyword in candidate_keywords]
        elif ignore_case:
            text = profile.text_lower
            candidate_keywords = [keyword.lower() for keyword in keywords]
        else:
            text = profile.raw_text
            candidate_keywords = keywords

        return any(keyword in text for keyword in candidate_keywords)

    @staticmethod
    def _markdown_title_contains_any(
        profile: _TextProfile,
        keywords: list[str],
        *,
        ignore_case: bool = False,
        ignore_space: bool = False,
    ) -> bool:
        if ignore_space:
            title_lines = profile.markdown_title_lines_no_space
            candidate_keywords = [re.sub(r"\s+", "", keyword) for keyword in keywords]
            if ignore_case:
                title_lines = [line.lower() for line in title_lines]
                candidate_keywords = [keyword.lower() for keyword in candidate_keywords]
        elif ignore_case:
            title_lines = profile.markdown_title_lines_lower
            candidate_keywords = [keyword.lower() for keyword in keywords]
        else:
            title_lines = profile.markdown_title_lines
            candidate_keywords = keywords

        return any(keyword in line for line in title_lines for keyword in candidate_keywords)

    @staticmethod
    def _contains_any(text: str, keywords: list[str]) -> bool:
        return any(keyword in text for keyword in keywords)

    @staticmethod
    def _build_result(document_type: str, matched_by: str, scores: dict[str, int], reasons: list[str]) -> dict[str, Any]:
        result = {
            "document_type": document_type,
            "matched_by": matched_by,
            "scores": scores,
            "reasons": reasons,
        }
        logger.info(f"票据类型识别结果: {result}")
        return result


document_type_recognizer = DocumentTypeRecognizer()


