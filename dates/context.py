from datetime import timedelta

from django.utils import timezone

from . import weather


def next_saturday(today=None):
    today = today or timezone.localdate()
    days = (5 - today.weekday()) % 7 or 7
    return today + timedelta(days=days)


def prefs_of(member):
    if not member:
        return {}
    return {p.category: p.level for p in member.preferences.all()}


def pick_context(member, day=None):
    partner = member.partner
    day = day or next_saturday()
    forecast = weather.day_weather(day)
    return {
        "prefs": prefs_of(partner) if partner else prefs_of(member),
        "wishes": [{"id": w.id, "text": w.text} for w in member.couple.wishes.all()],
        "history": [
            {"title": e.title, "category": e.category, "rating": e.rating}
            for e in member.couple.dates.all()
        ],
        "day": day,
        "bad_weather": weather.is_bad_for_outdoor(forecast),
        "weather_text": weather.describe(forecast),
    }
