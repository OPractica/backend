
from rag.search import search_seats


def retrieve_seat_context(
    text: str,
    language: str = "ru",
) -> str:
    result = search_seats(text, language)

    if result["preferences"]["needs_clarification"]:
        return (
            "Запрос содержит неоднозначные предпочтения. "
            "Перед бронированием необходимо уточнение."
        )

    if not result["preferences"]["attributes"]:
        return (
            "Не удалось определить характеристики места. "
            "Нужно уточнить пожелания пользователя."
        )

    if not result["matches"]:
        return "Подходящие рабочие места не найдены."

    lines = [
        "Демонстрационные рабочие места "
        "(доступность не проверена):"
    ]

    for seat in result["matches"]:
        lines.append(
            f"- {seat['label']}, этаж {seat['floor']}, "
            f"зона {seat['zone']}: {seat['description']}"
        )

    return "\n".join(lines)
