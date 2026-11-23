from django.urls import path

from . import views

urlpatterns = [
    path("health/", views.health),
    path("app/", views.mini_app),
    path("tg/webhook/", views.telegram_webhook),
    path("cron/weekly/", views.cron_weekly),
    path("api/state/", views.api_state),
    path("api/prefs/", views.api_pref),
    path("api/wishes/", views.api_wish_add),
    path("api/wishes/<int:wish_id>/delete/", views.api_wish_delete),
    path("api/pick/", views.api_pick),
    path("api/dates/", views.api_date_add),
    path("api/dates/<int:event_id>/rate/", views.api_date_rate),
    path("api/dates/<int:event_id>/delete/", views.api_date_delete),
]
