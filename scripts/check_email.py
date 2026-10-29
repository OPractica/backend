import asyncio

from app.services.email import get_email_sender


async def main() -> None:
    await get_email_sender().send(
        to="test@example.com",
        subject="Test email",
        html="<h1>Hello!</h1><p>This is a test email from Office Booking.</p>",
    )
    print("Sent. Open http://localhost:8025")


if __name__ == "__main__":
    asyncio.run(main())
