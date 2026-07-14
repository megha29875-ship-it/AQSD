
from pathlib import Path

scanner = Path(__file__).resolve().parent / "scanner.py"

if not scanner.exists():
    raise FileNotFoundError(f"scanner.py not found:\n{scanner}")

text = scanner.read_text(encoding="utf-8")

old = '"Confidence",\n            "Grade",\n            "Action",'
new = '"Trade Confidence",\n            "Trade Grade",\n            "Stars",\n            "Recommendation",'

if old in text:
    text = text.replace(old, new)
else:
    text = text.replace(
        '"Confidence", "Grade", "Action",',
        '"Trade Confidence", "Trade Grade", "Stars", "Recommendation",'
    )

scanner.write_text(text, encoding="utf-8")

print("scanner.py patched successfully.")
