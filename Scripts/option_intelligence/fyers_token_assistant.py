"""
AQSD
FYERS DAILY TOKEN ASSISTANT

Module: fyers_token_assistant.py
Version: 1.0
Author: AQSD

Purpose:
- Opens the official FYERS authorization page.
- User completes FYERS login and 2FA in the browser.
- Accepts either the complete redirected URL or only the auth_code.
- Exchanges auth_code for an access token through fyers-apiv3.
- Updates FYERS_ACCESS_TOKEN safely inside AQSD/.env.
- Verifies the token by requesting the FYERS profile.

Security:
- Does not store FYERS password, PIN, OTP, or TOTP secret.
- Does not bypass FYERS login or 2FA.
- Does not place orders.
"""

from __future__ import annotations

import json
import os
import threading
import tkinter as tk
import webbrowser

from datetime import datetime
from pathlib import Path
from tkinter import messagebox
from typing import Any
from urllib.parse import parse_qs, urlparse

from dotenv import load_dotenv
from fyers_apiv3 import fyersModel


# ============================================================
# PATHS AND SETTINGS
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BASE_DIR / ".env"

WINDOW_TITLE = "AQSD — FYERS Daily Token Assistant"
WINDOW_WIDTH = 820
WINDOW_HEIGHT = 610

BACKGROUND = "#111827"
PANEL_BACKGROUND = "#182230"
CARD_BACKGROUND = "#243041"
BORDER_COLOR = "#3B4A5F"

TEXT_PRIMARY = "#F8FAFC"
TEXT_SECONDARY = "#AAB7C8"

ACCENT_BLUE = "#6EA8FE"
ACCENT_GREEN = "#4ADE80"
ACCENT_RED = "#FB7185"
ACCENT_ORANGE = "#FDBA74"


# ============================================================
# ENVIRONMENT HELPERS
# ============================================================

def read_environment_value(
    *names: str,
) -> str:
    """
    Return the first non-empty environment variable.
    """

    for name in names:
        value = os.getenv(name)

        if value:
            return value.strip()

    return ""


def load_fyers_credentials() -> tuple[str, str, str]:
    """
    Load client ID, secret key and redirect URI from AQSD/.env.
    """

    load_dotenv(
        ENV_FILE,
        override=True,
    )

    client_id = read_environment_value(
        "FYERS_CLIENT_ID",
        "FYERS_APP_ID",
        "CLIENT_ID",
    )

    secret_key = read_environment_value(
        "FYERS_SECRET_KEY",
        "FYERS_APP_SECRET",
        "SECRET_KEY",
    )

    redirect_uri = read_environment_value(
        "FYERS_REDIRECT_URI",
        "REDIRECT_URI",
    )

    missing: list[str] = []

    if not client_id:
        missing.append(
            "FYERS_CLIENT_ID"
        )

    if not secret_key:
        missing.append(
            "FYERS_SECRET_KEY"
        )

    if not redirect_uri:
        missing.append(
            "FYERS_REDIRECT_URI"
        )

    if missing:
        raise RuntimeError(
            "Missing value(s) in .env: "
            + ", ".join(missing)
        )

    return (
        client_id,
        secret_key,
        redirect_uri,
    )


def mask_value(
    value: str,
    visible_end: int = 4,
) -> str:
    """
    Mask a sensitive value for display.
    """

    if not value:
        return "N/A"

    if len(value) <= visible_end:
        return "*" * len(value)

    return (
        "*" * (len(value) - visible_end)
        + value[-visible_end:]
    )


# ============================================================
# FYERS AUTHENTICATION
# ============================================================

def build_session_model(
    client_id: str,
    secret_key: str,
    redirect_uri: str,
) -> Any:
    """
    Build the official FYERS API v3 SessionModel.
    """

    return fyersModel.SessionModel(
        client_id=client_id,
        secret_key=secret_key,
        redirect_uri=redirect_uri,
        response_type="code",
        grant_type="authorization_code",
    )


def generate_authorization_url(
    client_id: str,
    secret_key: str,
    redirect_uri: str,
) -> str:
    """
    Generate the official FYERS authorization URL.
    """

    session = build_session_model(
        client_id=client_id,
        secret_key=secret_key,
        redirect_uri=redirect_uri,
    )

    authorization_url = (
        session.generate_authcode()
    )

    if not authorization_url:
        raise RuntimeError(
            "FYERS did not return an authorization URL."
        )

    return str(
        authorization_url
    )


def extract_auth_code(
    user_input: str,
) -> str:
    """
    Extract auth_code from a redirected URL or accept a raw code.
    """

    cleaned = user_input.strip()

    if not cleaned:
        raise ValueError(
            "Please paste the redirected URL or auth_code."
        )

    if "://" not in cleaned and "auth_code=" not in cleaned:
        return cleaned

    candidate_url = cleaned

    if "://" not in candidate_url:
        candidate_url = (
            "https://localhost/?"
            + candidate_url.lstrip("?")
        )

    parsed = urlparse(
        candidate_url
    )

    query_values = parse_qs(
        parsed.query
    )

    auth_code_values = (
        query_values.get("auth_code")
        or query_values.get("authCode")
        or query_values.get("code")
    )

    if auth_code_values:
        auth_code = str(
            auth_code_values[0]
        ).strip()

        if auth_code:
            return auth_code

    fragment_values = parse_qs(
        parsed.fragment
    )

    auth_code_values = (
        fragment_values.get("auth_code")
        or fragment_values.get("authCode")
        or fragment_values.get("code")
    )

    if auth_code_values:
        auth_code = str(
            auth_code_values[0]
        ).strip()

        if auth_code:
            return auth_code

    raise ValueError(
        "Could not find auth_code in the pasted value."
    )


def exchange_auth_code(
    auth_code: str,
    client_id: str,
    secret_key: str,
    redirect_uri: str,
) -> dict[str, Any]:
    """
    Exchange auth_code for a FYERS access token.
    """

    session = build_session_model(
        client_id=client_id,
        secret_key=secret_key,
        redirect_uri=redirect_uri,
    )

    session.set_token(
        auth_code
    )

    response = session.generate_token()

    if not isinstance(
        response,
        dict,
    ):
        raise RuntimeError(
            f"Unexpected FYERS token response: {response}"
        )

    status = str(
        response.get(
            "s",
            "",
        )
    ).strip().lower()

    access_token = str(
        response.get(
            "access_token",
            "",
        )
    ).strip()

    if (
        status not in {
            "ok",
            "success",
            "",
        }
        or not access_token
    ):
        message = (
            response.get("message")
            or response.get("msg")
            or json.dumps(
                response,
                ensure_ascii=False,
            )
        )

        raise RuntimeError(
            f"FYERS token generation failed: {message}"
        )

    return response


def verify_access_token(
    client_id: str,
    access_token: str,
) -> dict[str, Any]:
    """
    Verify the generated token using the FYERS profile endpoint.
    """

    fyers = fyersModel.FyersModel(
        client_id=client_id,
        token=access_token,
        is_async=False,
        log_path="",
    )

    response = fyers.get_profile()

    if not isinstance(
        response,
        dict,
    ):
        raise RuntimeError(
            f"Unexpected profile response: {response}"
        )

    status = str(
        response.get(
            "s",
            "",
        )
    ).strip().lower()

    if status not in {
        "ok",
        "success",
    }:
        message = (
            response.get("message")
            or response.get("msg")
            or json.dumps(
                response,
                ensure_ascii=False,
            )
        )

        raise RuntimeError(
            f"Generated token could not be verified: {message}"
        )

    return response


# ============================================================
# .ENV UPDATE
# ============================================================

def update_env_value(
    env_file: Path,
    key: str,
    value: str,
) -> None:
    """
    Update or append one key in the .env file.

    Existing unrelated lines and comments are preserved.
    """

    env_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    existing_lines: list[str] = []

    if env_file.exists():
        existing_lines = env_file.read_text(
            encoding="utf-8",
        ).splitlines()

    new_lines: list[str] = []
    updated = False

    for line in existing_lines:
        stripped = line.strip()

        if (
            stripped
            and not stripped.startswith("#")
            and "=" in stripped
        ):
            existing_key = (
                stripped.split(
                    "=",
                    1,
                )[0]
                .strip()
            )

            if existing_key == key:
                new_lines.append(
                    f"{key}={value}"
                )
                updated = True
                continue

        new_lines.append(
            line
        )

    if not updated:
        if (
            new_lines
            and new_lines[-1].strip()
        ):
            new_lines.append(
                ""
            )

        new_lines.append(
            f"{key}={value}"
        )

    env_file.write_text(
        "\n".join(new_lines) + "\n",
        encoding="utf-8",
    )


def save_token_response(
    response: dict[str, Any],
) -> None:
    """
    Store the generated access token and optional metadata.
    """

    access_token = str(
        response.get(
            "access_token",
            "",
        )
    ).strip()

    if not access_token:
        raise RuntimeError(
            "Token response did not contain access_token."
        )

    update_env_value(
        ENV_FILE,
        "FYERS_ACCESS_TOKEN",
        access_token,
    )

    refresh_token = str(
        response.get(
            "refresh_token",
            "",
        )
    ).strip()

    if refresh_token:
        update_env_value(
            ENV_FILE,
            "FYERS_REFRESH_TOKEN",
            refresh_token,
        )

    generated_at = (
        datetime.now()
        .astimezone()
        .isoformat(
            timespec="seconds"
        )
    )

    update_env_value(
        ENV_FILE,
        "FYERS_TOKEN_GENERATED_AT",
        generated_at,
    )


# ============================================================
# GUI
# ============================================================

class FyersTokenAssistant:
    """
    AQSD FYERS daily login assistant.
    """

    def __init__(
        self,
        root: tk.Tk,
    ) -> None:
        self.root = root

        self.client_id = ""
        self.secret_key = ""
        self.redirect_uri = ""
        self.authorization_url = ""

        self.status_variable = tk.StringVar(
            value="Ready. Load credentials to begin."
        )

        self.client_variable = tk.StringVar(
            value="Client ID: N/A"
        )

        self.redirect_variable = tk.StringVar(
            value="Redirect URI: N/A"
        )

        self.build_window()
        self.build_interface()

        self.load_credentials_into_interface()

    def build_window(
        self,
    ) -> None:
        """
        Configure the main window.
        """

        self.root.title(
            WINDOW_TITLE
        )

        self.root.geometry(
            f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}"
        )

        self.root.minsize(
            WINDOW_WIDTH,
            WINDOW_HEIGHT,
        )

        self.root.configure(
            bg=BACKGROUND
        )

    def build_interface(
        self,
    ) -> None:
        """
        Build the complete token-assistant interface.
        """

        main_frame = tk.Frame(
            self.root,
            bg=BACKGROUND,
        )

        main_frame.pack(
            fill="both",
            expand=True,
            padx=24,
            pady=20,
        )

        self.build_header(
            main_frame
        )

        self.build_credentials_panel(
            main_frame
        )

        self.build_authentication_panel(
            main_frame
        )

        self.build_status_panel(
            main_frame
        )

    def build_header(
        self,
        parent: tk.Widget,
    ) -> None:
        """
        Build title and security message.
        """

        header = tk.Frame(
            parent,
            bg=PANEL_BACKGROUND,
            highlightthickness=1,
            highlightbackground=BORDER_COLOR,
        )

        header.pack(
            fill="x",
            pady=(
                0,
                16,
            ),
        )

        title = tk.Label(
            header,
            text="AQSD FYERS DAILY TOKEN ASSISTANT",
            bg=PANEL_BACKGROUND,
            fg=TEXT_PRIMARY,
            font=(
                "Segoe UI",
                20,
                "bold",
            ),
            anchor="w",
        )

        title.pack(
            fill="x",
            padx=22,
            pady=(
                18,
                5,
            ),
        )

        subtitle = tk.Label(
            header,
            text=(
                "OFFICIAL FYERS LOGIN AND 2FA | "
                "NO PASSWORD, PIN OR OTP IS STORED"
            ),
            bg=PANEL_BACKGROUND,
            fg=TEXT_SECONDARY,
            font=(
                "Segoe UI",
                10,
                "bold",
            ),
            anchor="w",
        )

        subtitle.pack(
            fill="x",
            padx=22,
            pady=(
                0,
                18,
            ),
        )

    def build_credentials_panel(
        self,
        parent: tk.Widget,
    ) -> None:
        """
        Display the loaded app configuration.
        """

        panel = tk.Frame(
            parent,
            bg=CARD_BACKGROUND,
            highlightthickness=1,
            highlightbackground=BORDER_COLOR,
        )

        panel.pack(
            fill="x",
            pady=(
                0,
                16,
            ),
        )

        heading = tk.Label(
            panel,
            text="FYERS APP CONFIGURATION",
            bg=CARD_BACKGROUND,
            fg=TEXT_PRIMARY,
            font=(
                "Segoe UI",
                11,
                "bold",
            ),
            anchor="w",
        )

        heading.pack(
            fill="x",
            padx=18,
            pady=(
                15,
                8,
            ),
        )

        client_label = tk.Label(
            panel,
            textvariable=self.client_variable,
            bg=CARD_BACKGROUND,
            fg=TEXT_SECONDARY,
            font=(
                "Consolas",
                10,
            ),
            anchor="w",
        )

        client_label.pack(
            fill="x",
            padx=18,
            pady=3,
        )

        redirect_label = tk.Label(
            panel,
            textvariable=self.redirect_variable,
            bg=CARD_BACKGROUND,
            fg=TEXT_SECONDARY,
            font=(
                "Consolas",
                10,
            ),
            anchor="w",
        )

        redirect_label.pack(
            fill="x",
            padx=18,
            pady=(
                3,
                15,
            ),
        )

    def build_authentication_panel(
        self,
        parent: tk.Widget,
    ) -> None:
        """
        Build browser-login and auth-code controls.
        """

        panel = tk.Frame(
            parent,
            bg=PANEL_BACKGROUND,
            highlightthickness=1,
            highlightbackground=BORDER_COLOR,
        )

        panel.pack(
            fill="both",
            expand=True,
        )

        instruction = tk.Label(
            panel,
            text=(
                "1. Click OPEN FYERS LOGIN.\n"
                "2. Complete FYERS login and 2FA in the browser.\n"
                "3. After redirection, copy the complete browser URL.\n"
                "4. Paste it below and click GENERATE & SAVE TOKEN."
            ),
            bg=PANEL_BACKGROUND,
            fg=TEXT_SECONDARY,
            font=(
                "Segoe UI",
                10,
            ),
            justify="left",
            anchor="w",
        )

        instruction.pack(
            fill="x",
            padx=20,
            pady=(
                18,
                12,
            ),
        )

        login_button = tk.Button(
            panel,
            text="OPEN FYERS LOGIN",
            command=self.open_fyers_login,
            bg=ACCENT_BLUE,
            fg="#FFFFFF",
            activebackground="#4F8DE8",
            activeforeground="#FFFFFF",
            relief="flat",
            cursor="hand2",
            font=(
                "Segoe UI",
                10,
                "bold",
            ),
            padx=20,
            pady=9,
        )

        login_button.pack(
            anchor="w",
            padx=20,
            pady=(
                0,
                16,
            ),
        )

        input_label = tk.Label(
            panel,
            text="Redirected URL or auth_code:",
            bg=PANEL_BACKGROUND,
            fg=TEXT_PRIMARY,
            font=(
                "Segoe UI",
                10,
                "bold",
            ),
            anchor="w",
        )

        input_label.pack(
            fill="x",
            padx=20,
            pady=(
                0,
                6,
            ),
        )

        self.auth_input = tk.Text(
            panel,
            height=6,
            bg=CARD_BACKGROUND,
            fg=TEXT_PRIMARY,
            insertbackground=TEXT_PRIMARY,
            selectbackground=ACCENT_BLUE,
            relief="flat",
            wrap="word",
            font=(
                "Consolas",
                10,
            ),
            padx=10,
            pady=10,
        )

        self.auth_input.pack(
            fill="both",
            expand=True,
            padx=20,
            pady=(
                0,
                14,
            ),
        )

        button_frame = tk.Frame(
            panel,
            bg=PANEL_BACKGROUND,
        )

        button_frame.pack(
            fill="x",
            padx=20,
            pady=(
                0,
                18,
            ),
        )

        generate_button = tk.Button(
            button_frame,
            text="GENERATE & SAVE TOKEN",
            command=self.start_token_generation,
            bg=ACCENT_GREEN,
            fg="#111827",
            activebackground="#22C55E",
            activeforeground="#111827",
            relief="flat",
            cursor="hand2",
            font=(
                "Segoe UI",
                10,
                "bold",
            ),
            padx=20,
            pady=9,
        )

        generate_button.pack(
            side="left",
        )

        clear_button = tk.Button(
            button_frame,
            text="CLEAR",
            command=self.clear_auth_input,
            bg=ACCENT_ORANGE,
            fg="#111827",
            activebackground="#F59E0B",
            activeforeground="#111827",
            relief="flat",
            cursor="hand2",
            font=(
                "Segoe UI",
                10,
                "bold",
            ),
            padx=18,
            pady=9,
        )

        clear_button.pack(
            side="left",
            padx=(
                10,
                0,
            ),
        )

    def build_status_panel(
        self,
        parent: tk.Widget,
    ) -> None:
        """
        Build status and exit controls.
        """

        panel = tk.Frame(
            parent,
            bg=PANEL_BACKGROUND,
            highlightthickness=1,
            highlightbackground=BORDER_COLOR,
        )

        panel.pack(
            fill="x",
            pady=(
                14,
                0,
            ),
        )

        status = tk.Label(
            panel,
            textvariable=self.status_variable,
            bg=PANEL_BACKGROUND,
            fg=ACCENT_GREEN,
            font=(
                "Consolas",
                10,
                "bold",
            ),
            anchor="w",
        )

        status.pack(
            side="left",
            fill="x",
            expand=True,
            padx=18,
            pady=15,
        )

        exit_button = tk.Button(
            panel,
            text="EXIT",
            command=self.root.destroy,
            bg=ACCENT_RED,
            fg="#FFFFFF",
            activebackground="#E85A70",
            activeforeground="#FFFFFF",
            relief="flat",
            cursor="hand2",
            font=(
                "Segoe UI",
                10,
                "bold",
            ),
            padx=20,
            pady=8,
        )

        exit_button.pack(
            side="right",
            padx=18,
            pady=10,
        )

    def load_credentials_into_interface(
        self,
    ) -> None:
        """
        Load credentials and update the display.
        """

        try:
            (
                self.client_id,
                self.secret_key,
                self.redirect_uri,
            ) = load_fyers_credentials()

        except Exception as error:
            self.status_variable.set(
                f"Configuration error: {error}"
            )

            messagebox.showerror(
                "AQSD FYERS Configuration",
                (
                    f"{error}\n\n"
                    f"File: {ENV_FILE}"
                ),
            )
            return

        self.client_variable.set(
            "Client ID: "
            + mask_value(
                self.client_id
            )
        )

        self.redirect_variable.set(
            "Redirect URI: "
            + self.redirect_uri
        )

        self.status_variable.set(
            "Configuration loaded. Ready for FYERS login."
        )

    def open_fyers_login(
        self,
    ) -> None:
        """
        Generate and open the FYERS authorization URL.
        """

        try:
            if not self.client_id:
                (
                    self.client_id,
                    self.secret_key,
                    self.redirect_uri,
                ) = load_fyers_credentials()

            self.authorization_url = (
                generate_authorization_url(
                    client_id=self.client_id,
                    secret_key=self.secret_key,
                    redirect_uri=self.redirect_uri,
                )
            )

            opened = webbrowser.open(
                self.authorization_url,
                new=2,
            )

            if not opened:
                raise RuntimeError(
                    "The browser could not be opened automatically."
                )

        except Exception as error:
            self.status_variable.set(
                f"Could not open FYERS login: {error}"
            )

            messagebox.showerror(
                "AQSD FYERS Login",
                str(error),
            )
            return

        self.status_variable.set(
            "FYERS login opened. Complete login and paste the redirected URL."
        )

    def start_token_generation(
        self,
    ) -> None:
        """
        Start token generation in a background thread.
        """

        pasted_value = self.auth_input.get(
            "1.0",
            "end",
        ).strip()

        if not pasted_value:
            messagebox.showwarning(
                "AQSD FYERS Token",
                (
                    "Paste the complete redirected URL "
                    "or auth_code first."
                ),
            )
            return

        self.status_variable.set(
            "Generating and verifying FYERS access token..."
        )

        worker = threading.Thread(
            target=self.generate_and_save_token,
            args=(pasted_value,),
            daemon=True,
        )

        worker.start()

    def generate_and_save_token(
        self,
        pasted_value: str,
    ) -> None:
        """
        Exchange, verify and save the FYERS token.
        """

        try:
            auth_code = extract_auth_code(
                pasted_value
            )

            response = exchange_auth_code(
                auth_code=auth_code,
                client_id=self.client_id,
                secret_key=self.secret_key,
                redirect_uri=self.redirect_uri,
            )

            access_token = str(
                response["access_token"]
            ).strip()

            profile_response = verify_access_token(
                client_id=self.client_id,
                access_token=access_token,
            )

            save_token_response(
                response
            )

            profile_data = profile_response.get(
                "data",
                {}
            )

            if not isinstance(
                profile_data,
                dict,
            ):
                profile_data = {}

            display_name = str(
                profile_data.get(
                    "name",
                    "",
                )
            ).strip()

            success_message = (
                "FYERS token generated, verified and saved.\n\n"
                f"Updated file:\n{ENV_FILE}"
            )

            if display_name:
                success_message += (
                    f"\n\nConnected account: {display_name}"
                )

        except Exception as error:
            self.root.after(
                0,
                lambda message=str(error): (
                    self.show_generation_error(
                        message
                    )
                ),
            )
            return

        self.root.after(
            0,
            lambda message=success_message: (
                self.show_generation_success(
                    message
                )
            ),
        )

    def show_generation_success(
        self,
        message: str,
    ) -> None:
        """
        Display successful completion.
        """

        self.status_variable.set(
            "SUCCESS: New FYERS access token is active."
        )

        messagebox.showinfo(
            "AQSD FYERS Token",
            message,
        )

        self.clear_auth_input()

    def show_generation_error(
        self,
        message: str,
    ) -> None:
        """
        Display token-generation failure.
        """

        self.status_variable.set(
            f"FAILED: {message}"
        )

        messagebox.showerror(
            "AQSD FYERS Token",
            message,
        )

    def clear_auth_input(
        self,
    ) -> None:
        """
        Clear the redirected URL/auth-code box.
        """

        self.auth_input.delete(
            "1.0",
            "end",
        )


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    """
    Launch the AQSD FYERS Token Assistant.
    """

    root = tk.Tk()

    FyersTokenAssistant(
        root
    )

    root.mainloop()


if __name__ == "__main__":
    main()
