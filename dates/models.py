import secrets

from django.db import models


def make_invite_code():
    return secrets.token_urlsafe(6)


class Couple(models.Model):
    invite_code = models.CharField(max_length=32, unique=True, default=make_invite_code)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        names = ", ".join(m.name for m in self.members.all())
        return f"Пара #{self.pk}: {names or 'порожня'}"


class Member(models.Model):
    telegram_id = models.BigIntegerField(unique=True)
    name = models.CharField(max_length=128, blank=True)
    couple = models.ForeignKey(Couple, on_delete=models.CASCADE, related_name="members")
    reminders = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name or str(self.telegram_id)

    @property
    def partner(self):
        return self.couple.members.exclude(pk=self.pk).first()


class Preference(models.Model):
    LOVE, OK, NO = 2, 1, 0
    LEVELS = [(LOVE, "Обожнюю"), (OK, "Можна"), (NO, "Не моє")]

    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="preferences")
    category = models.CharField(max_length=32)
    level = models.PositiveSmallIntegerField(choices=LEVELS)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["member", "category"], name="one_level_per_category")]


class Wish(models.Model):
    couple = models.ForeignKey(Couple, on_delete=models.CASCADE, related_name="wishes")
    author = models.ForeignKey(Member, on_delete=models.SET_NULL, null=True, related_name="wishes")
    text = models.CharField(max_length=300)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class DateEvent(models.Model):
    LIKED, MEH = 1, -1
    RATINGS = [(LIKED, "Сподобалось"), (MEH, "Так собі")]

    couple = models.ForeignKey(Couple, on_delete=models.CASCADE, related_name="dates")
    title = models.CharField(max_length=300)
    category = models.CharField(max_length=32, blank=True)
    date = models.DateField()
    rating = models.SmallIntegerField(choices=RATINGS, null=True, blank=True)
    from_wish = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["date"]
