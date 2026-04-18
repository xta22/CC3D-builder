from pathlib import Path
import sys

# locate the RuleParser directory
# Path(__file__) ==> paths.py
# .parents[2] -- go up two levels: utils -> cc3d_builder -> RuleParser
ROOT = Path(__file__).resolve().parents[2]

# 2. define the essential child directories
BUILDER_DIR = ROOT / "cc3d_builder"
SANDBOX_DIR = ROOT / "Rules_project"
SIMULATION_DIR = SANDBOX_DIR / "Simulation"
RULES_JSON = SIMULATION_DIR / "config" / "rules.json"

# 3. automatically adjust sys.path
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT)) # prioritized