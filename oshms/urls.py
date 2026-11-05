from django.conf import settings
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.urls import include, path, re_path
from django.views.static import serve

urlpatterns = [
    path("admin/", admin.site.urls),
    path("login/", auth_views.LoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    re_path(r"^media/(?P<path>.*)$", login_required(serve), {"document_root": settings.MEDIA_ROOT}),
    path("", include("audits.urls")),
]
