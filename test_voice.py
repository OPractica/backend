
from pathlib import Path
from difflib import SequenceMatcher
from voice.transcribe_audio import transcribe_audio

BASE_DIR = Path(__file__).resolve().parent

TEST_CASES = [
    {
        "language": "ru",
        "file": "russian.mp3",
        "expected": "Забронируй мне завтра рабочее место возле окна с девяти до шести.",
    },
    {
        "language": "ro",
        "file": "romanian.mp3",
        "expected": "Rezervă-mi pentru mâine un loc de lucru lângă fereastră, de la ora nouă până la ora șase.",
    },
    {
        "language": "en",
        "file": "english.mp3",
        "expected": "Book me a desk near the window tomorrow from nine to six.",
    },
]


def normalize(text):
    return " ".join(
        char for char in text.lower()
        if char.isalnum() or char.isspace()
    ).strip()


def run_tests():
    print("\n=== VOICE RECOGNITION TESTS ===\n")

    results = []

    for case in TEST_CASES:
        language = case["language"]
        file_path = BASE_DIR / "test_audio" / case["file"]

        print(f"Language: {language.upper()}")

        if not file_path.is_file():
            print(f"SKIPPED: Missing file {file_path}\n")
            continue

        try:
            recognized = transcribe_audio(
                str(file_path),
                language=language,
            )

            expected = case["expected"]

            similarity = SequenceMatcher(
                None,
                normalize(expected),
                normalize(recognized),
            ).ratio() * 100

            print(f"Expected:   {expected}")
            print(f"Recognized: {recognized}")
            print(f"Similarity: {similarity:.1f}%\n")

            results.append((language, similarity))

        except Exception as error:
            print(f"ERROR: {type(error).__name__}: {error}\n")

    print("=== SUMMARY ===")

    for language, score in results:
        print(f"{language.upper()}: {score:.1f}%")

    print(f"Completed: {len(results)}/{len(TEST_CASES)}")


if __name__ == "__main__":
    run_tests()
