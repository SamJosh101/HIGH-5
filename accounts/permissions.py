"""
Role-based access control helpers. EVERY protected view in HIGH 5 must use
one of these (function views: decorators; class-based views: mixins).

Behaviour:
  * Not logged in         -> redirected to the login page.
  * Logged in, wrong role -> HTTP 403 Forbidden.

Usage:
    from accounts.permissions import admin_required, passenger_required

    @admin_required
    def route_list(request): ...

    class RouteListView(AdminRequiredMixin, ListView): ...
"""

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied


def _role_required(check):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not check(request.user):
                raise PermissionDenied
            return view_func(request, *args, **kwargs)

        return login_required(wrapper)

    return decorator


#: Allow only ADMIN users.
admin_required = _role_required(lambda user: user.is_admin_role)

#: Allow only PASSENGER users.
passenger_required = _role_required(lambda user: user.is_passenger_role)


class _RoleRequiredMixin(LoginRequiredMixin):
    role_check = None

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not type(self).role_check(request.user):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


class AdminRequiredMixin(_RoleRequiredMixin):
    """Class-based view mixin: ADMIN users only."""

    @staticmethod
    def role_check(user):
        return user.is_admin_role


class PassengerRequiredMixin(_RoleRequiredMixin):
    """Class-based view mixin: PASSENGER users only."""

    @staticmethod
    def role_check(user):
        return user.is_passenger_role
