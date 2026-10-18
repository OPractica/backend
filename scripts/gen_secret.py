"""Print a random SECRET_KEY for .env.  Usage: uv run python -m scripts.gen_secret"""

import secrets

print(secrets.token_urlsafe(48))
