#!/usr/bin/env python3
"""
Warframe Market v2 API 客户端
封装对 api.warframe.market/v2 的 HTTP 请求
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional
from urllib.parse import quote

import requests


API_BASE = "https://api.warframe.market/v2"
DEFAULT_PLATFORM = "pc"
DEFAULT_LANGUAGE = "zh-hans"
DEFAULT_USER_AGENT = "PriceSearcher/1.0"
DEFAULT_TIMEOUT = 15
DEFAULT_MIN_INTERVAL = 0.35
DEFAULT_MAX_RETRIES = 3


class APIError(Exception):
    """API 请求异常"""
    def __init__(
        self,
        message: str,
        *,
        status_code: Optional[int] = None,
        url: Optional[str] = None,
        response: Any = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.url = url
        self.response = response


class WarframeAPIClient:
    """Warframe Market v2 API 客户端"""

    def __init__(
        self,
        platform: str = DEFAULT_PLATFORM,
        language: str = DEFAULT_LANGUAGE,
        user_agent: str = DEFAULT_USER_AGENT,
        timeout: int = DEFAULT_TIMEOUT,
        min_interval: float = DEFAULT_MIN_INTERVAL,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> None:
        self.platform = self._normalize_platform(platform)
        self.language = language
        self.user_agent = user_agent
        self.timeout = timeout
        self.min_interval = min_interval
        self.max_retries = max_retries
        self._last_request_ts = 0.0
        self.session = requests.Session()
        self._apply_headers()

    @staticmethod
    def _normalize_platform(platform: str) -> str:
        aliases = {"xb1": "xbox"}
        return aliases.get(platform.lower().strip(), platform.lower().strip())

    def _apply_headers(self) -> None:
        self.session.headers.update({
            "Accept": "application/json",
            "User-Agent": self.user_agent,
            "Platform": self.platform,
            "Language": self.language,
        })

    def _throttle(self) -> None:
        elapsed = time.time() - self._last_request_ts
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)

    def _request(self, path: str) -> Dict[str, Any]:
        url = f"{API_BASE}{path}"
        last_error: Optional[Exception] = None

        for attempt in range(1, self.max_retries + 1):
            self._throttle()
            try:
                resp = self.session.get(url, timeout=self.timeout)
                self._last_request_ts = time.time()

                try:
                    payload: Any = resp.json()
                except ValueError:
                    payload = resp.text

                if resp.status_code in {429, 500, 502, 503, 504} and attempt < self.max_retries:
                    delay = min(2 ** (attempt - 1), 8)
                    time.sleep(delay)
                    continue

                if not resp.ok:
                    raise APIError(
                        f"API 请求失败: {resp.status_code}",
                        status_code=resp.status_code,
                        url=url,
                        response=payload,
                    )

                if not isinstance(payload, dict):
                    raise APIError(
                        "API 返回非对象 JSON",
                        status_code=resp.status_code,
                        url=url,
                        response=payload,
                    )
                return payload

            except (requests.RequestException, APIError) as exc:
                last_error = exc
                if isinstance(exc, APIError) and exc.status_code not in {429, 500, 502, 503, 504}:
                    raise
                if attempt >= self.max_retries:
                    break
                delay = min(2 ** (attempt - 1), 8)
                time.sleep(delay)

        raise APIError(
            f"API 请求最终失败: {last_error}",
            url=url,
            response=repr(last_error),
        )

    def fetch_items(self) -> Dict[str, Any]:
        """获取全部物品列表 GET /v2/items"""
        return self._request("/items")

    def fetch_top_orders(self, slug: str) -> Dict[str, Any]:
        """获取指定物品的 top 买卖单 GET /v2/orders/item/{slug}/top"""
        safe_slug = quote(str(slug), safe="")
        return self._request(f"/orders/item/{safe_slug}/top")
