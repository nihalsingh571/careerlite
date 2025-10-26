from django.urls import re_path as url

from social.views import (
    google_login,
    github_login,
)

app_name = "social"

urlpatterns = [
    url(r"^google_login/$", google_login, name="google_login"),
    url(r"^github/$", github_login, name="github_login"),
]
