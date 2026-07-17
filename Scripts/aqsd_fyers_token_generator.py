"""
AQSD FYERS Secure Token Generator v2.0
"""
from __future__ import annotations

import argparse
import json
import os
import webbrowser
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from fyers_apiv3 import fyersModel

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "Data"
LOGS = BASE / "Logs"
CONFIG = DATA / "fyers_config.env"


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def first(values: dict[str, str], *names: str) -> str:
    for name in names:
        value = values.get(name) or os.getenv(name)
        if value:
            return value.strip()
    return ""


def save_env(path: Path, original: dict[str, str], updates: dict[str, str]) -> None:
    merged = original.copy()
    merged.update(updates)
    order = [
        "FYERS_CLIENT_ID",
        "FYERS_SECRET_KEY",
        "FYERS_REDIRECT_URI",
        "FYERS_ACCESS_TOKEN",
        "FYERS_REFRESH_TOKEN",
    ]
    lines: list[str] = []
    written: set[str] = set()
    for key in order:
        if key in merged:
            lines.append(f"{key}={merged[key]}")
            written.add(key)
    for key, value in merged.items():
        if key not in written:
            lines.append(f"{key}={value}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def credentials() -> tuple[dict[str, str], str, str, str]:
    config = read_env(CONFIG)
    client_id = first(config, "FYERS_CLIENT_ID", "CLIENT_ID", "APP_ID")
    secret_key = first(config, "FYERS_SECRET_KEY", "SECRET_KEY", "APP_SECRET")
    redirect_uri = first(config, "FYERS_REDIRECT_URI", "REDIRECT_URI")

    missing = []
    if not client_id:
        missing.append("FYERS_CLIENT_ID")
    if not secret_key:
        missing.append("FYERS_SECRET_KEY")
    if not redirect_uri:
        missing.append("FYERS_REDIRECT_URI")
    if missing:
        raise SystemExit(
            "Missing config values: " + ", ".join(missing) + f"\nEdit: {CONFIG}"
        )
    return config, client_id, secret_key, redirect_uri


def extract_auth_code(full_url: str) -> str:
    query = parse_qs(urlparse(full_url.strip()).query)
    code = query.get("auth_code", [None])[0] or query.get("code", [None])[0]
    if not code:
        raise SystemExit("Could not extract auth_code from the redirected URL.")
    return code


def verify(client_id: str, token: str) -> tuple[bool, str]:
    LOGS.mkdir(parents=True, exist_ok=True)
    fyers = fyersModel.FyersModel(
        client_id=client_id,
        token=token,
        is_async=False,
        log_path=str(LOGS),
    )
    response = fyers.quotes({"symbols": "NSE:NIFTYBANK-INDEX"})
    if not isinstance(response, dict):
        return False, "Unexpected response"
    if response.get("s") != "ok":
        return False, str(response.get("message", "Verification failed"))
    if not response.get("d"):
        return False, "No BANKNIFTY quote returned"
    return True, "BANKNIFTY quote received"


def show_status() -> None:
    config = read_env(CONFIG)
    print("\nAQSD FYERS TOKEN STATUS")
    print("=" * 68)
    print(f"Config file:   {CONFIG}")
    print(f"Config exists: {'YES' if CONFIG.exists() else 'NO'}")
    print(f"Client ID:     {'FOUND' if first(config, 'FYERS_CLIENT_ID', 'CLIENT_ID', 'APP_ID') else 'MISSING'}")
    print(f"Secret key:    {'FOUND' if first(config, 'FYERS_SECRET_KEY', 'SECRET_KEY', 'APP_SECRET') else 'MISSING'}")
    print(f"Redirect URI:  {'FOUND' if first(config, 'FYERS_REDIRECT_URI', 'REDIRECT_URI') else 'MISSING'}")
    print(f"Access token:  {'SAVED' if first(config, 'FYERS_ACCESS_TOKEN', 'ACCESS_TOKEN') else 'MISSING'}")
    print("=" * 68)


def run() -> None:
    config, client_id, secret_key, redirect_uri = credentials()

    session = fyersModel.SessionModel(
        client_id=client_id,
        secret_key=secret_key,
        redirect_uri=redirect_uri,
        response_type="code",
        grant_type="authorization_code",
    )

    login_url = session.generate_authcode()

    print("\n" + "=" * 72)
    print("AQSD FYERS SECURE TOKEN GENERATOR")
    print("=" * 72)
    print("Opening FYERS login page in your browser...")

    opened = False
    try:
        opened = webbrowser.open(login_url)
    except Exception:
        opened = False

    if not opened:
        print("\nOpen this URL in Chrome:")
        print(login_url)

    print("\nAfter login, the browser may show 'This site can't be reached'.")
    print("That is normal. Copy the FULL URL from the browser address bar.")
    redirected_url = input("\nPaste the FULL redirected URL here:\n").strip()

    auth_code = extract_auth_code(redirected_url)
    session.set_token(auth_code)
    response = session.generate_token()

    if not isinstance(response, dict) or response.get("s") != "ok":
        code = response.get("code", "UNKNOWN") if isinstance(response, dict) else "UNKNOWN"
        message = response.get("message", "Token generation failed") if isinstance(response, dict) else "Unexpected response"
        raise SystemExit(f"Token generation failed. Code={code}; Message={message}")

    access_token = str(response.get("access_token", "")).strip()
    refresh_token = str(response.get("refresh_token", "")).strip()
    if not access_token:
        raise SystemExit("FYERS did not return an access token.")

    updates = {
        "FYERS_CLIENT_ID": client_id,
        "FYERS_SECRET_KEY": secret_key,
        "FYERS_REDIRECT_URI": redirect_uri,
        "FYERS_ACCESS_TOKEN": access_token,
    }
    if refresh_token:
        updates["FYERS_REFRESH_TOKEN"] = refresh_token

    save_env(CONFIG, config, updates)

    print("\nToken saved. Verifying with BANKNIFTY quote...")
    ok, message = verify(client_id, access_token)

    print("\n" + "=" * 72)
    if ok:
        print("ACCESS TOKEN GENERATED AND VERIFIED SUCCESSFULLY")
        print(f"Verification: {message}")
        print(f"Saved into:  {CONFIG}")
        print("Security: Access and refresh tokens were not displayed.")
    else:
        print("ACCESS TOKEN GENERATED, BUT VERIFICATION FAILED")
        print(f"Reason: {message}")
        print(f"Saved into: {CONFIG}")
        raise SystemExit(1)
    print("=" * 72)


def main() -> None:
    parser = argparse.ArgumentParser(description="AQSD FYERS Secure Token Generator")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()

    if args.status:
        show_status()
    else:
        run()


if __name__ == "__main__":
    main()
