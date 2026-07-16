"""
AQSD FYERS TOKEN GENERATOR
Version: 1.0

Creates a FYERS login URL and exchanges the returned auth_code
for an access token.

Keep App ID, Secret ID, auth code and access token private.
"""

from pathlib import Path
from urllib.parse import urlparse, parse_qs

from fyers_apiv3 import fyersModel


BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_FILE = BASE_DIR / "Data" / "fyers_config.env"


def load_config():
    config = {}

    if not CONFIG_FILE.exists():
        raise FileNotFoundError(
            f"Configuration file not found:\n{CONFIG_FILE}"
        )

    for raw_line in CONFIG_FILE.read_text(
        encoding="utf-8"
    ).splitlines():

        line = raw_line.strip()

        if not line:
            continue

        if line.startswith("#"):
            continue

        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        config[key.strip()] = value.strip()

    return config


def update_access_token(token):

    lines = CONFIG_FILE.read_text(
        encoding="utf-8"
    ).splitlines()

    updated = []
    found = False

    for line in lines:

        if line.startswith("ACCESS_TOKEN="):
            updated.append(f"ACCESS_TOKEN={token}")
            found = True
        else:
            updated.append(line)

    if not found:
        updated.append(f"ACCESS_TOKEN={token}")

    CONFIG_FILE.write_text(
        "\n".join(updated) + "\n",
        encoding="utf-8"
    )


def extract_auth_code(text):

    value = text.strip()

    if not value:
        raise ValueError("Nothing entered.")

    if "auth_code=" not in value:
        return value

    parsed = urlparse(value)
    query = parse_qs(parsed.query)

    codes = query.get("auth_code")

    if not codes:
        raise ValueError("auth_code not found.")

    return codes[0]


def main():

    config = load_config()

    required = [
        "CLIENT_ID",
        "SECRET_KEY",
        "REDIRECT_URI"
    ]

    missing = [
        key
        for key in required
        if not config.get(key)
    ]

    if missing:

        print(
            "\nMissing values:\n"
            + "\n".join(missing)
        )
        return

    session = fyersModel.SessionModel(
        client_id=config["CLIENT_ID"],
        secret_key=config["SECRET_KEY"],
        redirect_uri=config["REDIRECT_URI"],
        response_type="code",
        grant_type="authorization_code",
    )

    login_url = session.generate_authcode()

    print("\n")
    print("=" * 70)
    print("AQSD FYERS TOKEN GENERATOR")
    print("=" * 70)

    print("\nOpen this URL in Chrome:\n")
    print(login_url)

    print("\nAfter login you will be redirected.")
    print("The browser may show:")
    print("This site can't be reached")
    print("This is NORMAL.")

    value = input(
        "\nPaste the FULL redirected URL here:\n"
    )

    auth_code = extract_auth_code(value)

    session.set_token(auth_code)

    response = session.generate_token()

    print("\n")
    print(response)

    if response.get("s") != "ok":
        print("\nToken generation failed.")
        return

    token = response.get("access_token")

    update_access_token(token)

    print("\n")
    print("=" * 70)
    print("ACCESS TOKEN GENERATED SUCCESSFULLY")
    print("=" * 70)
    print("Saved into:")
    print(CONFIG_FILE)


if __name__ == "__main__":
    main()