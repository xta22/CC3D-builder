# pif_snapshot_steppable.py
import json
from pathlib import Path

from cc3d.core.PySteppables import SteppableBasePy


class RuleParserPIFDumperSteppable(SteppableBasePy):
    """Cluster-aware PIFF dumper for RuleParser projects."""

    def __init__(self, frequency=1, settings_path=None, config=None):
        super().__init__(frequency)
        self.settings_path = Path(settings_path) if settings_path else None
        self.config = config if isinstance(config, dict) else None
        self.enabled = False
        self.base_name = ""
        self.dump_frequency = 100

    def start(self):
        self._load_config()
        if self.enabled:
            print(
                "[RuleParserPIFDumper] enabled: "
                f"base={self.base_name} frequency={self.dump_frequency} include_clusters=True"
            )

    def step(self, mcs):
        if not self.enabled:
            return
        if mcs <= 0 or mcs % self.dump_frequency != 0:
            return
        self.dump_snapshot(mcs)

    def dump_snapshot(self, mcs):
        path = self._snapshot_path(mcs)
        path.parent.mkdir(parents=True, exist_ok=True)
        line_count = 0
        with path.open("w", encoding="utf-8") as handle:
            handle.write("Include Clusters\n")
            for x in range(self.dim.x):
                for y in range(self.dim.y):
                    for z in range(self.dim.z):
                        cell = self.cell_field[x, y, z]
                        if cell is None:
                            continue
                        cluster_id = getattr(cell, "clusterId", getattr(cell, "id", 0))
                        cell_id = getattr(cell, "id", 0)
                        type_name = self._cell_type_name(cell)
                        handle.write(
                            f"{int(cluster_id)}\t{int(cell_id)}\t{type_name}\t"
                            f"{x}\t{x}\t{y}\t{y}\t{z}\t{z}\n"
                        )
                        line_count += 1
        print(f"[RuleParserPIFDumper] wrote {line_count} occupied pixels to {path}")

    def _load_config(self):
        config = self.config or self._config_from_settings_file()
        dumper = self._normalize_dumper_config(config)
        self.enabled = bool(dumper.get("enabled") and dumper.get("path"))
        self.base_name = str(dumper.get("path") or "").strip()
        self.dump_frequency = max(1, int(dumper.get("frequency", 100)))

    def _config_from_settings_file(self):
        if self.settings_path is None or not self.settings_path.exists():
            return {}
        try:
            data = json.loads(self.settings_path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"[RuleParserPIFDumper] could not read settings: {exc}")
            return {}
        settings = data.get("settings", data) if isinstance(data, dict) else {}
        if not isinstance(settings, dict):
            return {}
        return settings.get("piff") or settings.get("pif") or settings.get("pif_io") or {}

    @staticmethod
    def _normalize_dumper_config(config):
        if not isinstance(config, dict):
            config = {}
        raw = config.get("dumper") or config.get("export") or {}
        if not isinstance(raw, dict):
            raw = {}
        try:
            frequency = int(float(raw.get("frequency", raw.get("Frequency", 100))))
        except (TypeError, ValueError):
            frequency = 100
        return {
            "enabled": bool(raw.get("enabled", raw.get("use", False))),
            "path": str(
                raw.get("path")
                or raw.get("base_name")
                or raw.get("pif_name")
                or raw.get("PIFName")
                or ""
            ).strip(),
            "frequency": max(1, frequency),
        }

    def _snapshot_path(self, mcs):
        base = Path(self.base_name).expanduser()
        extension = base.suffix if base.suffix.lower() in {".pif", ".piff"} else ".piff"
        if base.suffix.lower() in {".pif", ".piff"}:
            base = base.with_suffix("")
        path = base.parent / f"{base.name}{int(mcs):06d}{extension}"
        if path.is_absolute():
            return path
        return self._project_root() / path

    def _project_root(self):
        try:
            base_path = Path(self.simulator.getBasePath()).expanduser().resolve()
        except Exception:
            return Path.cwd()
        if base_path.name == "Simulation":
            return base_path.parent
        return base_path

    def _cell_type_name(self, cell):
        try:
            return str(self.get_type_name_by_cell(cell))
        except Exception:
            return str(getattr(cell, "type", "Cell"))
