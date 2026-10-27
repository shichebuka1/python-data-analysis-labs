import json
from pathlib import Path
from src.config import RAW_FILES, REVIEW_SAMPLE_JSONL, SAMPLE_SIZE, INTERIM_DIR


def inspect_raw_files(n_preview: int = 100) -> None:
    print("=" * 75)
    print(f"{'Файл':<38} | {'Размер, МБ':<12} | {'Кодировка'} | {'Столбцов'}")
    print("=" * 75)

    for name, path in RAW_FILES.items():
        if not path.exists():
            print(f"[!] Файл не найден: {path.name}")
            continue

        size_mb = path.stat().st_size / (1024**2)

        columns = set()
        first_keys = []
        with open(path, mode="r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                if i >= n_preview:
                    break
                record = json.loads(line)
                if i == 0:
                    first_keys = list(record.keys())
                columns.update(record.keys())

        print(f"{path.name:<38} | {size_mb:<12.2f} | {'UTF-8':<9} | {len(columns)}")
        print(f"   -> Перечень столбцов ({name}): {', '.join(first_keys)}\n")


def create_debug_sample(
    source_path: Path = RAW_FILES["review"],
    target_path: Path = REVIEW_SAMPLE_JSONL,
    n_rows: int = SAMPLE_SIZE,
) -> None:
    INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Формирование среза на {n_rows:,} строк из {source_path.name}...")

    count = 0
    with (
        open(source_path, mode="r", encoding="utf-8") as src,
        open(target_path, mode="w", encoding="utf-8") as dst,
    ):
        for line in src:
            if count >= n_rows:
                break
            dst.write(line)
            count += 1

    sample_size_mb = target_path.stat().st_size / (1024**2)
    print(f"Готово! Записано строк: {count:,}")
    print(f"Файл сохранён: {target_path} ({sample_size_mb:.2f} МБ)")


if __name__ == "__main__":
    inspect_raw_files(n_preview=100)
    create_debug_sample()
