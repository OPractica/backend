"""Оценка агента на наборе сценариев: процент успеха, время, запросы и токены.

Нужна отдельная база с именем на _eval: она пересоздаётся при каждом сценарии
    docker exec office_db psql -U office -d postgres -c "create database office_eval"
    DATABASE_URL=postgresql+asyncpg://office:office@localhost:5432/office_eval \\
        uv run python -m scripts.eval_agent
Параметры: --only <часть названия или категория>, --delay <секунды>, --json <файл>.
Модель берётся из LLM_MODEL (.env), её можно переопределить в команде запуска.
"""

import argparse
import asyncio
import json
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta

from langchain_core.exceptions import ModelRateLimitError
from langchain_core.messages import BaseMessage
from sqlalchemy import select

from app.ai.agent import build_agent
from app.ai.llm import MODEL_ERRORS
from app.ai.tools import OFFICE_TZ
from app.core.db import SessionLocal, engine
from app.models.database import Booking
from scripts.eval_cases import CASES, HOLDOUT, ROMANIAN_WORDS, Case, Step

USER_ID = 1
TECHNICAL_WORDS = {
    "window",
    "quiet",
    "open",
    "cozy",
    "monitors",
    "dock",
    "true",
    "false",
}
REFUSAL_MARKERS = (
    "только с бронированием",
    "only help with booking",
    "doar cu rezervarea",
)


@dataclass
class StepResult:
    text: str
    reply: str = ""
    tools: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    seconds: float = 0.0
    requests: int = 0
    tokens_in: int = 0
    tokens_out: int = 0


@dataclass
class CaseResult:
    name: str
    category: str
    known_gap: str | None
    steps: list[StepResult] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems and all(not step.problems for step in self.steps)


def eval_now(real_now: datetime | None = None) -> datetime:
    """Фиксированное «сейчас» для оценки: ближайшая среда, 10:00, в будущем.

    Тогда «завтра» это всегда четверг, и результат не зависит от дня запуска
    (в выходные агент справедливо отвечает, что офис закрыт).
    """
    real = real_now or datetime.now(OFFICE_TZ)
    days = (2 - real.weekday()) % 7 or 7
    target = real + timedelta(days=days)
    return target.replace(hour=10, minute=0, second=0, microsecond=0)


def lang_of(text: str) -> str:
    """Грубо определить язык ответа: ru (кириллица), ro (румынские слова и буквы), иначе en."""
    # Технические токены (7-A03, quiet=True, числа) и названия зон не показывают язык ответа
    words = [
        w for w in text.split() if not any(ch.isdigit() or ch in "=*_" for ch in w)
    ]
    words = [w for w in words if w.strip(".,:;!?()-—").lower() not in TECHNICAL_WORDS]
    letters = [ch for ch in " ".join(words) if ch.isalpha()]
    cyrillic = sum("а" <= ch.lower() <= "я" or ch.lower() == "ё" for ch in letters)
    if letters and cyrillic / len(letters) > 0.5:
        return "ru"
    lowered = text.lower()
    words = {word.strip(".,:;!?()-") for word in lowered.split()}
    if words & ROMANIAN_WORDS or any(ch in lowered for ch in "ăâîșț"):
        return "ro"
    return "en"


def next_weekday(today: date, weekday: int) -> date:
    """Ближайший день недели (0 = понедельник) строго после сегодняшнего."""
    return today + timedelta(days=(weekday - today.weekday() - 1) % 7 + 1)


def problems_for(step: Step, calls: list[dict], reply: str, today: date) -> list[str]:
    """Сравнить, что сделал агент на реплике, с ожиданиями сценария."""
    names = [call["name"] for call in calls]
    problems = [f"не вызван {tool}" for tool in step.tools if tool not in names]
    problems += [
        f"нельзя было вызывать {tool}" for tool in step.forbid if tool in names
    ]
    if step.no_tools and names:
        problems.append(f"инструменты вызывать не нужно, вызваны: {names}")
    if step.refusal and not (
        any(marker in reply for marker in REFUSAL_MARKERS) and len(reply) < 200
    ):
        problems.append("ожидалась короткая фраза-отказ")
    if step.lang and lang_of(reply) != step.lang:
        problems.append(f"ответ не на языке {step.lang}")
    expected = None
    if step.search_day is not None:
        expected = today + timedelta(days=step.search_day)
    elif step.search_weekday is not None:
        expected = next_weekday(today, step.search_weekday)
    if expected is not None:
        starts = [
            call["args"].get("start", "")[:10]
            for call in calls
            if call["name"] == "search_free_seats"
        ]
        if expected.isoformat() not in starts:
            problems.append(f"поиск не на {expected} (было: {starts})")
    return problems


def usage_of(messages: list[BaseMessage]) -> tuple[int, int, int]:
    requests = tokens_in = tokens_out = 0
    for message in messages:
        usage = getattr(message, "usage_metadata", None)
        if usage:
            requests += 1
            tokens_in += usage.get("input_tokens", 0)
            tokens_out += usage.get("output_tokens", 0)
    return requests, tokens_in, tokens_out


async def reset_db() -> None:
    process = await asyncio.create_subprocess_exec(
        "uv",
        "run",
        "python",
        "-m",
        "scripts.dev_reset_db",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await process.communicate()
    if process.returncode != 0:
        sys.exit(f"Не удалось пересоздать базу:\n{stderr.decode()[-400:]}")


async def read_bookings() -> list[Booking]:
    async with SessionLocal() as session:
        result = await session.execute(select(Booking).order_by(Booking.id))
        return list(result.scalars().all())


async def run_step(
    agent, messages: list, step: Step, today: date
) -> tuple[list, StepResult]:
    result = StepResult(text=step.text)
    known = len(messages)
    messages = [*messages, {"role": "user", "content": step.text}]
    started = time.perf_counter()
    for attempt in range(2):
        try:
            output = await agent.ainvoke({"messages": messages})
            break
        except ModelRateLimitError:
            if attempt == 1:
                result.problems.append("лимит запросов модели")
                return messages[:-1], result
            await asyncio.sleep(35)
        except MODEL_ERRORS as error:
            result.problems.append(f"ошибка модели: {type(error).__name__}")
            return messages[:-1], result
    result.seconds = time.perf_counter() - started
    messages = output["messages"]
    new = messages[known:]
    calls = [
        call for message in new for call in (getattr(message, "tool_calls", None) or [])
    ]
    result.tools = [call["name"] for call in calls]
    result.reply = messages[-1].text.replace("\n", " ")
    result.requests, result.tokens_in, result.tokens_out = usage_of(new)
    result.problems += problems_for(step, calls, result.reply, today)
    return messages, result


async def run_case(case: Case, delay: float) -> CaseResult:
    now = eval_now()
    today = now.date()
    outcome = CaseResult(case.name, case.category, case.known_gap)
    if case.reset:
        await reset_db()
    agent = build_agent(USER_ID, now=now)
    messages: list = []
    for step in case.steps:
        messages, step_result = await run_step(agent, messages, step, today)
        outcome.steps.append(step_result)
        await asyncio.sleep(delay)
    if case.bookings is not None:
        bookings = await read_bookings()
        statuses = tuple(b.status for b in bookings)
        if statuses != case.bookings:
            outcome.problems.append(
                f"брони в базе {statuses}, ожидалось {case.bookings}"
            )
        elif bookings and (
            case.booking_day is not None or case.booking_hour is not None
        ):
            start = bookings[0].starts_at.astimezone(OFFICE_TZ)
            wanted_day = today + timedelta(days=case.booking_day or 0)
            if case.booking_day is not None and start.date() != wanted_day:
                outcome.problems.append(
                    f"бронь на {start.date()}, ожидалось {wanted_day}"
                )
            if case.booking_hour is not None and start.hour != case.booking_hour:
                outcome.problems.append(
                    f"бронь в {start.hour}:00, ожидалось {case.booking_hour}:00"
                )
    return outcome


def print_report(results: list[CaseResult]) -> None:
    counted = [r for r in results if not r.known_gap]
    gaps = [r for r in results if r.known_gap]
    print("\n==== ИТОГ ====")
    for category in dict.fromkeys(r.category for r in counted):
        group = [r for r in counted if r.category == category]
        print(f"  {category:<9} {sum(r.ok for r in group)} из {len(group)}")
    passed = sum(r.ok for r in counted)
    percent = 100 * passed // max(len(counted), 1)
    print(f"  ВСЕГО     {passed} из {len(counted)} ({percent}%)")
    for r in gaps:
        state = "пройден" if r.ok else "не пройден"
        print(f"  известное ограничение: {r.name}: {state} ({r.known_gap})")
    steps = [s for r in results for s in r.steps if s.seconds]
    if steps:
        print(
            f"  реплик {len(steps)} | запросов к модели {sum(s.requests for s in steps)} | "
            f"токенов вход {sum(s.tokens_in for s in steps)}, "
            f"выход {sum(s.tokens_out for s in steps)} | "
            f"среднее время реплики {sum(s.seconds for s in steps) / len(steps):.1f} с"
        )


def save_json(path: str, results: list[CaseResult]) -> None:
    with open(path, "w", encoding="utf-8") as file:
        json.dump([asdict(r) for r in results], file, ensure_ascii=False, indent=2)


async def main(
    only: str | None, delay: float, json_path: str | None, holdout: bool
) -> None:
    if not (engine.url.database or "").endswith("_eval"):
        sys.exit(
            "Отказ: оценка пересоздаёт базу. Используйте базу с именем на _eval "
            "(см. описание файла)."
        )
    pool = HOLDOUT if holdout else CASES
    cases = [c for c in pool if not only or only in c.name or only == c.category]
    if not cases:
        sys.exit(f"Нет сценариев по фильтру {only!r}")
    results: list[CaseResult] = []
    for case in cases:
        result = await run_case(case, delay)
        results.append(result)
        seconds = sum(s.seconds for s in result.steps)
        status = "OK  " if result.ok else "FAIL"
        print(f"{status} [{case.category}] {case.name} ({seconds:.1f} с)", flush=True)
        for step in result.steps:
            for problem in step.problems:
                print(f"       · «{step.text[:40]}»: {problem}", flush=True)
            if step.problems and step.reply:
                print(f"         ответ: {step.reply[:160]}", flush=True)
        for problem in result.problems:
            print(f"       · {problem}", flush=True)
    print_report(results)
    if json_path:
        await asyncio.to_thread(save_json, json_path, results)
    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Оценка агента бронирования")
    parser.add_argument("--only", help="часть названия сценария или категория")
    parser.add_argument(
        "--delay", type=float, default=6.0, help="пауза между репликами, секунды"
    )
    parser.add_argument("--json", dest="json_path", help="сохранить отчёт в файл")
    parser.add_argument(
        "--holdout", action="store_true", help="контрольный набор (новые фразы)"
    )
    args = parser.parse_args()
    asyncio.run(main(args.only, args.delay, args.json_path, args.holdout))
