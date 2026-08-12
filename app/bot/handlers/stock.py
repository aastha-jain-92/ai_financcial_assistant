from telegram import Update
from telegram.ext import ContextTypes

from app.services.yahoo_service import YahooFinanceService


yahoo_service = YahooFinanceService()


async def price_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not context.args:

        await update.message.reply_text(
            "Usage:\n"
            "/price AAPL"
        )

        return

    ticker = context.args[0].upper()

    try:

        data = await yahoo_service.quote(
            ticker
        )

        price = data["current_price"]
        previous = data["previous_close"]

        if (
            price is not None
            and previous is not None
            and previous != 0
        ):

            change = price - previous

            change_percent = (
                change / previous
            ) * 100

        else:

            change = None
            change_percent = None

        message = (
            f"📈 {ticker}\n\n"
            f"Company: {data['company_name']}\n"
            f"Price: {price} {data['currency']}\n"
        )

        if change_percent is not None:

            emoji = (
                "🟢"
                if change_percent >= 0
                else "🔴"
            )

            message += (
                f"{emoji} "
                f"Change: {change:.2f} "
                f"({change_percent:.2f}%)\n"
            )

        message += (
            f"\nExchange: {data['exchange']}\n"
            f"Sector: {data['sector'] or 'N/A'}"
        )

        await update.message.reply_text(
            message
        )

    except Exception as exc:

        await update.message.reply_text(
            "❌ Unable to retrieve Yahoo "
            "Finance data right now."
        )

        print(
            f"Yahoo price error: {exc}"
        )