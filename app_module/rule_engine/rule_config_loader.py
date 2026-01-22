import json

from app_module.rule_engine.ocr_rule_engine import RuleEngine, ExtractionRule


class RuleConfigurationLoader:
    """规则配置加载器"""

    def __init__(self, rule_engine: RuleEngine):
        self.rule_engine = rule_engine

    def load_from_json(self, config_path: str):
        """从JSON文件加载规则配置"""
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)

        for doc_type, fields in config_data.items():
            for field_name, rules_config in fields.items():
                for rule_config in rules_config:
                    # 创建 ExtractionRule 对象
                    rule = ExtractionRule(
                        field_name=field_name,
                        rule_type=rule_config['rule_type'],
                        patterns=rule_config['patterns'],
                        weight=rule_config.get('weight', 1.0),
                        confidence_threshold=rule_config.get('confidence_threshold', 0.5)
                    )
                    # 添加规则到引擎
                    self.rule_engine.add_rule(doc_type, field_name, rule)

    def load_from_dict(self, config_dict: dict):
        """从字典加载规则配置"""
        for doc_type, fields in config_dict.items():
            for field_name, rules_config in fields.items():
                for rule_config in rules_config:
                    rule = ExtractionRule(
                        field_name=field_name,
                        rule_type=rule_config['rule_type'],
                        patterns=rule_config['patterns'],
                        weight=rule_config.get('weight', 1.0),
                        confidence_threshold=rule_config.get('confidence_threshold', 0.5)
                    )
                    self.rule_engine.add_rule(doc_type, field_name, rule)
