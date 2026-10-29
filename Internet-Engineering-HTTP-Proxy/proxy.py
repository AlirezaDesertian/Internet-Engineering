import os
import requests
from flask import Flask, request, jsonify, Response
import jwt
from datetime import datetime, timedelta, timezone

app = Flask(__name__)

# Configurations
SECRET_KEY = os.getenv("JWT_SECRET", "super-secure-jwt-secret-key-internet-engineering-2026-strictly-32bytes")
ALGORITHM = "HS256"
BACKEND_URL = os.getenv("BACKEND_URL", "http://legacy-service:8080")


@app.route("/login", methods=["POST"])
def login():
    """
    Public endpoint to generate a valid JWT token for demonstration.
    Accepts JSON with 'username' and 'password' or defaults to guest.
    """
    data = request.get_json(silent=True) or {}
    username = data.get("username", "admin")

    payload = {
        "sub": username,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

    return jsonify({
        "message": "Authentication successful",
        "access_token": token,
        "token_type": "Bearer",
        "expires_in_hours": 1
    }), 200


@app.route("/", defaults={"path": ""}, methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
@app.route("/<path:path>", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
def proxy(path):
    """
    Reverse proxy handler with JWT validation.
    Forwards valid requests to the legacy service.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({
            "error": "Unauthorized",
            "message": "Missing or invalid Authorization header. Expected 'Bearer <token>'"
        }), 401

    token = auth_header.split(" ")[1]

    try:
        decoded_payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        return jsonify({"error": "Unauthorized", "message": "JWT token has expired"}), 401
    except jwt.InvalidTokenError:
        return jsonify({"error": "Unauthorized", "message": "Invalid JWT token"}), 401

    # Prepare request to internal legacy service
    target_url = f"{BACKEND_URL}/{path}"
    
    # Filter out hop-by-hop headers
    forward_headers = {
        key: value for key, value in request.headers
        if key.lower() not in ["host", "authorization"]
    }
    # Pass user context from token to legacy service
    forward_headers["X-Authenticated-User"] = str(decoded_payload.get("sub"))

    try:
        resp = requests.request(
            method=request.method,
            url=target_url,
            headers=forward_headers,
            params=request.args,
            data=request.get_data(),
            cookies=request.cookies,
            allow_redirects=False,
            timeout=10
        )
    except requests.exceptions.RequestException as e:
        return jsonify({
            "error": "Bad Gateway",
            "message": f"Could not reach legacy service: {str(e)}"
        }), 502

    # Return response from legacy service
    excluded_headers = ["content-encoding", "content-length", "transfer-encoding", "connection"]
    headers = [
        (name, value) for name, value in resp.raw.headers.items()
        if name.lower() not in excluded_headers
    ]

    return Response(resp.content, resp.status_code, headers)


if __name__ == "__main__":
    port = int(os.getenv("PORT", 80))
    app.run(host="0.0.0.0", port=port)