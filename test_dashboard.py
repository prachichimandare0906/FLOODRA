
import json
import urllib.error
import urllib.request

BASE_URL = "http://127.0.0.1:5000"

ENDPOINTS = [
    "/api/status",
    "/api/roads",
    "/api/isolation",
    "/api/priority",
    "/api/flood-stats",
    "/api/summary",
    "/api/analysis-report",
    "/api/road-risk-summary",
    "/api/connectivity",
    "/api/connectivity-summary",
    "/api/response-decisions",
    "/api/model-validation",
]


def check_endpoint(endpoint):
    url = BASE_URL + endpoint

    try:
        request = urllib.request.Request(
            url,
            headers={"Accept": "application/json"},
        )

        with urllib.request.urlopen(request, timeout=10) as response:
            status_code = response.status
            body = response.read().decode("utf-8")

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            print(f"[FAIL] {endpoint} - Response is not valid JSON")
            return False

        if not isinstance(data, (dict, list)):
            print(f"[FAIL] {endpoint} - Unexpected JSON format")
            return False

        if status_code == 200:
            print(f"[PASS] {endpoint} - HTTP {status_code}")
            return True

        print(f"[FAIL] {endpoint} - HTTP {status_code}")
        return False

    except urllib.error.HTTPError as error:
        print(f"[FAIL] {endpoint} - HTTP {error.code}")
    except urllib.error.URLError as error:
        print(f"[FAIL] {endpoint} - Cannot connect: {error.reason}")
    except TimeoutError:
        print(f"[FAIL] {endpoint} - Request timed out")
    except Exception as error:
        print(f"[FAIL] {endpoint} - {error}")

    return False


def main():
    print("=" * 60)
    print("FLOODRA DASHBOARD API HEALTH CHECK")
    print("=" * 60)

    passed = 0

    for endpoint in ENDPOINTS:
        if check_endpoint(endpoint):
            passed += 1

    failed = len(ENDPOINTS) - passed

    print("\n" + "=" * 60)
    print(f"Passed: {passed}/{len(ENDPOINTS)}")
    print(f"Failed: {failed}/{len(ENDPOINTS)}")
    print("=" * 60)

    if failed:
        print(
            "\nReview failed endpoints in dashboard/app.py "
            "and check the Flask terminal."
        )
    else:
        print("\nAll tested endpoints returned valid JSON.")


if __name__ == "__main__":
    main()
