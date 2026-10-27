from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

RAW_DIR = BASE_DIR / "data" / "raw"
INTERIM_DIR = BASE_DIR / "data" / "interim"
PROCESSED_DIR = BASE_DIR / "data" / "processed"
LOGS_DIR = BASE_DIR / "logs"

RAW_FILES = {
    "business": RAW_DIR / "yelp_academic_dataset_business.json",
    "review": RAW_DIR / "yelp_academic_dataset_review.json",
    "user": RAW_DIR / "yelp_academic_dataset_user.json",
    "checkin": RAW_DIR / "yelp_academic_dataset_checkin.json",
    "tip": RAW_DIR / "yelp_academic_dataset_tip.json",
}

SAMPLE_SIZE = 200_000
REVIEW_SAMPLE_JSONL = INTERIM_DIR / "review_sample_200k.jsonl"
