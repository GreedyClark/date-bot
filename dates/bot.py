import html

from . import telegram as tg
from .models import Member
from .picker import top_ideas
from .services import JoinError, get_or_create_member, join_couple, leave_couple
from .context import pick_context

HELP = (
    "Я допомагаю вигадати, куди піти на побачення.\n\n"
    "/app — відкрити застосунок\n"
    "/idea — три ідеї на найближчі вихідні\n"
    "/invite — посилання для твоєї половинки\n"
    "/remind — увімкнути або вимкнути нагадування в четвер\n"
    "/leave — вийти з пари"
)


def handle_update(update):
    message = update.get("message")
    if not message or "text" not in message or "from" not in message:
        return
    if message["chat"].get("type") != "private":
        return
    chat_id = message["chat"]["id"]
    member, created = get_or_create_member(message["from"])
    text = message["text"].strip()
    command, _, arg = text.partition(" ")
    command = command.split("@")[0].lower()

    if command == "/start":
        start(chat_id, member, created, arg.strip())
    elif command == "/app":
        tg.send_message(chat_id, "Тисни кнопку нижче.", tg.app_button())
    elif command == "/idea":
        send_ideas(member)
    elif command == "/invite":
        send_invite(chat_id, member)
    elif command == "/remind":
        member.reminders = not member.reminders
        member.save(update_fields=["reminders"])
        state = "увімкнено" if member.reminders else "вимкнено"
        tg.send_message(chat_id, f"Нагадування в четвер {state}.")
    elif command == "/leave":
        if leave_couple(member):
            tg.send_message(chat_id, "Ти вийшов з пари. Твої вподобання збереглися.")
        else:
            tg.send_message(chat_id, "Ти поки не в парі.")
    else:
        tg.send_message(chat_id, HELP, tg.app_button())


def start(chat_id, member, created, code):
    if code:
        try:
            couple = join_couple(member, code)
        except JoinError as exc:
            tg.send_message(chat_id, str(exc))
            return
        partner = couple.members.exclude(pk=member.pk).first()
        tg.send_message(chat_id, f"Готово, ви з {html.escape(partner.name)} тепер пара. Відміть, що тобі подобається.", tg.app_button())
        tg.send_message(partner.telegram_id, f"{html.escape(member.name)} тепер з тобою в парі. Загляньте в застосунок.", tg.app_button())
        return
    greeting = "Привіт!" if created else "З поверненням!"
    tg.send_message(chat_id, f"{greeting} {HELP}", tg.app_button())
    if not member.partner:
        send_invite(chat_id, member)


def send_invite(chat_id, member):
    if member.partner:
        tg.send_message(chat_id, f"Ви вже в парі з {html.escape(member.partner.name)}.")
        return
    link = tg.invite_link(member.couple.invite_code)
    tg.send_message(chat_id, f"Перешли це посилання своїй половинці, і бот вас з'єднає:\n{link}")


def ideas_text(member, ctx, ideas):
    lines = ["<b>Ідеї на вихідні</b>"]
    if ctx["weather_text"]:
        lines.append(f"Прогноз на {ctx['day'].strftime('%d.%m')}: {ctx['weather_text']}")
    for i, idea in enumerate(ideas, 1):
        mark = " (з вашого списку бажань)" if idea["source"] == "wish" else ""
        lines.append(f"{i}. {html.escape(idea['title'])}{mark}")
    return "\n".join(lines)


def send_ideas(member):
    ctx = pick_context(member)
    ideas = top_ideas(ctx["prefs"], ctx["wishes"], ctx["history"], ctx["bad_weather"])
    if not ideas:
        tg.send_message(member.telegram_id, "Поки нема з чого обирати. Відміть вподобання в застосунку.", tg.app_button())
        return
    tg.send_message(member.telegram_id, ideas_text(member, ctx, ideas), tg.app_button("Обрати в застосунку"))


def weekly_reminders():
    sent = 0
    for member in Member.objects.filter(reminders=True).select_related("couple"):
        if not member.partner:
            continue
        send_ideas(member)
        sent += 1
    return sent
