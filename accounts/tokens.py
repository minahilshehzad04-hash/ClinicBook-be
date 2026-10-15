from django.contrib.auth.tokens import PasswordResetTokenGenerator


class EmailVerificationTokenGenerator(PasswordResetTokenGenerator):
    """
    Same signed, expiring token Django uses for password resets, but the hash
    includes `is_email_verified`. Once the user verifies, the token stops
    working, so a link can only be used once.
    Expiry = settings.PASSWORD_RESET_TIMEOUT (seconds, default 3 days).
    """

    def _make_hash_value(self, user, timestamp):
        return f"{user.pk}{user.email}{user.is_email_verified}{timestamp}"


email_token_generator = EmailVerificationTokenGenerator()
