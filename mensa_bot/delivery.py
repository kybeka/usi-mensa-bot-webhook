from typing import Any

import requests


class DeliveryError(RuntimeError):
    pass


class TelegramPublisher:
    def __init__(
        self,
        bot_token: str,
        chat_id: str,
        *,
        session: requests.Session | None = None,
        timeout_seconds: float = 45,
    ) -> None:
        self._base_url = f"https://api.telegram.org/bot{bot_token}"
        self._chat_id = chat_id
        self._session = session or requests.Session()
        self._timeout_seconds = timeout_seconds

    def _call(self, method: str, body: dict[str, Any]) -> Any:
        try:
            response = self._session.post(
                f"{self._base_url}/{method}",
                json=body,
                timeout=self._timeout_seconds,
            )
        except requests.RequestException as exc:
            raise DeliveryError(f"Telegram {method} request failed: {exc}") from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise DeliveryError(
                f"Telegram {method} returned HTTP {response.status_code} with invalid JSON."
            ) from exc
        if response.status_code >= 400 or not data.get("ok"):
            description = data.get("description", "unknown Telegram error")
            raise DeliveryError(
                f"Telegram {method} failed with HTTP {response.status_code}: {description}"
            )
        return data.get("result")

    def send_html(self, text: str) -> int:
        result = self._call(
            "sendMessage",
            {
                "chat_id": self._chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
        )
        if not isinstance(result, dict) or not isinstance(result.get("message_id"), int):
            raise DeliveryError("Telegram sendMessage did not return a message ID.")
        return result["message_id"]

    def pin(self, message_id: int) -> None:
        self._call(
            "pinChatMessage",
            {
                "chat_id": self._chat_id,
                "message_id": message_id,
                "disable_notification": True,
            },
        )


class DiscordPublisher:
    def __init__(
        self,
        webhook_url: str,
        *,
        session: requests.Session | None = None,
        timeout_seconds: float = 45,
    ) -> None:
        self._webhook_url = webhook_url
        self._session = session or requests.Session()
        self._timeout_seconds = timeout_seconds

    def send(self, payload: dict[str, Any]) -> None:
        try:
            response = self._session.post(
                self._webhook_url,
                json=payload,
                timeout=self._timeout_seconds,
            )
        except requests.RequestException as exc:
            raise DeliveryError(f"Discord webhook request failed: {exc}") from exc
        if response.status_code not in {200, 204}:
            raise DeliveryError(f"Discord webhook returned HTTP {response.status_code}.")
