from django.db import transaction

from .models import Couple, Member


def full_name(user):
    return " ".join(filter(None, [user.get("first_name"), user.get("last_name")])) or user.get("username", "")


def get_or_create_member(user):
    member = Member.objects.filter(telegram_id=user["id"]).select_related("couple").first()
    name = full_name(user)
    if member:
        if name and member.name != name:
            member.name = name
            member.save(update_fields=["name"])
        return member, False
    couple = Couple.objects.create()
    return Member.objects.create(telegram_id=user["id"], name=name, couple=couple), True


class JoinError(Exception):
    pass


@transaction.atomic
def join_couple(member, code):
    target = Couple.objects.select_for_update().filter(invite_code=code).first()
    if not target:
        raise JoinError("Посилання недійсне. Попроси надіслати нове.")
    if target.pk == member.couple_id:
        raise JoinError("Це твоє власне посилання. Надішли його своїй половинці.")
    if target.members.count() >= 2:
        raise JoinError("У цій парі вже двоє.")
    old = member.couple
    if old.members.count() > 1:
        raise JoinError("Ти вже в парі. Спершу вийди з неї командою /leave.")
    member.couple = target
    member.save(update_fields=["couple"])
    old.delete()
    return target


@transaction.atomic
def leave_couple(member):
    if member.couple.members.count() < 2:
        return False
    member.couple = Couple.objects.create()
    member.save(update_fields=["couple"])
    return True
