from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils import timezone
from datetime import timedelta

class ExpiringPasswordResetTokenGenerator(PasswordResetTokenGenerator):
    def _make_hash_value(self, user, timestamp):
        return f"{user.pk}{user.password}{timestamp}"

    def check_token(self, user, token):
        if not super().check_token(user, token):
            return False

        ts_b36 = token.split("-")[1]
        try:
            ts = PasswordResetTokenGenerator._num_from_timestamp(ts_b36)
        except Exception:
            return False

        token_time = self._datetime_from_timestamp(ts)
        if timezone.now() - token_time > timedelta(minutes=5):
            return False

        return True
