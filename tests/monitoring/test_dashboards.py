import json
from pathlib import Path

import pytest
import yaml

PROJECT_ROOT = Path(__file__).parent.parent.parent
DASHBOARDS_DIR = PROJECT_ROOT / "grafana" / "dashboards"
DATASOURCES_DIR = PROJECT_ROOT / "grafana" / "provisioning" / "datasources"

REQUIRED_DASHBOARD_FIELDS = ("title", "uid", "panels", "timezone")


def _list_dashboard_files():
    return sorted(DASHBOARDS_DIR.glob("*.json"))


class TestDashboardJson:
    """Tests for Grafana dashboard JSON files."""

    @pytest.mark.parametrize("dashboard_path", _list_dashboard_files(), ids=lambda p: p.name)
    def test_valid_json(self, dashboard_path: Path) -> None:
        """Each dashboard file must be valid JSON."""
        with dashboard_path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        assert isinstance(data, dict)

    @pytest.mark.parametrize("dashboard_path", _list_dashboard_files(), ids=lambda p: p.name)
    def test_required_fields_present(self, dashboard_path: Path) -> None:
        """Each dashboard must have required fields: title, uid, panels, timezone."""
        with dashboard_path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)

        for field in REQUIRED_DASHBOARD_FIELDS:
            assert field in data, f"{dashboard_path.name} missing required field: {field}"

    @pytest.mark.parametrize("dashboard_path", _list_dashboard_files(), ids=lambda p: p.name)
    def test_panels_is_non_empty_array(self, dashboard_path: Path) -> None:
        """Each dashboard must have at least one panel."""
        with dashboard_path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)

        panels = data.get("panels", [])
        assert isinstance(panels, list), f"{dashboard_path.name}: panels must be a list"
        assert len(panels) > 0, f"{dashboard_path.name}: panels must not be empty"

    def test_dashboard_uids_are_unique(self) -> None:
        """All dashboard UIDs must be unique across the repository."""
        uids = []
        for dashboard_path in _list_dashboard_files():
            with dashboard_path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            uid = data.get("uid")
            assert uid is not None, f"{dashboard_path.name} missing uid"
            uids.append((dashboard_path.name, uid))

        seen = {}
        duplicates = []
        for name, uid in uids:
            if uid in seen:
                duplicates.append((name, seen[uid], uid))
            seen[uid] = name

        assert not duplicates, f"Duplicate UIDs found: {duplicates}"

    def test_datasource_references_exist(self) -> None:
        """Datasource UIDs referenced in dashboards must exist in provisioning."""
        valid_uids = set()
        for ds_path in DATASOURCES_DIR.glob("*.yml"):
            with ds_path.open("r", encoding="utf-8") as fh:
                data = yaml.safe_load(fh)
            for ds in data.get("datasources", []):
                if "uid" in ds:
                    valid_uids.add(ds["uid"])
                if "jsonData" in ds:
                    jd = ds["jsonData"]
                    for key in ("datasourceUid", "alertmanagerUid"):
                        if key in jd:
                            valid_uids.add(jd[key])
                    for field in ("tracesToLogs", "tracesToMetrics"):
                        if field in jd and "datasourceUid" in jd[field]:
                            valid_uids.add(jd[field]["datasourceUid"])

        # Also allow built-in datasource UIDs commonly used in dashboards
        valid_uids.update({"-- Grafana --", "grafana"})

        missing = []
        for dashboard_path in _list_dashboard_files():
            with dashboard_path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)

            def _extract_datasource_uids(obj):
                uids = []
                if isinstance(obj, dict):
                    if obj.get("type") == "prometheus" and "uid" in obj:
                        uids.append(obj["uid"])
                    if "datasource" in obj and isinstance(obj["datasource"], dict):
                        ds = obj["datasource"]
                        if "uid" in ds:
                            uids.append(ds["uid"])
                    for v in obj.values():
                        uids.extend(_extract_datasource_uids(v))
                elif isinstance(obj, list):
                    for item in obj:
                        uids.extend(_extract_datasource_uids(item))
                return uids

            referenced = set(_extract_datasource_uids(data))
            # Filter out empty or placeholder UIDs
            referenced = {u for u in referenced if u and not u.startswith("$")}

            for uid in referenced:
                if uid not in valid_uids:
                    # Check if it's a literal datasource name instead of UID
                    # Some dashboards reference datasource by name in old schema
                    if uid in {"Prometheus", "Loki", "Tempo", "Mimir"}:
                        continue
                    missing.append((dashboard_path.name, uid))

        assert not missing, f"Missing datasource references: {missing}"
