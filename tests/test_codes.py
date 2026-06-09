from __future__ import annotations

import pandas as pd

from tinydata.codes import (
    normalize_codes,
    tinysoft_symbol_series_to_ts_code,
    tinysoft_symbol_to_ts_code,
    ts_code_series_to_tinysoft_symbol,
    ts_code_to_tinysoft_symbol,
)


def test_code_conversion():
    assert ts_code_to_tinysoft_symbol("000001.SZ") == "SZ000001"
    assert ts_code_to_tinysoft_symbol("000001.OF") == "OF000001"
    assert ts_code_to_tinysoft_symbol("000300.CSI") == "CSI000300"
    assert ts_code_to_tinysoft_symbol("00700.HK") == "HK00700"
    assert ts_code_to_tinysoft_symbol("IF2406.CFX", kind="future") == "IF2406"
    assert tinysoft_symbol_to_ts_code("SH600000") == "600000.SH"
    assert tinysoft_symbol_to_ts_code("CSI000300") == "000300.CSI"
    assert tinysoft_symbol_to_ts_code("HK00700") == "00700.HK"


def test_normalize_codes_deduplicates_and_splits_strings():
    assert normalize_codes("000001.SZ, 600000.SH 000001.SZ") == ["SZ000001", "SH600000"]


def test_series_code_conversion_helpers():
    assert ts_code_series_to_tinysoft_symbol(pd.Series(["000001.SZ", "600000.SH", "CSI000300", "00700.HK", None])).tolist() == [
        "SZ000001",
        "SH600000",
        "CSI000300",
        "HK00700",
        None,
    ]
    assert ts_code_series_to_tinysoft_symbol(pd.Series(["IF2406.CFX", "rb2410.shf", None]), kind="future").tolist() == [
        "IF2406",
        "RB2410",
        None,
    ]
    assert tinysoft_symbol_series_to_ts_code(pd.Series(["SH600000", "SZ000001", "CSI000300", "HK00700", None])).tolist() == [
        "600000.SH",
        "000001.SZ",
        "000300.CSI",
        "00700.HK",
        None,
    ]
