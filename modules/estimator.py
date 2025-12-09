"""Heuristic estimator for consumable usage."""

from __future__ import annotations

from typing import Dict, Any
import logging

from config import Config


class JobEstimator:
    """Produces rough estimates for job consumables and totals."""

    # Quality modifiers for toner usage
    QUALITY_MODIFIERS = {
        "draft": 0.70,      # Draft = -30% toner usage
        "standard": 1.00,   # Standard = baseline
        "high": 1.20,       # High = +20% toner usage
    }

    # Page coverage estimates (percentage of page covered in ink)
    # These are industry-standard estimates for typical documents
    # NOTE: "text_normal" is overridden by ESTIMATOR_PAGE_COVERAGE_PERCENT from .env
    PAGE_COVERAGE = {
        "text_light": 0.05,      # 5% coverage - light text documents
        "text_normal": 0.10,     # 10% coverage - normal text documents (default, configurable)
        "text_heavy": 0.15,      # 15% coverage - text with tables/formatting
        "graphics": 0.25,        # 25% coverage - documents with graphics
        "photos": 0.50,          # 50% coverage - photo-heavy documents
    }

    # Base toner consumption: mL per sheet at 100% coverage
    # NOTE: Overridden by ESTIMATOR_BASE_TONER_ML from .env
    BASE_TONER_ML_PER_SHEET_FULL_COVERAGE = 0.15

    @classmethod
    def _get_base_toner_ml(cls) -> float:
        """Get base toner mL from config (allows .env override)."""
        return Config.ESTIMATOR_BASE_TONER_ML

    @classmethod
    def _get_page_coverage(cls) -> float:
        """Get page coverage from config (allows .env override).

        Returns coverage as decimal (e.g., 0.10 for 10%).
        """
        return Config.ESTIMATOR_PAGE_COVERAGE_PERCENT / 100.0

    def __init__(self, inventory_service) -> None:  # inventory_service kept for parity
        self.inventory_service = inventory_service
        self.logger = logging.getLogger(__name__)

    def estimate(self, order: Dict[str, Any], inventory_snapshot: Dict[str, Any]) -> Dict[str, Any]:
        analysis = order.get("analysis", {})
        choices = order.get("choices", {})

        pages = max(int(analysis.get("pages", 1)), 1)
        quantity = int(choices.get("quantity", 0))
        color_mode = choices.get("color_mode", "full_color")
        quality = choices.get("quality", "standard")
        media_key = choices.get("media_type")

        sheets_required = quantity * pages

        toner_profile = inventory_snapshot["toner_profiles"].get(color_mode, [])

        # Debug logging
        self.logger.debug(f"Estimator inputs: pages={pages}, quantity={quantity}, color_mode={color_mode}, quality={quality}")
        self.logger.debug(f"Sheets required: {sheets_required}")
        self.logger.debug(f"Toner profile for {color_mode}: {toner_profile}")
        self.logger.debug(f"Toner profiles available: {list(inventory_snapshot['toner_profiles'].keys())}")

        # Calculate toner usage with enhanced heuristics
        toner_usage = self._calculate_toner_usage(
            sheets_required=sheets_required,
            toner_profile=toner_profile,
            color_mode=color_mode,
            quality=quality,
        )

        media_available = inventory_snapshot["media_options"].get(media_key, {}).get(
            "available", 0
        )

        media_ok = sheets_required <= media_available
        toner_ok = all(
            usage <= inventory_snapshot["toner_balances"].get(color, {}).get("available", 0)
            for color, usage in toner_usage.items()
        )

        base_media_cost = 0.05 * sheets_required
        base_toner_cost = 0.02 * sheets_required * max(len(toner_profile), 1)
        turnaround_modifier = self._turnaround_multiplier(choices.get("turnaround_time"))
        estimated_cost = round((base_media_cost + base_toner_cost) * turnaround_modifier, 2)

        # Build estimation reasoning for user
        quality_modifier = self.QUALITY_MODIFIERS.get(quality, 1.0)
        coverage_type = self._infer_coverage_type(analysis)
        reasoning = self._build_estimation_reasoning(
            quality=quality,
            quality_modifier=quality_modifier,
            coverage_type=coverage_type,
            color_mode=color_mode,
        )

        return {
            "sheets_required": sheets_required,
            "pages_per_copy": pages,
            "toner_usage": toner_usage,
            "media_ok": media_ok,
            "toner_ok": toner_ok,
            "estimated_cost": estimated_cost,
            "turnaround_modifier": turnaround_modifier,
            "quality": quality,
            "quality_modifier": quality_modifier,
            "coverage_type": coverage_type,
            "reasoning": reasoning,
            "warnings": self._build_warnings(media_ok, toner_ok),
        }

    def _calculate_toner_usage(
        self,
        sheets_required: int,
        toner_profile: list[str],
        color_mode: str,
        quality: str,
    ) -> Dict[str, float]:
        """Calculate toner usage with quality and coverage factors.

        Args:
            sheets_required: Total number of sheets to print
            toner_profile: List of toner colors needed (e.g., ["cyan", "magenta", "yellow", "black"])
            color_mode: Color mode selected (full_color, monochrome, etc.)
            quality: Print quality setting (draft, standard, high)

        Returns:
            Dictionary mapping toner color to mL usage
        """
        # Get quality modifier
        quality_modifier = self.QUALITY_MODIFIERS.get(quality, 1.0)

        # Get configurable values from .env (allows demo overrides)
        page_coverage = self._get_page_coverage()
        base_toner_ml = self._get_base_toner_ml()

        self.logger.debug(
            f"Estimator config: page_coverage={page_coverage:.2%}, "
            f"base_toner_ml={base_toner_ml}"
        )

        # Base calculation: sheets × coverage × base_consumption × quality_modifier
        base_usage_per_color = (
            sheets_required
            * page_coverage
            * base_toner_ml
            * quality_modifier
        )

        # For mono, only black is used
        # For full color, distribute usage across all colors
        if color_mode == "mono":
            # All usage goes to black
            toner_usage = {color: round(base_usage_per_color, 2) for color in toner_profile}
        else:
            # In full color mode, each color gets proportional usage
            # Cyan, Magenta, Yellow typically get equal usage
            # Black gets slightly more (used in text and shadows)
            toner_usage = {}
            for color in toner_profile:
                if color == "black":
                    # Black gets 1.3x usage (text + shadows)
                    toner_usage[color] = round(base_usage_per_color * 1.3, 2)
                else:
                    # CMY get standard usage
                    toner_usage[color] = round(base_usage_per_color, 2)

        self.logger.debug(f"Toner usage calculated: {toner_usage}")
        return toner_usage

    def _infer_coverage_type(self, analysis: Dict[str, Any]) -> str:
        """Infer page coverage type from PDF analysis.

        In the future, this could use actual PDF analysis.
        For now, we default to text_normal.

        Args:
            analysis: PDF analysis data

        Returns:
            Coverage type string (e.g., "text_normal")
        """
        # Future enhancement: analyze PDF content to determine coverage
        # For now, assume normal text coverage
        return "text_normal"

    def _build_estimation_reasoning(
        self,
        quality: str,
        quality_modifier: float,
        coverage_type: str,
        color_mode: str,
    ) -> str:
        """Build human-readable reasoning for the estimate.

        Args:
            quality: Quality setting
            quality_modifier: Numeric quality modifier
            coverage_type: Page coverage type
            color_mode: Color mode

        Returns:
            Formatted reasoning string
        """
        quality_desc = {
            "draft": "Draft quality uses 30% less toner with lighter print density.",
            "standard": "Standard quality provides balanced toner usage and print quality.",
            "high": "High quality uses 20% more toner for darker, richer output.",
        }

        coverage_desc = {
            "text_light": "Light text documents (5% page coverage)",
            "text_normal": "Normal text documents (10% page coverage)",
            "text_heavy": "Text-heavy documents with tables (15% page coverage)",
            "graphics": "Documents with graphics (25% page coverage)",
            "photos": "Photo-heavy documents (50% page coverage)",
        }

        mode_desc = {
            "mono": "Monochrome printing uses only black toner.",
            "full_color": "Full color printing uses all color channels with increased black usage for text and shadows.",
        }

        reasoning_parts = [
            quality_desc.get(quality, "Standard quality assumed."),
            f"Estimated as {coverage_desc.get(coverage_type, 'normal document')}.",
            mode_desc.get(color_mode, ""),
        ]

        return " ".join(part for part in reasoning_parts if part)

    @staticmethod
    def _turnaround_multiplier(turnaround: str | None) -> float:
        mapping = {
            "rush": 1.4,
            "standard": 1.0,
            "economy": 0.85,
        }
        return mapping.get(turnaround or "standard", 1.0)

    @staticmethod
    def _build_warnings(media_ok: bool, toner_ok: bool) -> list[str]:
        warnings: list[str] = []
        if not media_ok:
            warnings.append("Requested quantity exceeds available media.")
        if not toner_ok:
            warnings.append("Insufficient toner projected for this job.")
        return warnings
