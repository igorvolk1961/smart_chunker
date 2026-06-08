"""
Утилиты для NLP-анализа текста (опционально, через SpaCy).
Используется для детекции глаголов при определении:
- начала нумерованных разделов (поиск первого глагола)
- типа чанка (section_title vs section_content)
"""

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Fallback regex-паттерн для детекции глаголов (грубая эвристика, без SpaCy).
# Использует консервативный подход: только окончания, которые почти наверняка
# являются глагольными. Для надёжного детектирования рекомендуется SpaCy.
_FALLBACK_VERB_PATTERN = re.compile(
    r'\b[а-яё]{3,}'
    r'(?:'
    r'[аеиоуыэюя]ть(?:ся)?'   # инфинитив (с гласной перед ть, чтобы не цеплять "сть")
    r'|ти(?:сь)?'              # инфинитив (нести, вести)
    r'|чь(?:ся)?'              # инфинитив (мочь, беречь)
    r'|ешь'                    # 2-е л. ед.ч. (1 спр.)
    r'|ет(?:е)?'               # 3-е л. ед.ч. / 2-е л. мн.ч. (1 спр.)
    r'|ем(?:те)?'              # 1-е л. мн.ч. (1 спр.)
    r'|ют(?:ся)?'              # 3-е л. мн.ч. (1 спр.)
    r'|ут(?:ся)?'              # 3-е л. мн.ч. (1 спр.)
    r'|ишь'                    # 2-е л. ед.ч. (2 спр.)
    r'|ит(?:е)?'               # 3-е л. ед.ч. / 2-е л. мн.ч. (2 спр.)
    r'|им(?:те)?'              # 1-е л. мн.ч. (2 спр.)
    r'|ат(?:ся)?'              # 3-е л. мн.ч. (2 спр.)
    r'|ят(?:ся)?'              # 3-е л. мн.ч. (2 спр.)
    r'|[аеиоуыэюя]л(?:а|о|и)?(?:сь|ся)?'  # прошедшее время (гласная + л)
    r'|йте'                    # повелительное наклонение мн.ч.
    r'|ю(?:т(?:ся)?)?'         # 1-е л. ед.ч. / 3-е л. мн.ч. (1 спр.)
    r'|у(?:т(?:ся)?)?'         # 1-е л. ед.ч. / 3-е л. мн.ч. (1 спр.)
    r')\b',
    re.IGNORECASE
)


class VerbDetector:
    """
    Детектор глаголов в тексте.
    
    Использует SpaCy с POS-теггингом если модель доступна.
    Если SpaCy не установлен или модель не найдена — использует
    грубый fallback на regex (только для русского языка).
    
    Args:
        config: Опциональная конфигурация с секцией 'nlp':
            - enabled (bool): Включить SpaCy (по умолчанию True)
            - model (str): Название модели SpaCy (по умолчанию 'ru_core_news_sm')
    """
    
    def __init__(self, config: Optional[dict] = None):
        self.nlp = None
        self.use_spacy = False
        self._init_spacy(config)
    
    @property
    def use_fallback(self) -> bool:
        """True if fallback regex is used (SpaCy not available or disabled)."""
        return not self.use_spacy
    
    def _init_spacy(self, config: Optional[dict] = None):
        """Инициализирует SpaCy если доступен и включён в конфиге."""
        nlp_config = (config or {}).get('nlp', {})
        
        if not nlp_config.get('enabled', True):
            logger.info("SpaCy отключён конфигом, используется fallback regex")
            return
        
        try:
            import spacy
            model = nlp_config.get('model', 'ru_core_news_sm')
            self.nlp = spacy.load(model)
            self.use_spacy = True
            logger.info("SpaCy загружен: модель '%s'", model)
        except ImportError:
            logger.warning(
                "SpaCy не установлен. Установите: pip install spacy && "
                "python -m spacy download ru_core_news_sm. "
                "Используется fallback regex."
            )
        except OSError:
            logger.warning(
                "Модель SpaCy не найдена. Установите: "
                "python -m spacy download ru_core_news_sm. "
                "Используется fallback regex."
            )
    
    def contains_verb(self, text: str) -> bool:
        """
        Проверяет, содержит ли текст хотя бы один глагол.
        
        Args:
            text: Текст для анализа
            
        Returns:
            True если в тексте есть хотя бы один глагол
        """
        if not text or not text.strip():
            return False
        
        if self.use_spacy and self.nlp:
            doc = self.nlp(text)
            return any(token.pos_ == 'VERB' for token in doc)
        
        # Fallback: грубая regex-проверка по окончаниям
        return bool(_FALLBACK_VERB_PATTERN.search(text))
