from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("",                          views.main_dashboard,   name="index"),
    path("category/<slug:slug>/",     views.category_detail,  name="category"),
    path("compare/",                  views.signal_compare,   name="compare"),
    path("report/",                   views.overall_report,   name="overall_report"),
    path("geo/admdong/",              views.admdong_topojson, name="admdong_topojson"),
]
