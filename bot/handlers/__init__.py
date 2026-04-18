import telebot

from bot.handlers.start import register_start_handlers
from bot.handlers.state_handler import register_state_handlers
from bot.handlers.admin import register_admin_handlers
from bot.handlers.user import register_user_handlers


def register_handlers(bot: telebot.TeleBot) -> None:
    # Order matters: command handlers first, then state-based, then feature handlers.
    register_start_handlers(bot)   # /start, /cancel  → always works
    register_state_handlers(bot)   # state machine    → intercepts messages when in a state
    register_admin_handlers(bot)   # admin callbacks
    register_user_handlers(bot)    # user callbacks
