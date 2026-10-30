import html
import logging
import pandas as pd
from src.config import OPTIMAL_SCHEMA

log = logging.getLogger(__name__)


def merge_sources(df_reviews: pd.DataFrame, df_business: pd.DataFrame) -> pd.DataFrame:
    """Этап 1: Соединение отзывов со справочником заведений по ключу business_id."""
    before = len(df_reviews)
    biz_cols = [
        "business_id",
        "name",
        "city",
        "state",
        "postal_code",
        "latitude",
        "longitude",
        "stars",
        "review_count",
        "is_open",
        "categories",
    ]
    biz = df_business[biz_cols].rename(
        columns={"name": "business_name", "stars": "business_stars"}
    )
    biz = biz.drop_duplicates(subset=["business_id"])

    merged = df_reviews.merge(biz, on="business_id", how="left")
    unmatched = merged["business_name"].isna().sum()

    log.info(
        "merge_sources: строк до=%d, после=%d, несопоставившихся записей=%d",
        before,
        len(merged),
        unmatched,
    )
    return merged


def normalize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """Этап 2: Приведение имён столбцов к нижнему регистру и snake_case."""
    df = df.copy()
    df.columns = (
        df.columns.str.strip()
        .str.lower()
        .str.replace(" ", "_", regex=False)
        .str.replace(r"[^a-z0-9_]", "", regex=True)
    )
    log.info("normalize_column_names: столбцов=%d", len(df.columns))
    return df


def handle_hidden_missing(df: pd.DataFrame) -> pd.DataFrame:
    """Этап 3: Выявление скрытых пропусков (пустые строки, прочерки) и обработка NaN."""
    df = df.copy()
    before = len(df)

    hidden_tokens = {"", "-", "none", "null", "n/a", "нет данных"}
    for col in ["text", "business_name", "city", "state", "postal_code", "categories"]:
        if col in df.columns:
            mask = df[col].astype(str).str.strip().str.lower().isin(hidden_tokens)
            df.loc[mask, col] = pd.NA

    # Удаляем записи без категории или ключевых полей (около 0.05% выборки)
    df = df.dropna(
        subset=[
            "review_id",
            "user_id",
            "business_id",
            "text",
            "business_name",
            "categories",
        ]
    )

    # Выделяем главную (первую) категорию заведения для соблюдения 1НФ
    df["main_category"] = (
        df["categories"].astype("string").str.split(",").str[0].str.strip()
    )
    df["postal_code"] = df["postal_code"].fillna("UNKNOWN")
    df = df.drop(columns=["categories"]).reset_index(drop=True)

    log.info(
        "handle_hidden_missing: было=%d, стало=%d (удалено=%d)",
        before,
        len(df),
        before - len(df),
    )
    return df


def cast_types_and_dates(df: pd.DataFrame) -> pd.DataFrame:
    """Этап 4: Приведение дат и назначение оптимальных типов данных."""
    df = df.copy()
    before = len(df)

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])

    for col, dtype in OPTIMAL_SCHEMA.items():
        if col in df.columns:
            df[col] = df[col].astype(dtype)

    log.info("cast_types_and_dates: было=%d, стало=%d", before, len(df))
    return df


def remove_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    """Этап 5: Удаление полных дубликатов и дубликатов по ключу (оставляем последнюю запись по дате)."""
    before = len(df)
    df = df.drop_duplicates()
    df = df.sort_values(["date", "review_id"]).drop_duplicates(
        subset=["review_id"], keep="last"
    )
    df = df.sort_values("review_id").reset_index(drop=True)
    log.info(
        "remove_duplicates: было=%d, стало=%d (удалено=%d)",
        before,
        len(df),
        before - len(df),
    )
    return df


def normalize_categories(df: pd.DataFrame) -> pd.DataFrame:
    """Этап 6: Нормализация категориальных столбцов (регистр, пробелы, редкие категории)."""
    df = df.copy()

    cities = (
        df["city"]
        .astype("string")
        .str.strip()
        .str.replace(r"\s+", " ", regex=True)
        .str.title()
    )
    city_map = {
        "St. Louis": "Saint Louis",
        "St Louis": "Saint Louis",
        "St. Petersburg": "Saint Petersburg",
        "St Petersburg": "Saint Petersburg",
        "Phila": "Philadelphia",
    }
    cities = cities.replace(city_map)

    city_counts = cities.value_counts()
    rare_cities = city_counts[city_counts < 20].index
    cities = cities.where(~cities.isin(rare_cities), "Other")
    df["city"] = cities.astype("category")

    df["state"] = (
        df["state"].astype("string").str.strip().str.upper().astype("category")
    )

    cats = df["main_category"].astype("string").str.strip()
    cat_counts = cats.value_counts()
    rare_cats = cat_counts[cat_counts < 50].index
    df["main_category"] = cats.where(~cats.isin(rare_cats), "Other").astype("category")

    log.info(
        "normalize_categories: уникальных городов=%d, категорий=%d",
        df["city"].nunique(),
        df["main_category"].nunique(),
    )
    return df


def clean_text_fields(df: pd.DataFrame) -> pd.DataFrame:
    """Этап 7: Очистка текстового столбца text от HTML-разметки и коротких неинформативных строк."""
    df = df.copy()
    before = len(df)

    text = df["text"].astype("string")
    text = text.map(lambda x: html.unescape(x) if pd.notna(x) else x)
    text = text.str.replace(r"<[^>]+>", " ", regex=True)
    text = text.str.replace(r"\s+", " ", regex=True).str.strip()
    df["text"] = text.astype("string")

    # Отбрасываем пустые и слишком короткие неинформативные отзывы (< 15 символов)
    df = df[df["text"].str.len() >= 15].reset_index(drop=True)
    log.info(
        "clean_text_fields: было=%d, стало=%d (удалено=%d)",
        before,
        len(df),
        before - len(df),
    )
    return df


def validate_domain_constraints(df: pd.DataFrame) -> pd.DataFrame:
    """Этап 8: Проверка предметных ограничений и приведение шкалы рейтинга."""
    df = df.copy()
    before = len(df)

    for col in ["useful", "funny", "cool"]:
        neg_cnt = (df[col] < 0).sum()
        if neg_cnt > 0:
            df[col] = df[col].clip(lower=0).astype("int16")
            log.info(
                "validate_domain_constraints: исправлено %d отрицательных значений в %s",
                neg_cnt,
                col,
            )

    now = pd.Timestamp.now()
    valid_mask = (
        df["stars"].between(1, 5)
        & df["business_stars"].between(1.0, 5.0)
        & df["latitude"].between(-90.0, 90.0)
        & df["longitude"].between(-180.0, 180.0)
        & (df["date"] <= now)
    )
    df = df[valid_mask].reset_index(drop=True)
    df["stars_100"] = (df["stars"].astype("float32") * 20.0).astype("float32")

    log.info("validate_domain_constraints: было=%d, стало=%d", before, len(df))
    return df


def detect_and_handle_outliers(df: pd.DataFrame) -> pd.DataFrame:
    """Этап 9: Выявление выбросов двумя способами (IQR и 3 сигмы) и пометка флагом."""
    df = df.copy()
    s = df["useful"].astype("float64")

    q1 = s.quantile(0.25)
    q3 = s.quantile(0.75)
    iqr_upper = q3 + 1.5 * (q3 - q1)
    iqr_outliers = (s > iqr_upper).sum()

    sigma_upper = s.mean() + 3.0 * s.std()
    sigma_outliers = (s > sigma_upper).sum()

    p999 = int(s.quantile(0.999))
    df["is_useful_outlier"] = (df["useful"] > sigma_upper).astype("boolean")
    df["useful"] = df["useful"].clip(upper=p999).astype("int16")

    log.info(
        "detect_and_handle_outliers: выбросов по IQR=%d (>%.1f), по 3-сигма=%d (>%.1f), порог усечения 99.9%%=%d",
        iqr_outliers,
        iqr_upper,
        sigma_outliers,
        sigma_upper,
        p999,
    )
    return df


def run_cleaning_pipeline(
    df_reviews: pd.DataFrame, df_business: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Последовательный запуск всех этапов очистки со сбором сводки «было — стало»."""
    steps = [
        ("1. Соединение таблиц (JOIN)", lambda d: merge_sources(d, df_business)),
        ("2. Нормализация имён столбцов", normalize_column_names),
        ("3. Обработка скрытых и явных пропусков", handle_hidden_missing),
        ("4. Приведение типов и дат", cast_types_and_dates),
        ("5. Удаление дубликатов", remove_duplicates),
        ("6. Нормализация категорий и городов", normalize_categories),
        ("7. Очистка текстового поля text", clean_text_fields),
        ("8. Проверка предметных ограничений", validate_domain_constraints),
        ("9. Обработка выбросов (IQR vs 3-sigma)", detect_and_handle_outliers),
    ]

    current_df = df_reviews
    initial_rows = len(df_reviews)
    report_rows = []

    for step_name, func in steps:
        before = len(current_df)
        current_df = func(current_df)
        after = len(current_df)
        lost = before - after
        report_rows.append(
            {
                "Этап очистки": step_name,
                "Строк до": before,
                "Строк после": after,
                "Удалено строк": lost,
                "Доля потерь, %": round((lost / initial_rows) * 100, 3),
            }
        )

    summary_df = pd.DataFrame(report_rows)
    return current_df, summary_df
