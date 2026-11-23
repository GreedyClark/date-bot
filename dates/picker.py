import random

from .ideas import IDEAS

LEVEL_WEIGHT = {2: 6.0, 1: 2.0, None: 0.7}
WISH_WEIGHT = 5.0
BAD_WEATHER_FACTOR = 0.15
RECENT_FACTOR = 0.2


def category_feedback(history):
    factor = {}
    for event in history:
        if not event.get("category") or not event.get("rating"):
            continue
        step = 1.3 if event["rating"] > 0 else 0.7
        factor[event["category"]] = min(3.0, max(0.3, factor.get(event["category"], 1.0) * step))
    return factor


def candidates(prefs, wishes, filters):
    budget = filters.get("budget", 3)
    where = filters.get("where", "any")
    time = filters.get("time", "any")
    result = []
    for idea in IDEAS:
        if prefs.get(idea["category"]) == 0:
            continue
        if idea["budget"] > budget:
            continue
        if where != "any" and idea["where"] != where:
            continue
        if time != "any" and idea["time"] != time:
            continue
        result.append({**idea, "source": "idea"})
    for wish in wishes:
        result.append({
            "category": "",
            "title": wish["text"],
            "budget": None,
            "where": None,
            "time": None,
            "source": "wish",
            "wish_id": wish["id"],
        })
    return result


def weight(item, prefs, feedback, recent_titles, bad_weather):
    if item["source"] == "wish":
        w = WISH_WEIGHT
    else:
        w = LEVEL_WEIGHT[prefs.get(item["category"])]
        w *= feedback.get(item["category"], 1.0)
        if bad_weather and item["where"] == "out":
            w *= BAD_WEATHER_FACTOR
    if item["title"] in recent_titles:
        w *= RECENT_FACTOR
    return w


def pick(prefs, wishes, history, filters, bad_weather=False, exclude_title=None, rng=random):
    pool = candidates(prefs, wishes, filters)
    if exclude_title and len(pool) > 1:
        pool = [i for i in pool if i["title"] != exclude_title]
    if not pool:
        return None
    feedback = category_feedback(history)
    recent = {e["title"] for e in history[-5:]}
    weights = [weight(i, prefs, feedback, recent, bad_weather) for i in pool]
    return rng.choices(pool, weights=weights, k=1)[0]


def top_ideas(prefs, wishes, history, bad_weather=False, count=3, rng=random):
    chosen = []
    for _ in range(count * 5):
        idea = pick(prefs, wishes, history, {}, bad_weather, rng=rng)
        if idea and idea["title"] not in {c["title"] for c in chosen}:
            chosen.append(idea)
        if len(chosen) == count:
            break
    return chosen
