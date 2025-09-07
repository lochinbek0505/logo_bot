from __future__ import annotations

import os
from urllib.parse import urljoin
from typing import List, Dict, Any

import aiohttp


ADMIN_BASE = os.getenv("ADMIN_BASE", "http://185.217.131.39/")


class AdminClient:
    def __init__(self, base: str | None = None):
        self.base = base or ADMIN_BASE
        self._timeout = aiohttp.ClientTimeout(total=25)
        self._headers = {"User-Agent": "bot-darslik-client/1.0"}

    async def _get_json(self, path: str, params: dict | None = None) -> Any:
        url = urljoin(self.base, path)
        async with aiohttp.ClientSession(timeout=self._timeout, headers=self._headers) as s:
            async with s.get(url, params=params) as r:
                r.raise_for_status()
                return await r.json()

    async def _download_bytes(self, url: str) -> tuple[bytes, str]:
        async with aiohttp.ClientSession(timeout=self._timeout, headers=self._headers) as s:
            async with s.get(url) as r:
                r.raise_for_status()
                return await r.read(), r.headers.get("Content-Type", "")

    # ---------- Darsliklar ----------
    async def list_lessons(self, enabled: bool = True) -> List[Dict[str, Any]]:
        # /darslik GET (public)
        params = {"enabled": str(enabled).lower()}
        data = await self._get_json("/darslik", params=params)
        # normalizatsiya: pdf_url to'liq bo'lsin
        for d in data:
            pdf = (d.get("pdf_path") or "").strip()
            if pdf:
                d["pdf_url"] = pdf if pdf.startswith("/static/") else f"/static/pdfs/{os.path.basename(pdf)}"
                d["pdf_url"] = urljoin(self.base, d["pdf_url"])
        return data

    async def export_lesson(self, code: str) -> Dict[str, Any]:
        # /export/darslik/{code} GET (public, only enabled)
        data = await self._get_json(f"/export/darslik/{code}")
        # to'liq pdf URL
        pdf = (data.get("pdf_url") or "").strip()
        if pdf and pdf.startswith("/"):
            data["pdf_url"] = urljoin(self.base, pdf)
        return data

    async def download_pdf(self, abs_or_full_url: str) -> tuple[bytes, str]:
        # pdf'ni bytes qilib olib berish
        return await self._download_bytes(abs_or_full_url)
