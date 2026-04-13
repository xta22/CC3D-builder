import operator
import sys

# 强行将 RuleEngine 所在的绝对路径塞入 Python 环境变量
sys.path.append("/Users/xiaoyue/src/bioinfo/project/Rules_project/simulation")

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from rule_engine import RuleEngine

def evaluate(cell, engine: 'RuleEngine', params: dict):
    """
    判断某个子状态是否持续了指定的 MCS。
    参数示例: {"sub_condition_script": "environment/is_hypoxia.py", "threshold_mcs": 50}
    """
    threshold_mcs = params.get("threshold_mcs", 50)
    sub_script = params.get("sub_condition_script")
    
    current_mcs = engine.cc3d_steppable.mcs
    
    # 1. 评估当前这一步，那个基础状态（比如缺氧）是否成立？
    # （这里假设你引擎里有一个执行子条件的方法）
    is_state_active = engine.evaluate_single_condition(cell, sub_script, params.get("sub_params", {}))
    
    # 我们用一个专门的 key 存在 cell.dict 里
    dict_key = f"timer_start_{sub_script}"
    
    if is_state_active:
        # 如果状态激活了，且之前没记录过时间，则记录下开始的 MCS
        if dict_key not in cell.dict:
            cell.dict[dict_key] = current_mcs
            
        # 计算持续了多久
        duration = current_mcs - cell.dict[dict_key]
        return duration > threshold_mcs
    else:
        # 如果状态中断了（比如突然有氧气了），计时器清零！(极其重要)
        if dict_key in cell.dict:
            del cell.dict[dict_key]
        return False