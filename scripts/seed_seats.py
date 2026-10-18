"""Create the seats from the floor plan in the current database.  Usage: uv run python -m scripts.seed_seats"""

import asyncio

from app.seed import seed_seats

if __name__ == "__main__":
    asyncio.run(seed_seats())
    print("Seats are in the database.")
