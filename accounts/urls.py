from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("register/", views.register, name="register"),
    path("verify-email/", views.resend_verification, name="resend_verification"),
    path("verify-email/sent/", views.verification_sent, name="verification_sent"),
    path("verify-email/<str:token>/", views.verify_email, name="verify_email"),
    path("login/", views.HighFiveLoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),  # POST only (Django 5+)
    path("welcome/", views.after_login, name="after_login"),
    path("profile/", views.profile, name="profile"),
    path("password/change/", views.password_change, name="password_change"),
    path("password/reset/", views.password_reset, name="password_reset"),
    path("password/reset/sent/", views.password_reset_done, name="password_reset_done"),
    path("password/reset/<uidb64>/<token>/", views.password_reset_confirm, name="password_reset_confirm"),
    path("password/reset/complete/", views.password_reset_complete, name="password_reset_complete"),
]
