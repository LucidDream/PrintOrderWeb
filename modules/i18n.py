"""
Internationalization (i18n) Module

Provides multi-language support for the Print Order Web application.

Supported languages:
- English (en)
- German (de)

Usage in templates:
    {{ _('key.path.to.string') }}

Usage in Python:
    from modules.i18n import translate
    message = translate('key.path.to.string', lang='en')
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Supported languages
SUPPORTED_LANGUAGES = {
    'en': {'name': 'English', 'flag': '🇺🇸', 'flag_emoji': 'US'},
    'de': {'name': 'Deutsch', 'flag': '🇩🇪', 'flag_emoji': 'DE'},
}

DEFAULT_LANGUAGE = 'en'

# Translation cache
_translations: Dict[str, Dict[str, Any]] = {}


class I18nManager:
    """Manages internationalization and translation loading."""

    def __init__(self, translations_dir: Optional[Path] = None):
        """
        Initialize i18n manager.

        Args:
            translations_dir: Path to translations directory.
                            Defaults to ./translations relative to this file.
        """
        if translations_dir is None:
            # Default to translations/ directory in project root
            translations_dir = Path(__file__).parent.parent / 'translations'

        self.translations_dir = translations_dir
        self._load_all_translations()

    def _load_all_translations(self) -> None:
        """Load all translation files from translations directory."""
        global _translations

        if not self.translations_dir.exists():
            logger.warning(
                f"Translations directory not found: {self.translations_dir}. "
                "Creating directory..."
            )
            self.translations_dir.mkdir(parents=True, exist_ok=True)
            return

        for lang_code in SUPPORTED_LANGUAGES.keys():
            self._load_translation(lang_code)

    def _load_translation(self, lang_code: str) -> None:
        """
        Load translation file for a specific language.

        Args:
            lang_code: Language code (e.g., 'en', 'de')
        """
        global _translations

        translation_file = self.translations_dir / f'{lang_code}.json'

        if not translation_file.exists():
            logger.warning(
                f"Translation file not found: {translation_file}. "
                f"Using empty translations for {lang_code}."
            )
            _translations[lang_code] = {}
            return

        try:
            with open(translation_file, 'r', encoding='utf-8') as f:
                _translations[lang_code] = json.load(f)
            logger.info(
                f"Loaded {len(_translations[lang_code])} translation keys "
                f"for language: {lang_code}"
            )
        except json.JSONDecodeError as e:
            logger.error(
                f"Failed to parse translation file {translation_file}: {e}"
            )
            _translations[lang_code] = {}
        except Exception as e:
            logger.error(
                f"Failed to load translation file {translation_file}: {e}"
            )
            _translations[lang_code] = {}

    def get_translation(
        self,
        key: str,
        lang: str = DEFAULT_LANGUAGE,
        **kwargs
    ) -> str:
        """
        Get translated string for a key.

        Supports nested keys using dot notation: 'section.subsection.key'
        Supports variable substitution: translate('hello', name='World')
            -> "Hello {name}!" becomes "Hello World!"

        Args:
            key: Translation key (supports dot notation)
            lang: Language code
            **kwargs: Variables for string formatting

        Returns:
            Translated string, or key if translation not found
        """
        if lang not in _translations:
            logger.warning(f"Language not loaded: {lang}. Using default: {DEFAULT_LANGUAGE}")
            lang = DEFAULT_LANGUAGE

        # Navigate nested dictionary using dot notation
        keys = key.split('.')
        value = _translations.get(lang, {})

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                value = None
                break

        if value is None:
            logger.debug(f"Translation key not found: {key} (lang: {lang})")
            return key  # Return key as fallback

        # Format string with variables if provided
        if kwargs:
            try:
                return value.format(**kwargs)
            except KeyError as e:
                logger.warning(
                    f"Missing variable in translation: {e} "
                    f"(key: {key}, lang: {lang})"
                )
                return value
        else:
            return value

    def get_all_languages(self) -> Dict[str, Dict[str, str]]:
        """
        Get all supported languages with metadata.

        Returns:
            Dict mapping language codes to language info
        """
        return SUPPORTED_LANGUAGES

    def is_language_supported(self, lang_code: str) -> bool:
        """
        Check if a language is supported.

        Args:
            lang_code: Language code to check

        Returns:
            True if supported, False otherwise
        """
        return lang_code in SUPPORTED_LANGUAGES


# Global i18n manager instance
i18n_manager = I18nManager()


def translate(key: str, lang: str = DEFAULT_LANGUAGE, **kwargs) -> str:
    """
    Translate a key to the specified language.

    This is the main entry point for translations in Python code.

    Args:
        key: Translation key (supports dot notation)
        lang: Language code
        **kwargs: Variables for string formatting

    Returns:
        Translated string

    Example:
        >>> translate('common.welcome', lang='en')
        'Welcome'
        >>> translate('common.hello', lang='de', name='Hans')
        'Hallo Hans!'
    """
    return i18n_manager.get_translation(key, lang, **kwargs)


def get_supported_languages() -> Dict[str, Dict[str, str]]:
    """
    Get all supported languages.

    Returns:
        Dict mapping language codes to language metadata
    """
    return i18n_manager.get_all_languages()


# Flask template filter
def create_translation_filter(current_language: str):
    """
    Create a translation filter function for Flask templates.

    Args:
        current_language: Current language code from session

    Returns:
        Translation filter function

    Usage in Flask:
        @app.context_processor
        def inject_translator():
            lang = session.get('language', 'en')
            return {'_': create_translation_filter(lang)}
    """
    def translation_filter(key: str, **kwargs) -> str:
        return translate(key, lang=current_language, **kwargs)

    return translation_filter
