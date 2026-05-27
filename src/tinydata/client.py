"""Synchronous TS-OPI HTTP client used by tinydata."""

from __future__ import annotations

import base64
import json
import logging
import threading
import time
from typing import Any, Callable, Dict, Iterable, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

import pandas as pd

from .config import TinyDataConfig, get_config
from .errors import TinyDataAuthError, TinyDataQueryError, TinyDataRateLimitError, TinyDataTimeoutError
from .infotable import format_stock_selector, parse_tinysoft_date

TransportCallable = Callable[..., Any]


class TinyClient:
    """Thin, defensive wrapper around Tinysoft TS-OPI.

    ``exec`` returns a DataFrame by default, ``query`` returns market data, and
    ``call`` invokes a named server function. Authentication happens per HTTP
    request, so there is no persistent local login session.
    """

    DEFAULT_BASE_URL = "https://opi.tinysoft.com.cn"
    RATE_LIMIT_MAX_ATTEMPTS = 3
    RATE_LIMIT_BACKOFF_SECONDS = 1.0

    def __init__(
        self,
        config: Optional[TinyDataConfig] = None,
        *,
        transport: Optional[TransportCallable] = None,
        logger: Optional[logging.Logger] = None,
    ):
        self.config = config or get_config()
        self.transport = transport
        self.logger = logger or logging.getLogger(__name__)
        self._last_request_time = 0.0
        self._request_slot_lock = threading.Lock()

    @property
    def base_url(self) -> str:
        return (self.config.opi_url or self.DEFAULT_BASE_URL).strip().rstrip("/")

    def _wait_for_request_slot(self) -> None:
        with self._request_slot_lock:
            elapsed = time.monotonic() - self._last_request_time
            if elapsed < self.config.request_interval:
                time.sleep(self.config.request_interval - elapsed)
            self._last_request_time = time.monotonic()

    def _auth_headers(self) -> Dict[str, str]:
        auth_mode = (self.config.opi_auth_mode or "basic").strip().lower().replace("_", "-")
        if auth_mode in {"none", "no-auth"}:
            return {}

        if auth_mode in {"basic", "base"}:
            if not self.config.user:
                raise TinyDataAuthError("Tinysoft OPI user is empty. Set TINYDATA_USER or call configure(user=...).")
            if not self.config.password:
                raise TinyDataAuthError(
                    "Tinysoft OPI password is empty. Set TINYDATA_PASSWORD or call configure(password=...)."
                )
            token = base64.b64encode(f"{self.config.user}:{self.config.password}".encode("utf-8")).decode("ascii")
            return {"Authorization": f"Basic {token}"}

        if auth_mode in {"bearer", "session", "session-key"}:
            if not self.config.session_key:
                raise TinyDataAuthError("Tinysoft OPI session_key is empty.")
            token = self.config.session_key
            if self.config.session_password:
                token = f"{token}:{self.config.session_password}"
            return {"Authorization": f"Bearer {token}"}

        if auth_mode in {"x-api-key", "api-key", "apikey"}:
            if not self.config.session_key:
                raise TinyDataAuthError("Tinysoft OPI api key is empty.")
            token = self.config.session_key
            if self.config.session_password:
                token = f"{token}:{self.config.session_password}"
            return {"X-API-Key": token}

        raise TinyDataAuthError(f"Unsupported Tinysoft OPI auth_mode: {self.config.opi_auth_mode}")

    def _headers(self, *, service: Optional[str] = None, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        headers = {
            "Connection": "keep-alive",
            "Content-Type": "application/json",
            "JSON-Encode": self.config.json_encode or "utf8",
        }
        headers.update(self._auth_headers())
        event_name = service if service is not None else self.config.service
        if event_name:
            headers["TS-EVENTNAME"] = str(event_name)
        if extra:
            headers.update({str(k): str(v) for k, v in extra.items() if v is not None})
        return headers

    def _url(self, path: str) -> str:
        if not self.base_url:
            raise TinyDataQueryError("Tinysoft OPI base_url is empty.")
        return f"{self.base_url}/{path.lstrip('/')}"

    @staticmethod
    def _decode_text(body: bytes) -> str:
        for encoding in ("utf-8", "gbk", "gb18030"):
            try:
                return body.decode(encoding)
            except UnicodeDecodeError:
                continue
        return body.decode("utf-8", errors="replace")

    @classmethod
    def _decode_body(cls, body: Any) -> Any:
        if body is None or isinstance(body, (dict, list, int, float, bool)):
            return body
        if isinstance(body, bytes):
            body = cls._decode_text(body)
        text = str(body).strip()
        if not text:
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text

    @classmethod
    def _unpack_transport_response(cls, response: Any) -> Tuple[int, Dict[str, str], Any]:
        if isinstance(response, tuple):
            if len(response) == 3:
                status, headers, body = response
                return int(status), dict(headers or {}), body
            if len(response) == 2:
                status, body = response
                return int(status), {}, body
        if isinstance(response, dict) and {"status", "body"} & set(response):
            status = int(response.get("status", 200))
            headers = dict(response.get("headers") or {})
            body = response.get("body", response.get("payload"))
            return status, headers, body
        return 200, {}, response

    @staticmethod
    def _maybe_raise_payload_error(payload: Any) -> None:
        if not isinstance(payload, dict):
            return
        lowered = {str(k).lower(): v for k, v in payload.items()}
        code = lowered.get("code", lowered.get("error_code", lowered.get("status")))
        message = lowered.get("message", lowered.get("msg", lowered.get("error")))
        has_data = any(key in lowered for key in ("data", "result", "value", "rows", "body", "res"))
        if code is None or has_data:
            return
        code_text = str(code).strip().lower()
        if code_text and code_text not in {"0", "200", "success", "ok"}:
            raise TinyDataQueryError(f"Tinysoft OPI returned error: code={code}, message={message}")

    @staticmethod
    def _is_rate_limit_payload(payload: Any) -> bool:
        if not isinstance(payload, dict):
            return False
        lowered = {str(k).lower(): v for k, v in payload.items()}
        code = lowered.get("code", lowered.get("error_code", lowered.get("status")))
        message = lowered.get("message", lowered.get("msg", lowered.get("error")))
        if str(code).strip() == "429":
            return True
        return "too many requests" in str(message or "").lower()

    @staticmethod
    def _parse_retry_after(headers: Optional[Dict[str, str]]) -> Optional[float]:
        if not headers:
            return None
        value: Optional[str] = None
        for key, header_value in headers.items():
            if str(key).lower() == "retry-after":
                value = str(header_value).strip()
                break
        if not value:
            return None
        try:
            delay = float(value)
        except ValueError:
            return None
        if delay < 0:
            return None
        return min(delay, 60.0)

    def _rate_limit_retry_delay(self, attempt: int, headers: Optional[Dict[str, str]]) -> float:
        retry_after = self._parse_retry_after(headers)
        if retry_after is not None:
            return retry_after
        return min(8.0, self.RATE_LIMIT_BACKOFF_SECONDS * (2**attempt))

    def _retry_or_raise_rate_limit(
        self,
        decoded: Any,
        *,
        attempt: int,
        max_attempts: int,
        headers: Optional[Dict[str, str]] = None,
    ) -> bool:
        if attempt + 1 < max_attempts:
            delay = self._rate_limit_retry_delay(attempt, headers)
            self.logger.warning(
                "Tinysoft OPI returned HTTP 429; retrying in %.1fs (%s/%s).",
                delay,
                attempt + 2,
                max_attempts,
            )
            time.sleep(delay)
            return True
        raise TinyDataRateLimitError(
            "Tinysoft OPI HTTP 429: request limit or concurrent session limit exceeded "
            f"after {max_attempts} attempts. Reduce concurrent jobs, increase request_interval, "
            f"or contact Tinysoft to increase OPI concurrency. Response: {decoded}"
        )

    def _request_json(
        self,
        path: str,
        payload: Any,
        *,
        service: Optional[str] = None,
        timeout_ms: Optional[int] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> Any:
        timeout = int(timeout_ms or self.config.timeout_ms)
        headers = self._headers(service=service, extra=extra_headers)
        url = self._url(path)
        max_attempts = max(1, int(self.RATE_LIMIT_MAX_ATTEMPTS))

        for attempt in range(max_attempts):
            self._wait_for_request_slot()

            if self.transport is not None:
                response = self.transport(
                    path=path,
                    url=url,
                    headers=headers,
                    json=payload,
                    timeout_ms=timeout,
                )
                status, response_headers, body = self._unpack_transport_response(response)
            else:
                # TS-OPI /Service/Run/ rejects raw non-ASCII JSON bodies for TSL
                # scripts with Chinese field names. Match aiohttp's default escaped JSON.
                request_body = json.dumps(payload).encode("utf-8")
                request = Request(url, data=request_body, headers=headers, method="POST")
                try:
                    with urlopen(request, timeout=max(0.001, timeout / 1000.0)) as response:
                        status = int(response.status)
                        response_headers = dict(getattr(response, "headers", {}) or {})
                        body = response.read()
                except TimeoutError as exc:
                    raise TinyDataTimeoutError(f"Tinysoft OPI request timed out after {timeout}ms") from exc
                except HTTPError as exc:
                    decoded = self._decode_body(exc.read())
                    if int(exc.code) == 429 and self._retry_or_raise_rate_limit(
                        decoded,
                        attempt=attempt,
                        max_attempts=max_attempts,
                        headers=dict(exc.headers or {}),
                    ):
                        continue
                    raise TinyDataQueryError(f"Tinysoft OPI HTTP {exc.code}: {decoded}") from exc
                except URLError as exc:
                    reason = getattr(exc, "reason", exc)
                    if isinstance(reason, TimeoutError):
                        raise TinyDataTimeoutError(f"Tinysoft OPI request timed out after {timeout}ms") from exc
                    raise TinyDataQueryError(f"Tinysoft OPI request failed: {reason}") from exc

            decoded = self._decode_body(body)
            if (status == 429 or self._is_rate_limit_payload(decoded)) and self._retry_or_raise_rate_limit(
                decoded,
                attempt=attempt,
                max_attempts=max_attempts,
                headers=response_headers,
            ):
                continue
            if status < 200 or status >= 300:
                raise TinyDataQueryError(f"Tinysoft OPI HTTP {status}: {decoded}")
            self._maybe_raise_payload_error(decoded)
            return decoded

        raise TinyDataRateLimitError("Tinysoft OPI HTTP 429: request limit exceeded.")

    @staticmethod
    def _extract_data_payload(payload: Any) -> Any:
        if not isinstance(payload, dict):
            return payload
        for key in ("data", "Data", "result", "Result", "value", "Value", "rows", "Rows", "body", "Body", "res", "Res"):
            if key in payload:
                return payload[key]
        return payload

    @classmethod
    def _payload_to_dataframe(cls, payload: Any) -> pd.DataFrame:
        if isinstance(payload, dict):
            lowered = {str(k).lower(): k for k in payload}
            if "columns" in lowered and "rows" in lowered:
                data = payload
            else:
                data = cls._extract_data_payload(payload)
        else:
            data = cls._extract_data_payload(payload)
        if data is None:
            return pd.DataFrame()
        if isinstance(data, str):
            data = cls._decode_body(data)
            if isinstance(data, str):
                return pd.DataFrame({"value": [data]})
        if isinstance(data, dict):
            lowered = {str(k).lower(): k for k in data}
            if "columns" in lowered and "rows" in lowered:
                columns = data[lowered["columns"]]
                rows = data[lowered["rows"]]
                return pd.DataFrame(rows, columns=columns)
            list_values = [v for v in data.values() if isinstance(v, list)]
            if list_values and len(list_values) == len(data):
                lengths = {len(v) for v in list_values}
                if len(lengths) == 1:
                    return pd.DataFrame(data)
            return pd.DataFrame([data])
        if isinstance(data, list):
            if not data:
                return pd.DataFrame()
            first = data[0]
            if isinstance(first, dict):
                return pd.DataFrame(data)
            if (
                isinstance(first, (list, tuple))
                and first
                and all(isinstance(item, str) for item in first)
                and all(isinstance(row, (list, tuple)) and len(row) == len(first) for row in data[1:])
            ):
                return pd.DataFrame(data[1:], columns=list(first))
            return pd.DataFrame(data)
        return pd.DataFrame({"value": [data]})

    def login(self, *, force: bool = False) -> None:
        # TS-OPI authenticates every request via HTTP headers.
        self._auth_headers()

    def logout(self) -> None:
        return None

    def _uses_session_call_uri(self) -> bool:
        mode = (self.config.opi_auth_mode or "basic").strip().lower().replace("_", "-")
        return mode in {"bearer", "session", "session-key", "x-api-key", "api-key", "apikey"}

    def exec(self, tsl_code: str, *, as_dataframe: bool = True, timeout_ms: Optional[int] = None):
        if self._uses_session_call_uri():
            if self.config.run_func_name:
                return self.call(
                    self.config.run_func_name,
                    {"body": tsl_code},
                    as_dataframe=as_dataframe,
                    timeout_ms=timeout_ms,
                )
            raise TinyDataQueryError(
                "Tinysoft OPI /Service/Run/ requires developer-user authentication. "
                "SESSION-KEY tenants must expose a wrapper function and configure run_func_name."
            )
        payload = self._request_json(
            "/Service/Run/",
            {"body": tsl_code},
            timeout_ms=timeout_ms,
        )
        return self._payload_to_dataframe(payload) if as_dataframe else payload

    def _call_path(self, func_name: str) -> str:
        func = str(func_name or "").strip().strip("/")
        if not func:
            return "/Service/Session/Call/" if self._uses_session_call_uri() else "/Service/Call/"
        encoded = "/".join(quote(part) for part in func.split("/"))
        if self._uses_session_call_uri():
            return f"/Service/Session/Call/{encoded}"
        return f"/Service/Call/{encoded}"

    def call(
        self,
        func_name: str,
        *args: Any,
        code: str = "",
        as_dataframe: bool = True,
        timeout_ms: Optional[int] = None,
    ):
        if code:
            raise TinyDataQueryError("Tinysoft OPI call does not support inline TSL code.")
        if not args:
            payload_data: Any = {}
        elif len(args) == 1 and isinstance(args[0], (dict, list)):
            payload_data = args[0]
        else:
            payload_data = list(args)
        payload = self._request_json(self._call_path(func_name), payload_data, timeout_ms=timeout_ms)
        return self._payload_to_dataframe(payload) if as_dataframe else payload

    @staticmethod
    def _format_datetime_literal(value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            raise ValueError("Tinysoft OPI date/time value cannot be empty")
        dt = parse_tinysoft_date(text)
        if pd.isna(dt):
            raise ValueError(f"Tinysoft OPI date/time value is invalid: {value}")
        if dt.hour == 0 and dt.minute == 0 and dt.second == 0 and not any(ch in text for ch in (":", ".")):
            return dt.strftime("%Y%m%dT")
        return dt.strftime("%Y%m%d.%H%M%ST")

    @staticmethod
    def _cycle_to_tsl_expr(cycle: str) -> str:
        raw = str(cycle or "").strip()
        lowered = raw.lower()
        if lowered.startswith("cy_") and lowered.endswith(")"):
            return raw
        mapping = {
            "1m": "cy_1m()",
            "1min": "cy_1m()",
            "1分钟": "cy_1m()",
            "1分钟线": "cy_1m()",
            "5m": "cy_5m()",
            "5min": "cy_5m()",
            "5分钟": "cy_5m()",
            "5分钟线": "cy_5m()",
            "15m": "cy_15m()",
            "15min": "cy_15m()",
            "15分钟": "cy_15m()",
            "15分钟线": "cy_15m()",
            "30m": "cy_30m()",
            "30min": "cy_30m()",
            "30分钟": "cy_30m()",
            "30分钟线": "cy_30m()",
            "60m": "cy_60m()",
            "60min": "cy_60m()",
            "60分钟": "cy_60m()",
            "60分钟线": "cy_60m()",
            "d": "cy_day()",
            "day": "cy_day()",
            "daily": "cy_day()",
            "日线": "cy_day()",
            "w": "cy_week()",
            "week": "cy_week()",
            "weekly": "cy_week()",
            "周线": "cy_week()",
            "m": "cy_month()",
            "month": "cy_month()",
            "monthly": "cy_month()",
            "月线": "cy_month()",
        }
        if lowered in mapping:
            return mapping[lowered]
        raise ValueError(f"Unsupported Tinysoft OPI cycle: {cycle}")

    @staticmethod
    def _normalize_adjust_rate(adjust: Any) -> Optional[int]:
        if adjust is None:
            return None
        if isinstance(adjust, bool):
            adjust = int(adjust)
        if isinstance(adjust, int):
            if adjust in {0, 1, 2}:
                return adjust
            raise ValueError("Tinysoft adjust must be 0, 1, or 2.")

        raw = str(adjust).strip().lower().replace("-", "_").replace(" ", "_")
        mapping = {
            "0": 0,
            "none": 0,
            "raw": 0,
            "unadjusted": 0,
            "no": 0,
            "no_adjust": 0,
            "不复权": 0,
            "未复权": 0,
            "1": 1,
            "ratio": 1,
            "exchange": 1,
            "proportional": 1,
            "比例": 1,
            "比例复权": 1,
            "交易所除权": 1,
            "交易所数据除权": 1,
            "2": 2,
            "complex": 2,
            "dividend": 2,
            "cash_dividend": 2,
            "复杂": 2,
            "复杂复权": 2,
            "分红送配": 2,
            "分红送配复权": 2,
        }
        if raw in mapping:
            return mapping[raw]
        raise ValueError(
            "Unsupported Tinysoft adjust value. Use 0/'none', 1/'ratio', or 2/'complex'."
        )

    @classmethod
    def _format_rateday_literal(cls, value: Any) -> str:
        raw_text = str(value).strip().lower()
        if raw_text == "-1":
            return "-1"
        raw = raw_text.replace("-", "_").replace(" ", "_")
        if raw in {"-1", "listing", "listed", "first", "firstday", "ipo", "found", "establish"}:
            return "-1"
        if raw in {"0", "today", "current", "latest", "last"}:
            return "0"
        return cls._format_datetime_literal(value)

    @staticmethod
    def _format_select_field(field: Any) -> str:
        raw = str(field or "").strip()
        if not raw:
            raise ValueError("Tinysoft OPI field cannot be empty")
        if raw.lower() == "date":
            return 'datetimetostr(["date"]) as "date"'
        if raw.startswith("[") or " as " in raw.lower() or "(" in raw:
            return raw
        return f'["{raw}"]'

    @classmethod
    def _build_markettable_tsl(
        cls,
        *,
        stock: str,
        cycle: str,
        begin_time: Any,
        end_time: Any,
        fields: Optional[Iterable[Any]],
        adjust: Any = None,
        adjust_date: Any = None,
    ) -> str:
        return cls._build_markettable_panel_tsl(
            stocks=[stock],
            cycle=cycle,
            begin_time=begin_time,
            end_time=end_time,
            fields=fields,
            adjust=adjust,
            adjust_date=adjust_date,
        )

    @classmethod
    def _build_markettable_panel_tsl(
        cls,
        *,
        stocks: Iterable[Any],
        cycle: str,
        begin_time: Any,
        end_time: Any,
        fields: Optional[Iterable[Any]],
        code_kind: Optional[str] = None,
        adjust: Any = None,
        adjust_date: Any = None,
    ) -> str:
        field_list = list(fields or ["date", "StockID", "open", "high", "low", "close", "vol", "amount"])
        select_fields = ",".join(cls._format_select_field(field) for field in field_list)
        begin_literal = cls._format_datetime_literal(begin_time)
        end_literal = cls._format_datetime_literal(end_time)
        cycle_expr = cls._cycle_to_tsl_expr(cycle)
        selector = format_stock_selector(stocks, code_kind=code_kind)
        adjust_rate = cls._normalize_adjust_rate(adjust)
        if adjust_rate is None and adjust_date is not None:
            raise ValueError("Tinysoft adjust_date requires adjust.")
        sysparams = [f"setsysparam(pn_cycle(),{cycle_expr});"]
        if adjust_rate is not None:
            effective_adjust_date = adjust_date if adjust_date is not None else end_time
            sysparams.append(f"setsysparam(Pn_rate(),{adjust_rate});")
            adjust_date_literal = cls._format_rateday_literal(effective_adjust_date)
            sysparams.append(f"SetSysParam(Pn_rateday(),{adjust_date_literal});")
        return (
            "".join(sysparams)
            + f"return select {select_fields} "
            f"from markettable datekey {begin_literal} to {end_literal} "
            f"of {selector} end;"
        )

    def query(
        self,
        *,
        stock: str,
        cycle: str,
        begin_time: Any,
        end_time: Any,
        fields: Optional[Iterable[Any]] = None,
        service: Optional[str] = None,
        timeout_ms: Optional[int] = None,
        adjust: Any = None,
        adjust_date: Any = None,
        **kwargs: Any,
    ) -> pd.DataFrame:
        if self.config.query_func_name:
            params = {
                "StockID": stock,
                "Cycle": cycle,
                "BegT": begin_time,
                "EndT": end_time,
                "Fields": list(fields or []),
            }
            adjust_rate = self._normalize_adjust_rate(adjust)
            if adjust_rate is None and adjust_date is not None:
                raise ValueError("Tinysoft adjust_date requires adjust.")
            if adjust_rate is not None:
                effective_adjust_date = adjust_date if adjust_date is not None else end_time
                params["Adjust"] = adjust_rate
                params["AdjustDate"] = effective_adjust_date
            params.update({k: v for k, v in kwargs.items() if v is not None})
            return self.call(self.config.query_func_name, params, as_dataframe=True, timeout_ms=timeout_ms)
        tsl_code = self._build_markettable_tsl(
            stock=stock,
            cycle=cycle,
            begin_time=begin_time,
            end_time=end_time,
            fields=fields,
            adjust=adjust,
            adjust_date=adjust_date,
        )
        payload = self._request_json(
            "/Service/Run/",
            {"body": tsl_code},
            service=service,
            timeout_ms=timeout_ms,
        )
        return self._payload_to_dataframe(payload)

    def query_panel(
        self,
        *,
        stocks: Iterable[Any],
        cycle: str,
        begin_time: Any,
        end_time: Any,
        fields: Optional[Iterable[Any]] = None,
        code_kind: Optional[str] = None,
        service: Optional[str] = None,
        timeout_ms: Optional[int] = None,
        adjust: Any = None,
        adjust_date: Any = None,
    ) -> pd.DataFrame:
        tsl_code = self._build_markettable_panel_tsl(
            stocks=stocks,
            cycle=cycle,
            begin_time=begin_time,
            end_time=end_time,
            fields=fields,
            code_kind=code_kind,
            adjust=adjust,
            adjust_date=adjust_date,
        )
        return self.exec(tsl_code, as_dataframe=True, timeout_ms=timeout_ms or None)
