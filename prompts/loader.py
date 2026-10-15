from prompts.en import SYSTEM_PROMPT as EN_PROMPT
from prompts.ro import SYSTEM_PROMPT as RO_PROMPT
from prompts.ru import SYSTEM_PROMPT as RU_PROMPT

PROMPTS = {
    "ru": RU_PROMPT,
    "ro": RO_PROMPT,
    "en": EN_PROMPT,
}


def get_system_prompt(language: str = "ru") -> str:
    if language not in PROMPTS:
        raise ValueError(f"Unsupported language: {language}")

    return PROMPTS[language]
