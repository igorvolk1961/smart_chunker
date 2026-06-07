"""
Tests for VerbDetector — verb detection with SpaCy (optional) and regex fallback.
"""

import pytest
from src.nlp_utils import VerbDetector


class TestVerbDetectorFallback:
    """Test VerbDetector using regex fallback (no SpaCy)."""

    @pytest.fixture
    def detector(self):
        """Create VerbDetector with NLP disabled (fallback regex only)."""
        return VerbDetector({"nlp": {"enabled": False}})

    def test_contains_verb_russian_past(self, detector):
        """Russian past tense verbs should be detected."""
        assert detector.contains_verb("Документ определял порядок работ.")
        assert detector.contains_verb("Он разработал новый метод.")

    def test_contains_verb_russian_infinitive(self, detector):
        """Russian infinitive verbs should be detected."""
        assert detector.contains_verb("Необходимо разработать план.")
        assert detector.contains_verb("Целью является определить требования.")

    def test_contains_verb_russian_present(self, detector):
        """Russian present tense verbs should be detected."""
        assert detector.contains_verb("Документ содержит требования.")
        assert detector.contains_verb("Система обеспечивает безопасность.")

    def test_contains_verb_russian_future(self, detector):
        """Russian future tense verbs should be detected."""
        assert detector.contains_verb("Мы будем использовать новый подход.")

    def test_no_verb_title_only(self, detector):
        """Title-only lines without verbs should return False."""
        assert not detector.contains_verb("1. Введение")
        assert not detector.contains_verb("1.1. Область применения")
        assert not detector.contains_verb("2. Основная часть")
        assert not detector.contains_verb("3. Заключение")

    def test_no_verb_noun_phrase(self, detector):
        """Noun phrases without verbs should return False."""
        assert not detector.contains_verb("Цели и задачи проекта")
        assert not detector.contains_verb("Нормативные ссылки")
        assert not detector.contains_verb("Общие положения")

    def test_no_verb_empty_text(self, detector):
        """Empty or whitespace text should return False."""
        assert not detector.contains_verb("")
        assert not detector.contains_verb("   ")

    def test_no_verb_numbers_only(self, detector):
        """Text with only numbers should return False."""
        assert not detector.contains_verb("1.")
        assert not detector.contains_verb("1.1.")

    def test_verb_in_mixed_text(self, detector):
        """Verbs in mixed text should be detected."""
        assert detector.contains_verb("Настоящий стандарт устанавливает требования.")
        assert detector.contains_verb("Работы выполняются в соответствии с графиком.")

    def test_verb_with_punctuation(self, detector):
        """Verbs surrounded by punctuation should be detected."""
        assert detector.contains_verb("Утверждаю:")
        assert detector.contains_verb("(далее - Система) обеспечивает выполнение функций.")

    def test_false_positive_avoidance(self, detector):
        """Words that look like verbs but aren't should not trigger."""
        # "лаборатория" ends with "-ла" but is a noun
        assert not detector.contains_verb("1. Лаборатория")
        # "итог" ends with "-ит" but is a noun
        assert not detector.contains_verb("1. Итог")
        # "метод" ends with no verb pattern
        assert not detector.contains_verb("1. Метод")


class TestVerbDetectorWithSpaCy:
    """Test VerbDetector with SpaCy enabled (if model available)."""

    @pytest.fixture
    def detector(self):
        """Create VerbDetector with NLP enabled."""
        return VerbDetector({"nlp": {"enabled": True, "model": "ru_core_news_sm"}})

    def test_spacy_loading(self, detector):
        """SpaCy model should load or gracefully fall back."""
        # If SpaCy is not installed or model not found, it should fall back to regex
        # In either case, contains_verb should work
        assert detector.nlp is not None or detector.use_fallback

    def test_verb_detection_with_spacy_or_fallback(self, detector):
        """Verb detection should work regardless of SpaCy availability."""
        assert detector.contains_verb("Документ определяет порядок.")
        assert not detector.contains_verb("1. Введение")
        assert not detector.contains_verb("Общие положения")


class TestVerbDetectorConfig:
    """Test VerbDetector configuration handling."""

    def test_default_config(self):
        """Should work with empty config (defaults to fallback)."""
        detector = VerbDetector({})
        assert detector.use_fallback is True

    def test_none_config(self):
        """Should work with None config."""
        detector = VerbDetector(None)
        assert detector.use_fallback is True

    def test_explicit_disable(self):
        """Should respect explicit disable."""
        detector = VerbDetector({"nlp": {"enabled": False}})
        assert detector.use_fallback is True

    def test_missing_nlp_section(self):
        """Should handle missing nlp section gracefully."""
        detector = VerbDetector({"other": {"key": "value"}})
        assert detector.use_fallback is True
