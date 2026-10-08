"""
Diagnose MooMoo AppKey authentication (401 errors) without printing the private key.

Reads MOOMOO_APP_KEY_ID / MOOMOO_PRIVATE_KEY from .streamlit/secrets.toml or environment variables, then:
  1. shows the PUBLIC key derived from your private key — it must match the public key uploaded
     for this AppKey at open.moomoo.com → AppKey Management
  2. checks clock offset against GET /api/v1.0/server-time
  3. makes one signed GET and one signed POST and prints the status and response

Run from the repo root:  python tools/check_moomoo_auth.py
"""
import base64
import hashlib
import json
import os
import secrets
import sys
import time

import requests
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

API = "https://webapi.moomoo.com/api/v1.0"


def _secrets():
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".streamlit", "secrets.toml")
    vals = {}
    if os.path.exists(path):
        try:
            import tomllib
        except ImportError:   # Python < 3.11
            import tomli as tomllib
        with open(path, "rb") as f:
            vals = tomllib.load(f)
    key_id = str(vals.get("MOOMOO_APP_KEY_ID") or os.environ.get("MOOMOO_APP_KEY_ID", ""))
    pem = str(vals.get("MOOMOO_PRIVATE_KEY") or os.environ.get("MOOMOO_PRIVATE_KEY", ""))
    return key_id, pem


def main():
    key_id, pem = _secrets()
    if not key_id or not pem:
        sys.exit("Set MOOMOO_APP_KEY_ID and MOOMOO_PRIVATE_KEY in .streamlit/secrets.toml (git-ignored) or env vars.")

    pem = pem.strip()
    pk = load_pem_private_key(pem.encode(), password=None) if pem.startswith("-----") \
        else Ed25519PrivateKey.from_private_bytes(base64.b64decode(pem))
    print("AppKey ID      : ...{}".format(key_id[-8:]))
    print("Key type       : {}".format(type(pk).__name__))
    if not isinstance(pk, Ed25519PrivateKey):
        print("!! Not an Ed25519 key. If the AppKey was created with RSA-SHA256, signing must use RSA.")
    pub = pk.public_key()
    print("Public key (compare with the one uploaded to MooMoo):")
    print(pub.public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode())
    print("Public key raw base64: {}".format(base64.b64encode(
        pub.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode()))

    st = requests.get(API + "/server-time", timeout=15).json()
    offset = int(st["server_time_ms"]) - int(time.time() * 1000)
    print("\nClock offset vs MooMoo: {} ms {}".format(offset, "(OK)" if abs(offset) < 5000 else "!! > 5s — fix PC clock"))

    def call(method, path, query="", body=None):
        body_bytes = json.dumps(body, separators=(",", ":")).encode() if body is not None else b""
        ts = str(int(time.time() * 1000))
        canonical = "{}\n{}\n/api/v1.0{}\n{}\n{}".format(
            ts, method, path, query, hashlib.sha256(body_bytes).hexdigest() if body_bytes else "")
        headers = {"X-Api-Key": key_id, "X-Timestamp": ts, "X-Nonce": secrets.token_hex(16),
                   "Authorization": base64.b64encode(pk.sign(canonical.encode())).decode(),
                   "Content-Type": "application/json"}
        url = API + path + ("?" + query if query else "")
        r = requests.request(method, url, headers=headers, data=body_bytes or None, timeout=20)
        print("\n{} {} -> HTTP {}".format(method, path, r.status_code))
        print(r.text[:400])

    call("GET", "/quote/US.AAPL/option-expiration")
    call("POST", "/quote/stock-quote", body={"code_list": ["US.SPY"]})


if __name__ == "__main__":
    main()
