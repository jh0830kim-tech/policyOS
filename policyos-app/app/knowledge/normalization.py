"""Conservative text normalization that preserves evidentiary structure."""

import re
import unicodedata

NORMALIZATION_VERSION = "1.0.0"


class TextNormalizer:
    version = NORMALIZATION_VERSION

    def normalize(self, text: str) -> str:
        text = unicodedata.normalize("NFC", text).replace("\r\n", "\n").replace("\r", "\n")
        lines = [re.sub(r"[\t ]+", " ", line).strip() for line in text.split("\n")]
        normalized: list[str] = []
        blank = False
        for line in lines:
            if not line:
                if normalized and not blank:
                    normalized.append("")
                blank = True
                continue
            normalized.append(line)
            blank = False
        return "\n".join(normalized).strip()


class HeaderFooterRemovalHook:
    """Opt-in hook; the default intentionally does not remove repeated evidence."""

    def remove(self, sections: list[str]) -> list[str]:
        return sections