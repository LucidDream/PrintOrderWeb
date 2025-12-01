"""Lightweight PDF analyzer for deriving smart defaults."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Any

from pypdf import PdfReader


class PDFAnalyzer:
    """Extract minimal metadata, resilient to malformed PDFs."""

    def analyze(self, pdf_path: str | Path) -> Dict[str, Any]:
        path = Path(pdf_path)
        info: Dict[str, Any] = {
            "path": str(path),
            "pages": 0,
            "size_kb": round(path.stat().st_size / 1024, 2) if path.exists() else 0,
            "recommended_color_mode": "full_color",
            "page_dimensions": [],
        }

        try:
            reader = PdfReader(str(path))
            info["pages"] = len(reader.pages)
            if reader.pages:
                page = reader.pages[0]
                width = round(float(page.mediabox.width) / 72, 2)
                height = round(float(page.mediabox.height) / 72, 2)
                info["page_dimensions"].append({"width_in": width, "height_in": height})
        except Exception as exc:  # pragma: no cover - defensive logging hook
            info["error"] = f"PDF analysis failed: {exc}"

        if info["pages"] <= 1:
            info["recommended_color_mode"] = "mono"

        return info
