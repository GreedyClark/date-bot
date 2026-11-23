from django.contrib import admin

from .models import Couple, DateEvent, Member, Preference, Wish


class MemberInline(admin.TabularInline):
    model = Member
    extra = 0


@admin.register(Couple)
class CoupleAdmin(admin.ModelAdmin):
    inlines = [MemberInline]


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ["name", "telegram_id", "couple", "reminders"]


@admin.register(DateEvent)
class DateEventAdmin(admin.ModelAdmin):
    list_display = ["title", "date", "couple", "rating"]


admin.site.register(Preference)
admin.site.register(Wish)
