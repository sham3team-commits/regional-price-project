from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin


class StaffRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Every operator page: logged in AND a staff member."""

    def test_func(self):
        return self.request.user.is_staff
