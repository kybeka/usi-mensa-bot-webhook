import pytest

from mensa_bot.delivery import DeliveryError, DiscordPublisher, TelegramPublisher


class FakeResponse:
    def __init__(self, status_code: int, body: dict | None = None) -> None:
        self.status_code = status_code
        self._body = body or {}

    def json(self) -> dict:
        return self._body


class FakeSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = responses
        self.posts: list[tuple[str, dict, float]] = []

    def post(self, url: str, *, json: dict, timeout: float) -> FakeResponse:
        self.posts.append((url, json, timeout))
        return self.responses.pop(0)


def test_telegram_sends_then_pins_returned_message() -> None:
    session = FakeSession(
        [
            FakeResponse(200, {"ok": True, "result": {"message_id": 42}}),
            FakeResponse(200, {"ok": True, "result": True}),
        ]
    )
    publisher = TelegramPublisher("token", "@usi_mensa", session=session)

    message_id = publisher.send_html("hello")
    publisher.pin(message_id)

    assert session.posts[0][0].endswith("/sendMessage")
    assert session.posts[1][0].endswith("/pinChatMessage")
    assert session.posts[1][1]["message_id"] == 42
    assert session.posts[1][1]["disable_notification"] is True


def test_telegram_pin_preflight_accepts_channel_editor() -> None:
    session = FakeSession(
        [
            FakeResponse(200, {"ok": True, "result": {"id": 123, "is_bot": True}}),
            FakeResponse(
                200,
                {
                    "ok": True,
                    "result": {
                        "status": "administrator",
                        "can_edit_messages": True,
                    },
                },
            ),
        ]
    )
    publisher = TelegramPublisher("token", "@usi_mensa", session=session)

    publisher.assert_can_pin()

    assert session.posts[0][0].endswith("/getMe")
    assert session.posts[1][0].endswith("/getChatMember")
    assert session.posts[1][1] == {"chat_id": "@usi_mensa", "user_id": 123}


def test_telegram_pin_preflight_rejects_missing_permission() -> None:
    session = FakeSession(
        [
            FakeResponse(200, {"ok": True, "result": {"id": 123, "is_bot": True}}),
            FakeResponse(
                200,
                {
                    "ok": True,
                    "result": {
                        "status": "administrator",
                        "can_edit_messages": False,
                    },
                },
            ),
        ]
    )
    publisher = TelegramPublisher("token", "@usi_mensa", session=session)

    with pytest.raises(DeliveryError, match="cannot pin messages"):
        publisher.assert_can_pin()


def test_discord_posts_payload() -> None:
    session = FakeSession([FakeResponse(204)])
    publisher = DiscordPublisher("https://discord.example/webhook", session=session)
    payload = {"content": "hello", "allowed_mentions": {"parse": []}}

    publisher.send(payload)

    assert session.posts[0][1] == payload
