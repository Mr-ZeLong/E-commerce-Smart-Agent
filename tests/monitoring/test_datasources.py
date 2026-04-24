import json
from pathlib import Path

import pytest
import yaml

PROJECT_ROOT = Path(__file__).parent.parent.parent
DATASOURCES_DIR = PROJECT_ROOT / "grafana" / "provisioning" / "datasources"
DASHBOARDS_DIR = PROJECT_ROOT / "grafana" / "dashboards"

REQUIRED_DATASOURCE_FIELDS = ("name", "type", "access", "url")


def _list_datasource_files():
    return sorted(DATASOURCES_DIR.glob("*.yml"))


class TestDatasourceYaml:
    """Tests for Grafana datasource provisioning YAML files."""

    @pytest.mark.parametrize("datasource_path", _list_datasource_files(), ids=lambda p: p.name)
    def test_valid_yaml(self, datasource_path: Path) -> None:
        """Each datasource file must be valid YAML."""
        with datasource_path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        assert isinstance(data, dict)

    @pytest.mark.parametrize("datasource_path", _list_datasource_files(), ids=lambda p: p.name)
    def test_api_version_present(self, datasource_path: Path) -> None:
        """Each datasource file must declare apiVersion."""
        with datasource_path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        assert "apiVersion" in data, f"{datasource_path.name} missing apiVersion"

    @pytest.mark.parametrize("datasource_path", _list_datasource_files(), ids=lambda p: p.name)
    def test_datasources_key_present(self, datasource_path: Path) -> None:
        """Each datasource file must contain a datasources list."""
        with datasource_path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        assert "datasources" in data, f"{datasource_path.name} missing datasources key"
        assert isinstance(data["datasources"], list)

    @pytest.mark.parametrize("datasource_path", _list_datasource_files(), ids=lambda p: p.name)
    def test_required_fields_present(self, datasource_path: Path) -> None:
        """Each datasource entry must have required fields."""
        with datasource_path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)

        for idx, ds in enumerate(data.get("datasources", [])):
            for field in REQUIRED_DATASOURCE_FIELDS:
                assert field in ds, (
                    f"{datasource_path.name} datasource[{idx}] missing required field: {field}"
                )

    def test_datasource_names_are_unique(self) -> None:
        """All datasource names must be unique across provisioning files."""
        names = []
        for ds_path in _list_datasource_files():
            with ds_path.open("r", encoding="utf-8") as fh:
                data = yaml.safe_load(fh)
            for idx, ds in enumerate(data.get("datasources", [])):
                name = ds.get("name")
                assert name is not None, f"{ds_path.name} datasource[{idx}] missing name"
                names.append((ds_path.name, name))

        seen = {}
        duplicates = []
        for file_name, name in names:
            if name in seen:
                duplicates.append((file_name, seen[name], name))
            seen[name] = file_name

        assert not duplicates, f"Duplicate datasource names found: {duplicates}"

    def test_no_orphan_datasource_references(self) -> None:
        """Datasource UIDs referenced in annotations must exist in provisioning."""
        provisioned_uids = set()
        for ds_path in _list_datasource_files():
            with ds_path.open("r", encoding="utf-8") as fh:
                data = yaml.safe_load(fh)
            for ds in data.get("datasources", []):
                if "uid" in ds:
                    provisioned_uids.add(ds["uid"])
                if "jsonData" in ds:
                    jd = ds["jsonData"]
                    for key in ("datasourceUid", "alertmanagerUid"):
                        if key in jd:
                            provisioned_uids.add(jd[key])
                    for field in ("tracesToLogs", "tracesToMetrics"):
                        if field in jd and "datasourceUid" in jd[field]:
                            provisioned_uids.add(jd[field]["datasourceUid"])

        for dashboard_path in DASHBOARDS_DIR.glob("*.json"):
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
            referenced = {u for u in referenced if u and not u.startswith("$")}

            for uid in referenced:
                if uid in {"-- Grafana --", "grafana"}:
                    continue
                if uid in {"Prometheus", "Loki", "Tempo", "Mimir"}:
                    continue
                assert uid in provisioned_uids, (
                    f"{dashboard_path.name} references unknown datasource uid: {uid}"
                )
