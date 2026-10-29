import os
import sys
import time
import threading
import requests
from flask import Flask, jsonify, request

# 1. Mock Legacy Service (simulating go-httpbin on port 8080)
legacy_app = Flask("legacy_service")

@legacy_app.route("/", defaults={"path": ""}, methods=["GET", "POST", "PUT", "DELETE"])
@legacy_app.route("/<path:path>", methods=["GET", "POST", "PUT", "DELETE"])
def legacy_endpoint(path):
    return jsonify({
        "status": "success",
        "service": "Internal Legacy Service (go-httpbin simulation)",
        "message": f"Hello from legacy service! Request to '/{path}' was authorized.",
        "client_user": request.headers.get("X-Authenticated-User", "Unknown"),
        "method": request.method
    }), 200

def run_legacy():
    legacy_app.run(host="127.0.0.1", port=8080, debug=False, use_reloader=False)

# 2. Main Test Runner
def main():
    print("=" * 60)
    print(">>> Starting Reverse Proxy & Legacy Service for Testing...")
    print("=" * 60)

    # Start mock legacy backend in background thread
    t_legacy = threading.Thread(target=run_legacy, daemon=True)
    t_legacy.start()

    # Configure proxy to talk to local legacy backend on 8080
    os.environ["BACKEND_URL"] = "http://127.0.0.1:8080"
    os.environ["PORT"] = "8000"
    
    # Import and start proxy
    from proxy import app as proxy_app
    def run_proxy():
        proxy_app.run(host="127.0.0.1", port=8000, debug=False, use_reloader=False)
    
    t_proxy = threading.Thread(target=run_proxy, daemon=True)
    t_proxy.start()

    # Wait 1.5 seconds for servers to bind
    time.sleep(1.5)

    base_url = "http://127.0.0.1:8000"
    all_passed = True

    # Test 1: Access without token
    print("\n[TEST 1] Sending request to internal service WITHOUT token...")
    r1 = requests.get(f"{base_url}/get")
    print(f"Status Code: {r1.status_code}")
    print(f"Response: {r1.json()}")
    if r1.status_code == 401:
        print("--> PASS: Unauthorized request successfully blocked with 401.")
    else:
        print("--> FAIL: Expected 401 status code.")
        all_passed = False

    # Test 2: Access with invalid token
    print("\n[TEST 2] Sending request WITH an INVALID token...")
    bad_headers = {"Authorization": "Bearer bad-token-12345"}
    r2 = requests.get(f"{base_url}/get", headers=bad_headers)
    print(f"Status Code: {r2.status_code}")
    print(f"Response: {r2.json()}")
    if r2.status_code == 401:
        print("--> PASS: Invalid token successfully rejected with 401.")
    else:
        print("--> FAIL: Expected 401 status code.")
        all_passed = False

    # Test 3: Login to get a valid JWT token
    print("\n[TEST 3] Calling /login endpoint to acquire a valid JWT token...")
    r3 = requests.post(f"{base_url}/login", json={"username": "alireza_sahraeian"})
    print(f"Status Code: {r3.status_code}")
    login_data = r3.json()
    token = login_data.get("access_token")
    print(f"Access Token: {token[:25]}... (truncated)")
    if r3.status_code == 200 and token:
        print("--> PASS: Token acquired successfully.")
    else:
        print("--> FAIL: Could not acquire JWT token.")
        all_passed = False

    # Test 4: Access internal service WITH valid token
    print("\n[TEST 4] Sending request to internal service WITH valid Bearer token...")
    good_headers = {"Authorization": f"Bearer {token}"}
    r4 = requests.get(f"{base_url}/api/resource", headers=good_headers)
    print(f"Status Code: {r4.status_code}")
    print(f"Response from Backend: {r4.json()}")
    if r4.status_code == 200 and r4.json().get("client_user") == "alireza_sahraeian":
        print("--> PASS: Request authorized and forwarded to legacy service successfully!")
    else:
        print("--> FAIL: Expected 200 and valid backend response.")
        all_passed = False

    print("\n" + "=" * 60)
    if all_passed:
        print(">>> ALL TESTS PASSED SUCCESSFULLY! (100% OK)")
    else:
        print(">>> SOME TESTS FAILED.")
    print("=" * 60)

    # Clean exit
    sys.exit(0)

if __name__ == "__main__":
    main()