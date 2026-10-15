from sqlalchemy.ext.asyncio import AsyncSession

from app.services.rag.search import SearchMode, search_seats


def render_seat_context(result: dict) -> str:
    preferences = result["preferences"]

    if preferences["needs_clarification"]:
        return "Some preferences are ambiguous. Ask for clarification."

    if not preferences["attributes"]:
        return "No seat preferences were identified. Ask for details."

    if not result["matches"]:
        return "No matching seats were found."

    source = result["data_source"]
    lines = [
        f"Seat candidates from {source} data.",
        "Availability has NOT been checked.",
        "No booking has been created.",
    ]

    for seat in result["matches"]:
        lines.append(
            f"- ID {seat.get('id', 'unknown')}: "
            f"{seat.get('label', 'unknown')}, "
            f"floor {seat.get('floor', 'unknown')}, "
            f"zone {seat.get('zone', 'unknown')}"
        )

    return "\n".join(lines)


async def retrieve_seat_context(
    text: str,
    language: str = "ru",
    session: AsyncSession | None = None,
    mode: SearchMode = "database",
) -> str:
    result = await search_seats(
        text=text,
        language=language,
        session=session,
        mode=mode,
    )
    return render_seat_context(result)
