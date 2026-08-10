# project_profile.py
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


PROFILE_DIR_NAME = ".ruleparser"
PROFILE_RULES_NAME = "rules.json"
PROFILE_METADATA_NAME = "metadata.json"
ACTIVE_PROJECT_NAME = "active_project.json"


def profile_dir(source_path):
    source = project_root(source_path)
    return source / PROFILE_DIR_NAME


def project_root(source_path):
    source = Path(source_path).expanduser().resolve()
    return source.parent if source.is_file() else source


def profile_rules_path(source_path):
    return profile_dir(source_path) / PROFILE_RULES_NAME


def profile_metadata_path(source_path):
    return profile_dir(source_path) / PROFILE_METADATA_NAME


def sandbox_profile_dir(sandbox_path):
    return Path(sandbox_path).expanduser().resolve() / PROFILE_DIR_NAME


def active_project_path(sandbox_path):
    return sandbox_profile_dir(sandbox_path) / ACTIVE_PROJECT_NAME


def utc_timestamp():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def has_project_profile(source_path):
    return profile_rules_path(source_path).exists()


def load_json(path, default=None):
    path = Path(path)
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def write_active_project(sandbox_path, source_path, mode):
    source = project_root(source_path)
    data = {
        "source_project_path": str(source),
        "profile_dir": str(profile_dir(source)),
        "profile_rules_path": str(profile_rules_path(source)),
        "mode": mode,
        "updated_at": utc_timestamp(),
    }
    write_json(active_project_path(sandbox_path), data)
    return data


def read_active_project(sandbox_path):
    return load_json(active_project_path(sandbox_path), {}) or {}


def restore_profile_to_sandbox(source_path, sandbox_path):
    source_rules = profile_rules_path(source_path)
    if not source_rules.exists():
        return False

    sandbox_rules = Path(sandbox_path).expanduser().resolve() / "Simulation" / PROFILE_RULES_NAME
    sandbox_rules.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_rules, sandbox_rules)
    return True


def _rule_count_from_file(path):
    try:
        data = load_json(path, {}) or {}
        rules = data.get("rules", [])
        return len(rules) if isinstance(rules, list) else 0
    except Exception:
        return None


def sync_sandbox_rules_to_profile(sandbox_path, source_path=None):
    sandbox = Path(sandbox_path).expanduser().resolve()
    if source_path is None:
        active = read_active_project(sandbox)
        source_path = active.get("source_project_path")
    if not source_path:
        return False

    source = project_root(source_path)
    sandbox_rules = sandbox / "Simulation" / PROFILE_RULES_NAME
    if not sandbox_rules.exists():
        return False

    target_rules = profile_rules_path(source)
    target_rules.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(sandbox_rules, target_rules)

    metadata = {
        "source_project_path": str(source),
        "sandbox_project_path": str(sandbox),
        "rules_path": str(target_rules),
        "rule_count": _rule_count_from_file(target_rules),
        "updated_at": utc_timestamp(),
    }
    cc3d_files = sorted(source.glob("*.cc3d"))
    if cc3d_files:
        metadata["cc3d_file"] = str(cc3d_files[0])
    write_json(profile_metadata_path(source), metadata)
    write_active_project(sandbox, source, mode="synced")
    return True
