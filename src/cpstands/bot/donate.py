"""Optional Telegram Stars donations (owner decision 2026-11-08): nothing is gated behind them.

``/donate`` (or the deep link ``/start donate`` from the Mini App) shows a few amounts; a tap
sends a Stars invoice. Nothing about the payer is stored: the charge id is logged so a refund
stays possible (``refundStarPayment``).
"""

from __future__ import annotations

import structlog
from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
    LabeledPrice,
    Message,
    PreCheckoutQuery,
)

from cpstands import metrics
from cpstands.bot import keyboards
from cpstands.bot.common import ensure_chat, say
from cpstands.bot.deps import Deps

log = structlog.get_logger(__name__)

AMOUNTS = (50, 100, 250, 500)
PREFIX = "don:"
PAYLOAD = "donate:"


def donate_keyboard(icons: bool) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                keyboards.button(f"{n} ⭐", f"{PREFIX}{n}", style="primary" if n == 100 else None)
                for n in AMOUNTS
            ]
        ]
    )


async def on_donate(message: Message, deps: Deps) -> None:
    chat = await ensure_chat(deps, message.chat)
    if chat is None:
        return
    await message.answer(say(deps, chat)("donate-text"), reply_markup=donate_keyboard(deps.icons))


async def on_start_donate(message: Message, command: CommandObject, deps: Deps) -> None:
    await on_donate(message, deps)


async def on_amount(callback: CallbackQuery, deps: Deps) -> None:
    raw = (callback.data or "")[len(PREFIX) :]
    if not raw.isdigit() or int(raw) not in AMOUNTS or callback.message is None:
        await callback.answer()
        return
    amount = int(raw)
    chat = await ensure_chat(deps, callback.message.chat)
    if chat is None:
        await callback.answer()
        return
    tr = say(deps, chat)
    await callback.answer()
    await callback.message.answer_invoice(
        title=tr("donate-title"),
        description=tr("donate-description"),
        payload=f"{PAYLOAD}{amount}",
        currency="XTR",
        prices=[LabeledPrice(label=tr("donate-label"), amount=amount)],
        provider_token="",
    )


async def on_pre_checkout(query: PreCheckoutQuery) -> None:
    ok = query.invoice_payload.startswith(PAYLOAD) and query.currency == "XTR"
    await query.answer(ok=ok, error_message=None if ok else "Unknown payment")


async def on_paid(message: Message, deps: Deps) -> None:
    payment = message.successful_payment
    if payment is None or not payment.invoice_payload.startswith(PAYLOAD):
        return
    log.info(
        "donation_received",
        stars=payment.total_amount,
        charge_id=payment.telegram_payment_charge_id,
    )
    metrics.DONATIONS.inc(payment.total_amount)
    chat = await ensure_chat(deps, message.chat)
    if chat is not None:
        await message.answer(say(deps, chat)("donate-thanks", stars=str(payment.total_amount)))


def create_donate_router() -> Router:
    router = Router(name="donate")
    router.message.register(on_start_donate, CommandStart(deep_link=True, magic=F.args == "donate"))
    router.message.register(on_donate, Command("donate"))
    router.callback_query.register(on_amount, F.data.startswith(PREFIX))
    router.pre_checkout_query.register(on_pre_checkout)
    router.message.register(on_paid, F.successful_payment)
    return router
