"""Code normalization and local code-pool helpers."""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

import pandas as pd

from .config import get_config


_PREFIX_SUFFIXES = {"SH", "SZ", "BJ", "OF", "CSI", "CNI"}
_STRIP_SUFFIXES = {"CFX", "CFFEX", "SHF", "DCE", "ZCE", "GFE", "INE"}
_FUTURE_LIKE_KINDS = {"future", "future_product", "option"}


def _normalized_text_series(values: pd.Series) -> pd.Series:
    text = values.astype("string").str.strip().str.upper()
    return text.mask(text == "")


def ts_code_series_to_tinysoft_symbol(values: pd.Series, *, kind: Optional[str] = None) -> pd.Series:
    text = _normalized_text_series(values)
    out = text.astype("object")
    out.loc[text.isna()] = None
    if text.empty:
        return out

    dotted_mask = text.str.contains(r"\.", na=False)
    if dotted_mask.any():
        dotted = text.loc[dotted_mask]
        split = dotted.str.rsplit(".", n=1, expand=True)
        code_part = split[0]
        suffix_part = split[1]
        if kind in _FUTURE_LIKE_KINDS:
            out.loc[dotted.index] = code_part.astype("object")
        else:
            prefix_mask = code_part.str.fullmatch(r"\d{6}", na=False) & suffix_part.isin(_PREFIX_SUFFIXES)
            if prefix_mask.any():
                prefix_index = prefix_mask[prefix_mask].index
                out.loc[prefix_index] = (suffix_part.loc[prefix_index] + code_part.loc[prefix_index]).astype("object")
            strip_mask = suffix_part.isin(_STRIP_SUFFIXES)
            if strip_mask.any():
                strip_index = strip_mask[strip_mask].index
                out.loc[strip_index] = code_part.loc[strip_index].astype("object")
    return out


def tinysoft_symbol_series_to_ts_code(values: pd.Series) -> pd.Series:
    text = _normalized_text_series(values)
    out = pd.Series([None] * len(values), index=values.index, dtype="object")
    if text.empty:
        return out

    prefix_match = text.str.extract(r"^(?P<suffix>SH|SZ|BJ|OF)(?P<code>\d{6})$")
    prefix_mask = prefix_match["suffix"].notna()
    if prefix_mask.any():
        prefix_index = prefix_mask[prefix_mask].index
        out.loc[prefix_index] = (
            prefix_match.loc[prefix_index, "code"] + "." + prefix_match.loc[prefix_index, "suffix"]
        ).astype("object")

    index_match = text.str.extract(r"^(?P<suffix>CSI|CNI)(?P<code>\d{6})$")
    index_mask = index_match["suffix"].notna()
    if index_mask.any():
        index_index = index_mask[index_mask].index
        out.loc[index_index] = (
            index_match.loc[index_index, "code"] + "." + index_match.loc[index_index, "suffix"]
        ).astype("object")

    already_mask = text.str.fullmatch(r"\d{6}\.(SH|SZ|BJ|OF|CSI|CNI)", na=False)
    if already_mask.any():
        already_index = already_mask[already_mask].index
        out.loc[already_index] = text.loc[already_index].astype("object")

    return out


def ts_code_to_tinysoft_symbol(value: object, *, kind: Optional[str] = None) -> Optional[str]:
    raw = str(value or "").strip().upper()
    if not raw:
        return None
    if "." in raw:
        code, suffix = raw.rsplit(".", 1)
        if re.fullmatch(r"\d{6}", code) and suffix in _PREFIX_SUFFIXES:
            return f"{suffix}{code}"
        if suffix in _STRIP_SUFFIXES or kind in {"future", "future_product", "option"}:
            return code
    if re.fullmatch(r"(SH|SZ|BJ|OF)\d{6}", raw):
        return raw
    if re.fullmatch(r"(CSI|CNI)\d{6}", raw):
        return raw
    return raw if raw else None


def tinysoft_symbol_to_ts_code(value: object) -> Optional[str]:
    raw = str(value or "").strip().upper()
    if not raw:
        return None
    match = re.fullmatch(r"(SH|SZ|BJ|OF)(\d{6})", raw)
    if match:
        return f"{match.group(2)}.{match.group(1)}"
    match = re.fullmatch(r"(CSI|CNI)(\d{6})", raw)
    if match:
        return f"{match.group(2)}.{match.group(1)}"
    if re.fullmatch(r"\d{6}\.(SH|SZ|BJ|OF)", raw):
        return raw
    if re.fullmatch(r"\d{6}\.(CSI|CNI)", raw):
        return raw
    return None


def normalize_codes(codes: Optional[Iterable[object]], *, kind: Optional[str] = None) -> List[str]:
    if codes is None:
        return []
    if isinstance(codes, (str, bytes)):
        raw_items: Iterable[object] = re.split(r"[\s,;]+", str(codes))
    else:
        raw_items = codes
    items = list(raw_items)
    if not items:
        return []
    normalized = ts_code_series_to_tinysoft_symbol(pd.Series(items, dtype="object"), kind=kind)
    return list(dict.fromkeys(code for code in normalized.tolist() if code))


def _read_codes_from_csv(path: Path, columns: Sequence[str]) -> List[str]:
    if not path.exists():
        return []
    out: List[str] = []
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            for col in columns:
                value = row.get(col)
                symbol = ts_code_to_tinysoft_symbol(value)
                if symbol:
                    out.append(symbol)
                    break
    return list(dict.fromkeys(out))


def load_code_pool(name: str, *, columns: Sequence[str] = ("ts_code", "code", "symbol")) -> List[str]:
    cfg = get_config()
    candidates = [
        cfg.code_dir / f"{name}.csv",
        cfg.code_dir / f"{name}_codes.csv",
    ]
    for path in candidates:
        codes = _read_codes_from_csv(path, columns)
        if codes:
            return codes
    return []
