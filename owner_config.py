"""Owner (super-admin) bootstrap configuration.

All values come from environment variables (see .env.example).  Nothing in this
file is a secret and nothing is hard-coded: with no environment the owner
cannot be created.  The initial password is only read when the
`flask create-owner` command runs, is never logged, and the resulting account
is flagged ``must_change_password`` so the bootstrap value stops working at
first login.
"""
import os

MIN_PASSWORD_LENGTH = 12


class OwnerConfigError(ValueError):
    pass


def load_owner_settings() -> dict:
    email = (os.environ.get("OWNER_EMAIL") or "").strip().lower()
    name = (os.environ.get("OWNER_NAME") or "Academy Owner").strip()
    password = os.environ.get("OWNER_INITIAL_PASSWORD") or ""
    if not email or "@" not in email:
        raise OwnerConfigError("OWNER_EMAIL is missing or invalid (set it in .env).")
    if password and len(password) < MIN_PASSWORD_LENGTH:
        raise OwnerConfigError(
            f"OWNER_INITIAL_PASSWORD must be at least {MIN_PASSWORD_LENGTH} characters."
        )
    return {"email": email, "name": name, "password": password or None}
