from app.services.rag.search import search_seats


def retrieve_seat_context(
    text: str,
    language: str = "ru",
) -> str:
    """Build context about matching desks for the AI agent."""

    result = search_seats(text, language)

    preferences = result["preferences"]
    matches = result["matches"]

    if preferences["needs_clarification"]:
        return (
            "Запрос содержит неоднозначные предпочтения. "
            "Перед бронированием необходимо уточнение."
        )

    if not preferences["attributes"]:
        return (
            "Не удалось определить характеристики рабочего места. "
            "Необходимо уточнить пожелания пользователя."
        )

    if not matches:
        return "В демонстрационных данных подходящие рабочие места не найдены."

    lines = [
        (
            "Найдены следующие демонстрационные рабочие места "
            "(реальная доступность не проверена):"
        )
    ]

    for seat in matches:
        lines.append(
            f"- {seat['label']}, "
            f"этаж {seat['floor']}, "
            f"зона {seat['zone']}: "
            f"{seat['description']}"
        )

    return "\n".join(lines)
