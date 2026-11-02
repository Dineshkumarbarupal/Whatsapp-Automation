from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

from py.services.contacts import normalize_phone, PHONE_RE


@dataclass(frozen=True)
class OcrCandidate:
    display_name: str
    phone: str = ""
    confidence: float = 0.0
    raw_text: str = ""


class OCRUnavailable(RuntimeError):
    pass


class ScreenOCR:
    """Read the currently visible desktop only. Screenshots are never persisted."""

    UI_NOISE = {
        "participants", "group info", "group information", "add participant",
        "add members", "search", "search name or number", "media links and docs",
        "media links docs", "disappearing messages", "exit group", "report group",
        "mute notifications", "custom notifications", "encryption", "cancel",
        "done", "close", "back", "view all", "see all", "admin", "you",
    }

    def __init__(self, tesseract_cmd: str = "", language: str = "eng"):
        self.tesseract_cmd = tesseract_cmd
        self.language = language

    def _dependencies(self):
        try:
            import pyautogui
            import pytesseract
        except ImportError as exc:
            raise OCRUnavailable("Install PyAutoGUI, Pillow and pytesseract to enable screen OCR.") from exc
        if self.tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = self.tesseract_cmd
        return pyautogui, pytesseract

    def capture(self):
        pyautogui, pytesseract = self._dependencies()
        image = pyautogui.screenshot()
        try:
            text = pytesseract.image_to_string(image, lang=self.language, config="--psm 6")
            data = pytesseract.image_to_data(
                image, lang=self.language, config="--psm 6",
                output_type=pytesseract.Output.DICT
            )
        except Exception as exc:
            raise OCRUnavailable("Tesseract OCR failed: " + str(exc)) from exc

        grouped: dict[tuple[int, int, int], list[tuple[str, float]]] = {}
        tokens = data.get("text", [])
        for index, token in enumerate(tokens):
            token = str(token or "").strip()
            if not token:
                continue
            try:
                score = float(data.get("conf", [0] * len(tokens))[index])
            except (TypeError, ValueError, IndexError):
                score = 0.0
            key = (
                int(data.get("block_num", [0] * len(tokens))[index]),
                int(data.get("par_num", [0] * len(tokens))[index]),
                int(data.get("line_num", [0] * len(tokens))[index]),
            )
            grouped.setdefault(key, []).append((token, max(0.0, score)))

        confidence: dict[str, float] = {}
        for parts in grouped.values():
            line = " ".join(token for token, _ in parts)
            scores = [score for _, score in parts if score > 0]
            if line:
                confidence[line] = round(sum(scores) / len(scores), 1) if scores else 0.0
        return image, text, confidence

    @classmethod
    def _is_likely_name(cls, value: str) -> bool:
        normalized = " ".join(value.casefold().split()).strip(" .,;:|-/")
        if len(normalized) < 2 or normalized in cls.UI_NOISE:
            return False
        if normalized.startswith(("participants ", "group members ", "members (")):
            return False
        if re.fullmatch(r"[\d\s()+./:-]+", normalized):
            return False
        return any(char.isalpha() for char in normalized)

    def extract_candidates(self, raw_text: str, line_confidence: dict[str, float] | None = None) -> list[dict[str, Any]]:
        confidence_map = line_confidence or {}
        candidates: list[OcrCandidate] = []
        for raw_line in raw_text.splitlines():
            line = " ".join(raw_line.split()).strip(" |\t")
            if len(line) < 2:
                continue
            phone = ""
            selected_match = ""
            for match in re.findall(r"\+?[0-9][0-9\s().-]{6,}[0-9]", line):
                normalized = normalize_phone(match)
                if PHONE_RE.fullmatch(normalized):
                    phone, selected_match = normalized, match
                    break
            name = line.replace(selected_match, " ").strip(" -|:") if phone else line
            if phone:
                if name and not self._is_likely_name(name):
                    name = ""
            elif not self._is_likely_name(name):
                continue
            confidence = float(confidence_map.get(line, 0.0))
            candidates.append(OcrCandidate(name[:120], phone, confidence, line[:240]))

        unique: dict[tuple[str, str], OcrCandidate] = {}
        for item in candidates:
            key = ("phone", item.phone) if item.phone else ("name", " ".join(item.display_name.casefold().split()))
            previous = unique.get(key)
            if previous is None or item.confidence > previous.confidence:
                unique[key] = item
        return [asdict(item) for item in unique.values()]

    def capture_and_extract(self) -> dict[str, Any]:
        image, text, confidence = self.capture()
        candidates = self.extract_candidates(text, confidence)
        return {
            "text": text[:12000],
            "candidates": candidates,
            "image_size": list(image.size),
            "candidate_count": len(candidates),
        }
