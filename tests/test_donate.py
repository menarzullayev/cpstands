"""Optional Stars donations: amounts, the invoice, the checkout answer and the thanks."""

from __future__ import annotations

from datetime import UTC, datetime

from aiogram.types import Chat, Message, PreCheckoutQuery, SuccessfulPayment, Update, User

from cpstands import metrics
from tests.test_bot import I18N, PRIVATE, Harness
from tests.test_bot import harness as harness  # the shared fixture

USER = User(id=PRIVATE, is_bot=False, first_name="U")


def checkout(update_id: int, payload: str, currency: str = "XTR") -> Update:
    query = PreCheckoutQuery(
        id=f"pc{update_id}",
        from_user=USER,
        currency=currency,
        total_amount=100,
        invoice_payload=payload,
    )
    return Update(update_id=update_id, pre_checkout_query=query)


def paid(update_id: int, payload: str, stars: int) -> Update:
    message = Message(
        message_id=update_id,
        date=datetime.now(UTC),
        chat=Chat(id=PRIVATE, type="private"),
        from_user=USER,
        successful_payment=SuccessfulPayment(
            currency="XTR",
            total_amount=stars,
            invoice_payload=payload,
            telegram_payment_charge_id="charge-1",
            provider_payment_charge_id="",
        ),
    )
    return Update(update_id=update_id, message=message)


def buttons(call: dict[str, object]) -> list[str]:
    rows = call["reply_markup"]["inline_keyboard"]  # type: ignore[index]
    return [b["callback_data"] for row in rows for b in row]


async def test_donate_offers_four_amounts(harness: Harness) -> None:
    await harness.say(PRIVATE, PRIVATE, "/donate")
    call = harness.session.sent()[-1]
    assert call["text"] == I18N.t(None, "donate-text")
    assert buttons(call) == ["don:50", "don:100", "don:250", "don:500"]


async def test_the_mini_app_link_opens_the_same_menu(harness: Harness) -> None:
    await harness.say(PRIVATE, PRIVATE, "/start donate")
    assert harness.session.last_text() == I18N.t(None, "donate-text")


async def test_plain_start_is_not_taken_for_donate(harness: Harness) -> None:
    await harness.say(PRIVATE, PRIVATE, "/start")
    assert harness.session.last_text() != I18N.t(None, "donate-text")


async def test_a_tap_sends_a_stars_invoice(harness: Harness) -> None:
    await harness.say(PRIVATE, PRIVATE, "/donate")
    await harness.tap(PRIVATE, PRIVATE, "don:100")
    (invoice,) = harness.session.sent("SendInvoice")
    assert invoice["currency"] == "XTR"
    assert invoice["payload"] == "donate:100"
    assert invoice["prices"] == [{"label": I18N.t(None, "donate-label"), "amount": 100}]
    assert invoice["provider_token"] == ""


async def test_an_unknown_amount_sends_nothing(harness: Harness) -> None:
    await harness.tap(PRIVATE, PRIVATE, "don:7")
    await harness.tap(PRIVATE, PRIVATE, "don:abc")
    assert harness.session.sent("SendInvoice") == []


async def test_checkout_accepts_only_our_stars_payloads(harness: Harness) -> None:
    await harness.feed(checkout(harness.uid(), "donate:100"))
    await harness.feed(checkout(harness.uid(), "something-else"))
    await harness.feed(checkout(harness.uid(), "donate:100", currency="USD"))
    answers = [c["ok"] for c in harness.session.sent("AnswerPreCheckoutQuery")]
    assert answers == [True, False, False]


async def test_a_payment_is_thanked_and_counted(harness: Harness) -> None:
    before = metrics.DONATIONS.value()
    await harness.feed(paid(harness.uid(), "donate:250", 250))
    assert harness.session.last_text() == I18N.t(None, "donate-thanks", stars="250")
    assert metrics.DONATIONS.value() == before + 250


async def test_a_foreign_payment_is_ignored(harness: Harness) -> None:
    await harness.feed(paid(harness.uid(), "other:1", 5))
    assert harness.session.sent() == []
