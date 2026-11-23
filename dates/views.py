import hmac
import html
import json
import logging
from datetime import date
from functools import wraps

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from . import telegram as tg
from .bot import handle_update, weekly_reminders
from .context import next_saturday, pick_context, prefs_of
from .ideas import CATEGORIES, CATEGORY_IDS
from .models import DateEvent, Preference, Wish
from .picker import pick
from .services import get_or_create_member

log = logging.getLogger(__name__)


def secret_matches(given, expected):
    return bool(expected) and hmac.compare_digest(given or "", expected)


@csrf_exempt
@require_POST
def telegram_webhook(request):
    if not secret_matches(request.headers.get("X-Telegram-Bot-Api-Secret-Token"), settings.WEBHOOK_SECRET):
        return HttpResponse(status=403)
    try:
        handle_update(json.loads(request.body))
    except Exception:
        log.exception("Не вдалося обробити оновлення")
    return HttpResponse("ok")


@csrf_exempt
@require_POST
def cron_weekly(request):
    if not secret_matches(request.headers.get("X-Cron-Secret"), settings.CRON_SECRET):
        return HttpResponse(status=403)
    return JsonResponse({"sent": weekly_reminders()})


@require_GET
def health(request):
    return HttpResponse("ok")


@require_GET
def mini_app(request):
    return render(request, "dates/app.html", {"categories": CATEGORIES})


def telegram_user(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        user = tg.validate_init_data(request.headers.get("X-Init-Data", ""), settings.TELEGRAM_BOT_TOKEN)
        if not user:
            return JsonResponse({"error": "Відкрий застосунок через бота в Telegram"}, status=401)
        request.member, _ = get_or_create_member(user)
        return view(request, *args, **kwargs)
    return csrf_exempt(wrapper)


def planner_only(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.member.is_planner:
            return JsonResponse({"error": "Ця дія доступна лише тому, хто планує побачення"}, status=403)
        return view(request, *args, **kwargs)
    return wrapper


def body(request):
    try:
        return json.loads(request.body or "{}")
    except ValueError:
        return {}


def parse_day(value):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def event_json(e):
    return {"id": e.id, "title": e.title, "category": e.category, "date": e.date.isoformat(), "rating": e.rating}


def state_json(member):
    partner = member.partner
    couple = member.couple
    ctx = pick_context(member)
    return {
        "me": {"name": member.name, "reminders": member.reminders, "is_planner": member.is_planner},
        "partner": {"name": partner.name} if partner else None,
        "invite_link": None if partner else tg.invite_link(couple.invite_code),
        "my_prefs": prefs_of(member),
        "partner_prefs": prefs_of(partner) if partner else {},
        "wishes": [
            {"id": w.id, "text": w.text, "mine": w.author_id == member.id}
            for w in couple.wishes.all()
        ],
        "dates": [event_json(e) for e in couple.dates.all()],
        "next_saturday": ctx["day"].isoformat(),
        "weather": ctx["weather_text"],
    }


@require_GET
@telegram_user
def api_state(request):
    return JsonResponse(state_json(request.member))


@require_POST
@telegram_user
def api_pref(request):
    data = body(request)
    category, level = data.get("category"), data.get("level")
    if category not in CATEGORY_IDS:
        return JsonResponse({"error": "Невідома категорія"}, status=400)
    if level is None:
        Preference.objects.filter(member=request.member, category=category).delete()
    elif level in (0, 1, 2):
        Preference.objects.update_or_create(member=request.member, category=category, defaults={"level": level})
    else:
        return JsonResponse({"error": "Невідомий рівень"}, status=400)
    return JsonResponse({"ok": True})


@require_POST
@telegram_user
def api_wish_add(request):
    text = str(body(request).get("text", "")).strip()[:300]
    if not text:
        return JsonResponse({"error": "Напиши, що саме хочеш"}, status=400)
    wish = Wish.objects.create(couple=request.member.couple, author=request.member, text=text)
    partner = request.member.partner
    if partner and partner.is_planner:
        tg.send_message(partner.telegram_id, f"{html.escape(request.member.name)} хоче спробувати: {html.escape(text)}")
    return JsonResponse({"id": wish.id})


@require_POST
@telegram_user
def api_wish_delete(request, wish_id):
    Wish.objects.filter(pk=wish_id, couple=request.member.couple).delete()
    return JsonResponse({"ok": True})


@require_POST
@telegram_user
@planner_only
def api_pick(request):
    data = body(request)
    day = parse_day(data.get("date")) or next_saturday()
    ctx = pick_context(request.member, day)
    try:
        budget = int(data.get("budget", 3))
    except (TypeError, ValueError):
        budget = 3
    filters = {
        "budget": budget,
        "where": data.get("where", "any"),
        "time": data.get("time", "any"),
    }
    idea = pick(ctx["prefs"], ctx["wishes"], ctx["history"], filters, ctx["bad_weather"], data.get("exclude"))
    return JsonResponse({"idea": idea, "weather": ctx["weather_text"], "bad_weather": ctx["bad_weather"]})


@require_POST
@telegram_user
@planner_only
def api_date_add(request):
    data = body(request)
    title = str(data.get("title", "")).strip()[:300]
    day = parse_day(data.get("date"))
    if not title or not day:
        return JsonResponse({"error": "Потрібні назва і дата"}, status=400)
    category = data.get("category") if data.get("category") in CATEGORY_IDS else ""
    couple = request.member.couple
    event = DateEvent.objects.create(couple=couple, title=title, category=category, date=day, from_wish=bool(data.get("wish_id")))
    if data.get("wish_id"):
        Wish.objects.filter(pk=data["wish_id"], couple=couple).delete()
    message = str(data.get("message", "")).strip()[:2000]
    partner = request.member.partner
    if partner and message:
        tg.send_message(partner.telegram_id, html.escape(message))
    return JsonResponse(event_json(event))


@require_POST
@telegram_user
@planner_only
def api_date_rate(request, event_id):
    rating = body(request).get("rating")
    if rating not in (1, -1, None):
        return JsonResponse({"error": "Невідома оцінка"}, status=400)
    DateEvent.objects.filter(pk=event_id, couple=request.member.couple).update(rating=rating)
    return JsonResponse({"ok": True})


@require_POST
@telegram_user
@planner_only
def api_date_delete(request, event_id):
    DateEvent.objects.filter(pk=event_id, couple=request.member.couple).delete()
    return JsonResponse({"ok": True})
