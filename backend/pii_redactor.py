"""
PII Redaction module using Microsoft Presidio.
Detects and anonymizes sensitive information before embedding.
Includes graceful fallback if Presidio/spaCy models are missing.
"""

# Lazy-loaded global instances
_analyzer = None
_anonymizer = None
_presidio_available = True


def _get_engines():
    """Initialize Presidio engines safely (cached after first call)."""
    global _analyzer, _anonymizer, _presidio_available
    if not _presidio_available:
        return None, None

    if _analyzer is None:
        try:
            from presidio_analyzer import AnalyzerEngine
            from presidio_anonymizer import AnonymizerEngine
            print("[PII Redactor] Initializing Presidio engines...")
            _analyzer = AnalyzerEngine()
            _anonymizer = AnonymizerEngine()
            print("[PII Redactor] Engines ready.")
        except Exception as e:
            print(f"[PII Redactor] WARNING: Presidio init failed ({e}). Proceeding without PII redaction.")
            _presidio_available = False
            return None, None

    return _analyzer, _anonymizer


def redact_pii(text: str, language: str = "en") -> str:
    """Detect and redact PII entities from text.

    Args:
        text: The input text to redact.
        language: Language code for analysis.

    Returns:
        Redacted text with PII replaced by entity type tags (e.g., <PHONE_NUMBER>).
    """
    from config import settings

    if not text or not text.strip():
        return text

    # If PII Redaction is toggled off in settings, retain raw text
    if not settings.enable_pii_redaction:
        return text

    try:

        analyzer, anonymizer = _get_engines()
        if not analyzer or not anonymizer:
            return text

        results = analyzer.analyze(
            text=text,
            language=language,
            entities=[
                "PHONE_NUMBER",
                "EMAIL_ADDRESS",
                "CREDIT_CARD",
                "US_SSN",
                "PERSON",
                "LOCATION",
                "DATE_TIME",
                "US_DRIVER_LICENSE",
                "MEDICAL_LICENSE",
                "IP_ADDRESS",
            ],
        )

        if not results:
            return text

        anonymized = anonymizer.anonymize(text=text, analyzer_results=results)
        return anonymized.text
    except Exception as err:
        print(f"[PII Redactor] Redaction error ({err}), returning un-redacted text.")
        return text


def redact_pii_batch(texts: list[str], language: str = "en") -> list[str]:
    """Redact PII from a batch of texts."""
    return [redact_pii(text, language) for text in texts]
