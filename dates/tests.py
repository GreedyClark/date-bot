import hashlib
import hmac
import json
import random
import time
from datetime import date
from unittest.mock import patch
from urllib.parse import urlencode

from django.test import TestCase, override_settings

from .context import next_saturday
from .models import Couple, DateEvent, Member, Wish
from .picker import category_feedback, pick
from .services import JoinError, join_couple
from .telegram import validate_init_data
from .weather import is_bad_for_outdoor

TOKEN = "123:TEST"


def signed_init_data(user, token=TOKEN, auth_date=None):
    fields = {"auth_date": str(auth_date or int(time.time())), "user": json.dumps(user), "query_id": "q1"}
    check = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields)


class InitDataTests(TestCase):
    def test_valid_signature(self):
        user = validate_init_data(signed_init_data({"id": 1, "first_name": "Юрій"}), TOKEN)
        self.assertEqual(user["id"], 1)

    def test_wrong_token(self):
        self.assertIsNone(validate_init_data(signed_init_data({"id": 1}), "999:OTHER"))

    def test_tampered_user(self):
        data = signed_init_data({"id": 1}).replace("%22id%22%3A+1", "%22id%22%3A+2")
        self.assertIsNone(validate_init_data(data, TOKEN))

    def test_expired(self):
        old = int(time.time()) - 3 * 24 * 3600
        self.assertIsNone(validate_init_data(signed_init_data({"id": 1}, auth_date=old), TOKEN))


class WeatherTests(TestCase):
    def test_rain_is_bad(self):
        self.assertTrue(is_bad_for_outdoor({"rain": 80, "t_max": 15}))

    def test_frost_is_bad(self):
        self.assertTrue(is_bad_for_outdoor({"rain": 0, "t_max": -8}))

    def test_nice_day(self):
        self.assertFalse(is_bad_for_outdoor({"rain": 10, "t_max": 18}))

    def test_no_forecast(self):
        self.assertFalse(is_bad_for_outdoor(None))


class PickerTests(TestCase):
    def test_disliked_category_never_picked(self):
        prefs = {c: 0 for c in ["walk", "nature", "trip", "bike", "skate", "photo"]}
        rng = random.Random(1)
        for _ in range(200):
            idea = pick(prefs, [], [], {"where": "out"}, rng=rng)
            if idea:
                self.assertNotIn(idea["category"], prefs)

    def test_budget_filter(self):
        rng = random.Random(2)
        for _ in range(100):
            self.assertLessEqual(pick({}, [], [], {"budget": 1}, rng=rng)["budget"], 1)

    def test_bad_weather_pushes_outdoor_down(self):
        def outdoor_share(bad):
            rng = random.Random(3)
            picks = [pick({}, [], [], {}, bad_weather=bad, rng=rng) for _ in range(2000)]
            return sum(p["where"] == "out" for p in picks) / len(picks)
        self.assertLess(outdoor_share(True), outdoor_share(False) / 2)

    def test_wish_can_be_picked(self):
        rng = random.Random(4)
        wishes = [{"id": 7, "text": "Кінний клуб"}]
        picks = {pick({}, wishes, [], {}, rng=rng)["title"] for _ in range(300)}
        self.assertIn("Кінний клуб", picks)

    def test_feedback_changes_category_weight(self):
        fb = category_feedback([
            {"category": "boulder", "rating": 1},
            {"category": "boulder", "rating": 1},
            {"category": "cinema", "rating": -1},
        ])
        self.assertGreater(fb["boulder"], 1.5)
        self.assertLess(fb["cinema"], 1)


class CoupleTests(TestCase):
    def make(self, tg_id):
        return Member.objects.create(telegram_id=tg_id, name=str(tg_id), couple=Couple.objects.create())

    def test_join_and_partner(self):
        a, b = self.make(1), self.make(2)
        join_couple(b, a.couple.invite_code)
        b.refresh_from_db()
        self.assertEqual(a.partner, b)
        self.assertTrue(a.is_planner)
        self.assertFalse(b.is_planner)
        self.assertFalse(b.reminders)
        self.assertEqual(Couple.objects.count(), 1)

    def test_third_person_rejected(self):
        a, b, c = self.make(1), self.make(2), self.make(3)
        join_couple(b, a.couple.invite_code)
        with self.assertRaises(JoinError):
            join_couple(c, a.couple.invite_code)

    def test_own_code_rejected(self):
        a = self.make(1)
        with self.assertRaises(JoinError):
            join_couple(a, a.couple.invite_code)


class DatesTests(TestCase):
    def test_next_saturday(self):
        self.assertEqual(next_saturday(date(2026, 11, 23)), date(2026, 11, 28))
        self.assertEqual(next_saturday(date(2026, 11, 28)), date(2026, 12, 5))


@override_settings(TELEGRAM_BOT_TOKEN=TOKEN, WEBHOOK_SECRET="hook", CRON_SECRET="cron",
                   PUBLIC_URL="https://example.onrender.com", TELEGRAM_BOT_USERNAME="test_bot")
@patch("dates.weather.fetch_forecast", return_value={})
@patch("dates.telegram.requests.post")
class ApiTests(TestCase):
    def headers(self, user_id, name="Юрій"):
        return {"HTTP_X_INIT_DATA": signed_init_data({"id": user_id, "first_name": name})}

    def post(self, url, data, user_id):
        return self.client.post(url, json.dumps(data), content_type="application/json", **self.headers(user_id))

    def test_requires_telegram_auth(self, *_):
        self.assertEqual(self.client.get("/api/state/").status_code, 401)

    def test_full_flow(self, tg_post, _):
        state = self.client.get("/api/state/", **self.headers(1)).json()
        self.assertIn("t.me/test_bot?start=", state["invite_link"])
        code = state["invite_link"].split("start=")[1]

        update = {"message": {"chat": {"id": 2, "type": "private"}, "from": {"id": 2, "first_name": "Оля"}, "text": f"/start {code}"}}
        resp = self.client.post("/tg/webhook/", json.dumps(update), content_type="application/json", HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN="hook")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Member.objects.get(telegram_id=1).partner.telegram_id, 2)

        self.assertEqual(self.post("/api/prefs/", {"category": "boulder", "level": 2}, 2).status_code, 200)
        self.post("/api/wishes/", {"text": "Кінний клуб"}, 2)
        state = self.client.get("/api/state/", **self.headers(1)).json()
        self.assertEqual(state["partner_prefs"], {"boulder": 2})
        self.assertEqual(state["wishes"][0]["text"], "Кінний клуб")

        idea = self.post("/api/pick/", {"budget": 3}, 1).json()["idea"]
        self.assertIsNotNone(idea)

        wish_id = Wish.objects.get().id
        event = self.post("/api/dates/", {"title": "Кінний клуб", "date": "2026-11-28", "wish_id": wish_id}, 1).json()
        self.assertFalse(Wish.objects.exists())
        self.post(f"/api/dates/{event['id']}/rate/", {"rating": 1}, 1)
        self.assertEqual(DateEvent.objects.get().rating, 1)

        partner_state = self.client.get("/api/state/", **self.headers(2)).json()
        self.assertFalse(partner_state["me"]["is_planner"])
        self.assertEqual(self.post("/api/pick/", {}, 2).status_code, 403)
        self.assertEqual(self.post("/api/dates/", {"title": "x", "date": "2026-11-28"}, 2).status_code, 403)

    def test_partner_gets_only_invitation(self, tg_post, _):
        tg_post.return_value.json.return_value = {"ok": True}
        couple = Couple.objects.create()
        Member.objects.create(telegram_id=1, name="Юрій", couple=couple)
        Member.objects.create(telegram_id=2, name="Оля", couple=couple, is_planner=False, reminders=False)
        self.post("/api/wishes/", {"text": "Каток"}, 1)
        self.assertEqual(tg_post.call_count, 0)
        self.post("/api/dates/", {"title": "Боулінг", "date": "2099-01-03"}, 1)
        self.assertEqual(tg_post.call_count, 0)
        self.post("/api/dates/", {"title": "Балет", "date": "2099-01-03", "message": "Підеш зі мною на <балет>?"}, 1)
        self.assertEqual(tg_post.call_count, 1)
        sent = tg_post.call_args.kwargs["json"]
        self.assertEqual(sent["chat_id"], 2)
        self.assertEqual(sent["text"], "Підеш зі мною на &lt;балет&gt;?")
        self.post("/api/wishes/", {"text": "Кінний клуб"}, 2)
        self.assertEqual(tg_post.call_args.kwargs["json"]["chat_id"], 1)

    def test_webhook_rejects_wrong_secret(self, *_):
        resp = self.client.post("/tg/webhook/", "{}", content_type="application/json", HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN="nope")
        self.assertEqual(resp.status_code, 403)

    def test_cron_sends_to_paired_members(self, tg_post, _):
        tg_post.return_value.json.return_value = {"ok": True}
        couple = Couple.objects.create()
        Member.objects.create(telegram_id=1, name="Ю", couple=couple)
        Member.objects.create(telegram_id=2, name="О", couple=couple, is_planner=False)
        resp = self.client.post("/cron/weekly/", HTTP_X_CRON_SECRET="cron")
        self.assertEqual(resp.json()["sent"], 1)
