import json
from pathlib import Path

class CC3DAdvancedGenerator:
    def __init__(self, registry):
        self.registry = registry
        # 获取最新的 rules
        self.rules = registry.rules 

    def generate(self):
        code = [
            "from cc3d.core.PySteppables import *",
            "from cc3d_builder.engine.core.model_registry import MODEL_REGISTRY",
            "from cc3d_builder.engine.core.condition_evaluator import evaluate_condition",
            "import json\n",
            "# 🚀 HIGH-PERFORMANCE COMPILED STEPPABLE",
            "class CompiledRuleSteppable(SteppableBasePy):",
            "    def step(self, mcs):"
        ]

        # 遍历所有 Rule 并编译
        for rule in self.rules:
            code.append(self._compile_rule(rule))

        return "\n".join(code)

    def _compile_rule(self, rule):
        r_id = rule.get('id', 'unknown')
        behaviour = rule.get('behaviour')
        target_type = rule.get('target', 'All').upper()
        
        indent = "        "
        rule_lines = [f"\n{indent}# --- Rule: {r_id} ---"]
        
        # 编译循环头部
        if target_type == "ALL":
            rule_lines.append(f"{indent}for cell in self.cell_list:")
        else:
            rule_lines.append(f"{indent}for cell in self.cell_list_by_type(self.{target_type}):")
        
        curr_indent = indent + "    "

        # 编译每一个 Case
        for i, case in enumerate(rule.get('cases', [])):
            when_block = case.get('when', {})
            apply_block = case.get('apply', {})
            
            # 1. 编译条件 (Condition)
            # 这里我们依然可以调用 evaluate_condition，但我们传入的是预解析的 JSON
            cond_json = json.dumps(when_block)
            rule_lines.append(f"{curr_indent}if evaluate_condition({cond_json}, cell, self):")
            
            # 2. 编译行为逻辑 (Behaviour Logic)
            exec_indent = curr_indent + "    "
            if behaviour == "growth":
                # 模拟你的 growth_plugin.py 逻辑，但跳过 cell.dict 中转
                model_name = apply_block.get("model")
                apply_json = json.dumps(apply_block)
                
                rule_lines.append(f"{exec_indent}# Direct Growth Application")
                rule_lines.append(f"{exec_indent}params = {apply_json}")
                rule_lines.append(f"{exec_indent}model_fn = MODEL_REGISTRY.get('{model_name}')")
                rule_lines.append(f"{exec_indent}if model_fn:")
                rule_lines.append(f"{exec_indent}    cell.targetVolume += model_fn(params, cell, self)")
            
            elif behaviour == "differentiate":
                to_type = apply_block.get("to_type", "Medium").upper()
                rule_lines.append(f"{exec_indent}cell.type = self.{to_type}")

        return "\n".join(rule_lines)

    def save_to_file(self, output_dir):
        path = Path(output_dir) / "CompiledSteppable.py"
        path.write_text(self.generate(), encoding='utf-8')
        return path