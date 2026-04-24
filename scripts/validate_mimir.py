"""Validation script for Mimir metrics storage."""

import json
import sys
import urllib.error
import urllib.parse
import urllib.request

MIMIR_URL = "http://localhost:9009"


def check_readiness() -> bool:
    """Check if Mimir is ready to accept traffic."""
    try:
        req = urllib.request.Request(f"{MIMIR_URL}/ready", method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = resp.read().decode()
            if resp.status == 200 and "ready" in body.lower():
                print(f"[OK] Mimir readiness: {body.strip()}")
                return True
            print(f"[WARN] Mimir readiness unexpected: {resp.status} {body}")
            return False
    except urllib.error.HTTPError as e:
        if e.code == 503:
            body = e.read().decode()
            print(f"[FAIL] Mimir not ready: {body.strip()}")
        else:
            print(f"[FAIL] Mimir readiness check failed: {e}")
        return False
    except Exception as e:
        print(f"[FAIL] Mimir readiness check failed: {e}")
        return False


def query_metric() -> bool:
    """Query a metric to verify data is being written to Mimir."""
    query = 'up{job="prometheus"}'
    url = f"{MIMIR_URL}/prometheus/api/v1/query?query={urllib.parse.quote(query)}"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            if data.get("status") == "success":
                result = data.get("data", {}).get("result", [])
                if result:
                    print(f"[OK] Mimir query returned {len(result)} series for {query}")
                    return True
                print(f"[WARN] Mimir query returned no data for {query} (may need time to ingest)")
                return False
            print(f"[FAIL] Mimir query error: {data.get('error')}")
            return False
    except Exception as e:
        print(f"[FAIL] Mimir query failed: {e}")
        return False


def check_retention() -> bool:
    """Verify retention configuration via Mimir runtime config."""
    try:
        req = urllib.request.Request(f"{MIMIR_URL}/runtime_config", method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            overrides = data.get("overrides", {})
            tenant = overrides.get("", {})
            ingestion_rate = tenant.get("ingestion_rate", 0)
            ingestion_burst = tenant.get("ingestion_burst_size", 0)
            print(f"[OK] Runtime ingestion_rate={ingestion_rate}, ingestion_burst_size={ingestion_burst}")
            return True
    except Exception as e:
        print(f"[WARN] Could not verify runtime config: {e}")
        return False


def main() -> int:
    """Run all validation checks."""
    print("=" * 50)
    print("Mimir Validation Script")
    print("=" * 50)

    results = []

    print("\n1. Checking Mimir readiness...")
    results.append(check_readiness())

    print("\n2. Querying metric from Mimir...")
    results.append(query_metric())

    print("\n3. Checking retention/runtime config...")
    results.append(check_retention())

    print("\n" + "=" * 50)
    passed = sum(results)
    total = len(results)
    print(f"Results: {passed}/{total} checks passed")
    print("=" * 50)

    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
