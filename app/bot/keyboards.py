# app/telegram/keyboards.py

from telegram import ReplyKeyboardMarkup, KeyboardButton


def role_keyboard():

    keyboard = [
        [KeyboardButton("Investor")],
        [KeyboardButton("Analyst")],
        [KeyboardButton("Founder")],
        [KeyboardButton("Student")],
        [KeyboardButton("Finance Professional")],
        [KeyboardButton("Skip")]
    ]

    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True
    )


def market_keyboard():

    keyboard = [
        ["US Market"],
        ["Indian Market"],
        ["Global"],
        ["Skip"]
    ]

    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True
    )