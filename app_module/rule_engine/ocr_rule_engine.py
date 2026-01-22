import re
from dataclasses import dataclass
from typing import Dict, List, Any, Optional

from bs4 import BeautifulSoup

from app_module.logger.logger_config import setup_logger

# 初始化日志记录器
logger = setup_logger("ocr_rule_engine")


@dataclass
class ExtractionRule:
    """提取规则定义"""
    field_name: str
    rule_type: str  # 'regex', 'css_selector', 'html_table'
    patterns: List[Dict[str, Any]]
    weight: float = 1.0
    validator: Optional[callable] = None
    confidence_threshold: float = 0.5


@dataclass
class ConfidenceResult:
    """置信度结果"""
    value: Any
    confidence: float
    rule_used: str


class RuleEngine:
    """规则引擎主类"""

    def __init__(self):
        self.rules: Dict[str, Dict[str, List[ExtractionRule]]] = {}
        self.soup: Optional[BeautifulSoup] = None
        self.ocr_text: str = ""

    def add_rule(self, doc_type: str, field_name: str, rule: ExtractionRule):
        """添加提取规则"""
        if doc_type not in self.rules:
            self.rules[doc_type] = {}
        if field_name not in self.rules[doc_type]:
            self.rules[doc_type][field_name] = []
        self.rules[doc_type][field_name].append(rule)

    def set_context(self, ocr_text: str):
        """设置OCR文本上下文"""
        self.ocr_text = re.sub(r'<br\s*/?>', '\n', ocr_text, flags=re.IGNORECASE)
        self.soup = BeautifulSoup(ocr_text, 'html.parser')

    def extract_fields(self, doc_type: str) -> Dict[str, Any]:
        """根据规则提取字段"""
        if doc_type not in self.rules:
            return {}

        results = {}
        for field_name, rules in self.rules[doc_type].items():
            best_result = self._apply_rules(field_name, rules)
            if best_result:
                results[field_name] = best_result.value

        return results

    def _apply_rules(self, field_name: str, rules: List[ExtractionRule]) -> Optional[ConfidenceResult]:
        """应用多个规则，返回最佳结果"""
        confidence_results = []

        for rule in rules:
            result = self._apply_single_rule(rule)
            if result:
                confidence_results.append(result)

        # 根据置信度排序，返回最佳结果
        if confidence_results:
            best_result = max(confidence_results, key=lambda x: x.confidence)
            return best_result if best_result.confidence >= min(r.confidence_threshold for r in rules) else None

        return None

    def _apply_single_rule(self, rule: ExtractionRule) -> Optional[ConfidenceResult]:
        """应用单个规则"""
        if rule.rule_type == 'regex':
            return self._apply_regex_rule(rule)
        elif rule.rule_type == 'css_selector':
            return self._apply_css_selector_rule(rule)
        elif rule.rule_type == 'html_table':
            return self._apply_html_table_rule(rule)
        elif rule.rule_type == 'html_table_column':
            return self._apply_html_table_column_rule(rule)
        else:
            logger.warning(f"未知的规则类型: {rule.rule_type}")
            return None

    def _apply_regex_rule(self, rule: ExtractionRule) -> Optional[ConfidenceResult]:
        """应用正则表达式规则"""
        for pattern_info in rule.patterns:
            pattern = pattern_info['value']
            flags = pattern_info.get('flags', 0)
            mapping = pattern_info.get('mapping', None)

            matches = re.findall(pattern, self.ocr_text, flags)
            if matches:
                # 如果有mapping配置，使用映射来构建结果
                if mapping:
                    value = self._build_mapped_value(matches[0], mapping)
                else:
                    # 计算置信度：基于匹配长度、正则复杂度等
                    value = matches[0] if isinstance(matches[0], str) else matches[0][0]
                    if isinstance(value, tuple):
                        value = value[0] if value else None

                if value is not None:
                    confidence = self._calculate_regex_confidence(pattern, matches)

                    # 验证结果
                    if rule.validator and not rule.validator(value):
                        continue

                    return ConfidenceResult(
                        value=value,
                        confidence=min(confidence * rule.weight, 1.0),
                        rule_used=pattern
                    )
        return None

    def _build_mapped_value(self, match_groups, mapping: Dict[str, Any]) -> Any:
        """根据映射配置构建返回值"""
        if isinstance(match_groups, str):
            # 如果匹配结果是字符串而不是元组，直接返回
            return match_groups.strip() if match_groups else None

        result = {}
        for field_name, indices in mapping.items():
            if indices is None:
                # 如果映射值为null，该字段设为None
                result[field_name] = None
            elif isinstance(indices, int):
                # 单个索引 - 需要考虑正则捕获组索引与Python元组索引的差异
                # 正则表达式捕获组从1开始，Python元组从0开始
                tuple_index = indices - 1  # 转换为Python元组索引
                if 0 <= tuple_index < len(match_groups):
                    value = match_groups[tuple_index]
                    result[field_name] = value.strip() if isinstance(value, str) else value
            elif isinstance(indices, list):
                # 多个索引，通常用于复合字段
                values = []
                for idx in indices:
                    tuple_index = idx - 1  # 转换为Python元组索引
                    if 0 <= tuple_index < len(match_groups):
                        value = match_groups[tuple_index]
                        values.append(value.strip() if isinstance(value, str) else value)
                # 如果只有一个值，直接返回该值；否则返回列表
                result[field_name] = values[0] if len(values) == 1 else values

        return result

    def _apply_css_selector_rule(self, rule: ExtractionRule) -> Optional[ConfidenceResult]:
        """应用CSS选择器规则"""
        for pattern_info in rule.patterns:
            selector = pattern_info['value']
            elements = self.soup.select(selector)

            if elements:
                values = [elem.get_text(strip=True) for elem in elements]
                value = values[0] if len(values) == 1 else values

                confidence = self._calculate_css_confidence(selector, elements)

                if rule.validator and not rule.validator(value):
                    continue

                return ConfidenceResult(
                    value=value,
                    confidence=min(confidence * rule.weight, 1.0),
                    rule_used=selector
                )
        return None

    def _apply_html_table_rule(self, rule: ExtractionRule) -> Optional[ConfidenceResult]:
        """应用HTML表格规则"""
        for pattern_info in rule.patterns:
            table_selector = pattern_info.get('selector', 'table')
            mapping = pattern_info.get('mapping', {})

            table = self.soup.select_one(table_selector)
            if table:
                data = self._extract_table_data(table, mapping)

                if data:
                    confidence = self._calculate_table_confidence(table, data)

                    if rule.validator and not rule.validator(data):
                        continue

                    return ConfidenceResult(
                        value=data,
                        confidence=min(confidence * rule.weight, 1.0),
                        rule_used=table_selector
                    )
        return None

    def _extract_table_data(self, table, mapping: Dict[str, List[str]]) -> List[Dict[str, str]]:
        """从HTML表格提取数据"""
        rows = table.find_all('tr')
        if not rows:
            return []

        # 获取表头
        header_cells = rows[0].find_all(['th', 'td'])
        headers = [cell.get_text(strip=True) for cell in header_cells]

        # 映射表头到字段名
        field_mapping = {}
        for field_name, possible_headers in mapping.items():
            for i, header in enumerate(headers):
                if any(possible_header in header for possible_header in possible_headers):
                    field_mapping[i] = field_name
                    break

        # 提取数据行
        data_rows = []
        for row in rows[1:]:
            cells = [cell.get_text(strip=True) for cell in row.find_all(['td', 'th'])]
            if len(cells) >= len(headers):
                row_data = {}
                for idx, field_name in field_mapping.items():
                    if idx < len(cells):
                        row_data[field_name] = cells[idx]
                if row_data:  # 只添加非空行
                    data_rows.append(row_data)

        return data_rows

    def _apply_html_table_column_rule(self, rule: ExtractionRule) -> Optional[ConfidenceResult]:
        """应用HTML表格列规则 - 提取特定表头对应的列值"""
        for pattern_info in rule.patterns:
            table_selector = pattern_info.get('selector', 'table')
            header_name = pattern_info.get('header')  # 目标表头名称
            row_index = pattern_info.get('row_index', 0)  # 目标数据行索引，默认第1行

            if not header_name:
                continue

            table = self.soup.select_one(table_selector)
            if table:
                # 从表格中提取指定表头对应的列值
                value = self._extract_table_column_value(table, header_name, row_index)

                if value is not None:
                    confidence = self._calculate_table_column_confidence(table, value)

                    if rule.validator and not rule.validator(value):
                        continue

                    return ConfidenceResult(
                        value=value,
                        confidence=min(confidence * rule.weight, 1.0),
                        rule_used=f"{table_selector}[{header_name}]"
                    )
        return None

    def _extract_table_column_value(self, table, target_header: str, row_index: int = 0) -> Optional[str]:
        """从表格中提取指定表头对应的列值"""
        rows = table.find_all('tr')
        if not rows:
            return None

        # 获取表头行
        header_row = rows[0]
        header_cells = header_row.find_all(['th', 'td'])
        headers = [cell.get_text(strip=True) for cell in header_cells]

        # 查找目标表头的列索引
        target_col_index = None
        for i, header in enumerate(headers):
            if target_header in header:
                target_col_index = i
                break

        if target_col_index is None:
            return None

        # 在数据行中获取对应列的值
        if len(rows) > row_index + 1:  # +1 因为第0行是表头
            data_row = rows[row_index + 1]
            data_cells = data_row.find_all(['td', 'th'])

            if len(data_cells) > target_col_index:
                return data_cells[target_col_index].get_text(strip=True)

        return None

    def _calculate_regex_confidence(self, pattern: str, matches: List) -> float:
        """计算正则匹配的置信度"""
        # 基础置信度
        base_confidence = 0.7

        # 根据正则复杂度调整
        if '(' in pattern and ')' in pattern:  # 有捕获组
            base_confidence += 0.2
        if '[+*?]' in pattern:  # 有量词
            base_confidence += 0.1

        # 根据匹配数量调整
        if len(matches) == 1:
            base_confidence += 0.1
        elif len(matches) > 1:
            base_confidence -= 0.1  # 多个匹配可能不够精确

        return min(base_confidence, 1.0)

    def _calculate_css_confidence(self, selector: str, elements: List) -> float:
        """计算CSS选择器的置信度"""
        base_confidence = 0.7
        if len(elements) == 1:
            base_confidence += 0.2
        elif len(elements) > 1:
            base_confidence += 0.1
        return min(base_confidence, 1.0)

    def _calculate_table_confidence(self, table, data: List[Dict]) -> float:
        """计算表格提取的置信度"""
        base_confidence = 0.8
        if data:
            base_confidence += min(len(data) * 0.05, 0.2)  # 数据行数越多置信度越高
        return min(base_confidence, 1.0)

    def _calculate_table_column_confidence(self, table, value: str) -> float:
        """计算表格列提取的置信度"""
        base_confidence = 0.8
        if value:
            base_confidence += 0.1  # 成功提取到值
        return min(base_confidence, 1.0)
