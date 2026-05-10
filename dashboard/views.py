from django.shortcuts import render


def index(request):
    context = {
        "page_title": "수원시 시그널 리포트",
        "active_menu": "dashboard",
    }
    return render(request, "dashboard/index.html", context)
