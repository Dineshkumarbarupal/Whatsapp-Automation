from __future__ import annotations

import re
import time
import webbrowser

from py.services.contacts import normalize_phone, PHONE_RE


class GUIAutomationError(RuntimeError):
    pass


class WhatsAppGUIDriver:
    """Visible, operator-supervised desktop helper. No stealth or unattended messaging."""

    WHATSAPP_WEB_URL = "https://web.whatsapp.com/"

    def __init__(self, delay_seconds: float = 1.0):
        self.delay = max(0.4, min(float(delay_seconds), 5.0))

    def open_web(self) -> dict:
        opened = webbrowser.open(self.WHATSAPP_WEB_URL, new=2)
        return {
            "opened": bool(opened),
            "url": self.WHATSAPP_WEB_URL,
            "message": "WhatsApp Web opened. Sign in manually and keep the browser window visible before continuing.",
        }

    @staticmethod
    def _normal(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()

    def _find_text_box(self, target: str):
        try:
            import pyautogui
            import pytesseract
        except ImportError as exc:
            raise GUIAutomationError("GUI automation requires pyautogui, Pillow and pytesseract.") from exc
        screen = pyautogui.screenshot()
        data = pytesseract.image_to_data(screen, output_type=pytesseract.Output.DICT)
        wanted = self._normal(target)
        lines: dict[tuple[int, int, int], list[dict]] = {}
        for index, raw in enumerate(data.get("text", [])):
            word = self._normal(str(raw))
            if not word:
                continue
            key = (
                data.get("block_num", [0] * len(data["text"]))[index],
                data.get("par_num", [0] * len(data["text"]))[index],
                data.get("line_num", [0] * len(data["text"]))[index],
            )
            lines.setdefault(key, []).append({
                "word": word, "left": int(data["left"][index]), "top": int(data["top"][index]),
                "width": int(data["width"][index]), "height": int(data["height"][index])
            })
        for tokens in lines.values():
            phrase = " ".join(item["word"] for item in tokens)
            if wanted == phrase or wanted in phrase:
                left = min(item["left"] for item in tokens)
                top = min(item["top"] for item in tokens)
                right = max(item["left"] + item["width"] for item in tokens)
                bottom = max(item["top"] + item["height"] for item in tokens)
                return ((left + right) // 2, (top + bottom) // 2)
        return None

    def _click_text(self, labels, required=True):
        import pyautogui
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.25
        for label in labels:
            point = self._find_text_box(label)
            if point:
                pyautogui.click(*point)
                time.sleep(self.delay)
                return True
        if required:
            raise GUIAutomationError("Could not locate the expected WhatsApp control on screen: " + ", ".join(labels) + ". Check the language, window size and current screen.")
        return False

    def _type_text(self, value: str):
        import pyautogui
        if not value or any(ord(char) > 127 for char in value):
            try:
                import pyperclip
                pyperclip.copy(value)
                pyautogui.hotkey("ctrl", "v")
            except ImportError as exc:
                raise GUIAutomationError("Install pyperclip for non-ASCII text or use English characters.") from exc
        else:
            pyautogui.write(value, interval=0.025)
        time.sleep(self.delay)

    def _validate_participants(self, participants: list[str]) -> list[str]:
        clean: list[str] = []
        for value in participants:
            phone = normalize_phone(str(value))
            if not PHONE_RE.fullmatch(phone):
                raise ValueError(f"Invalid participant phone number: {value!r}")
            if phone not in clean:
                clean.append(phone)
        if not clean:
            raise ValueError("At least one participant number is required.")
        if len(clean) > 20:
            raise ValueError("For safety, a single supervised GUI run is limited to 20 participants.")
        return clean

    def create_group(self, group_name: str, participants: list[str]) -> dict:
        name = (group_name or "").strip()
        if not name or len(name) > 80:
            raise ValueError("Group name must contain 1 to 80 characters.")
        numbers = self._validate_participants(participants)
        self._click_text(("New chat", "New conversation"))
        self._click_text(("New group", "New group chat"))
        for number in numbers:
            self._click_text(("Search name or number", "Search"), required=True)
            self._type_text(number)
            self._click_text((number, number.lstrip("+")))
        self._click_text(("Next", "Continue"))
        self._click_text(("Group subject", "Group name", "Subject"))
        self._type_text(name)
        self._click_text(("Create", "Done", "check"))
        return {"completed": True, "group_name": name, "participants_selected": len(numbers),
                "message": "The group creation sequence was submitted. Verify the resulting group in WhatsApp."}

    def add_members_to_current_group(self, participants: list[str]) -> dict:
        numbers = self._validate_participants(participants)
        self._click_text(("Add participant", "Add members", "Add people"))
        for number in numbers:
            self._click_text(("Search name or number", "Search"), required=True)
            self._type_text(number)
            self._click_text((number, number.lstrip("+")))
        self._click_text(("Add", "Done", "check"))
        return {"completed": True, "participants_selected": len(numbers),
                "message": "The add-members sequence was submitted. Verify the participant list in WhatsApp."}
