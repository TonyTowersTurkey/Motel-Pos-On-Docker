"""Guard the motel-wide 24-hour time display convention."""

import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class TwentyFourHourTimeFormatTest(SimpleTestCase):
    def test_django_uses_24_hour_time_formats(self) -> None:
        self.assertEqual(settings.TIME_FORMAT, "H:i")
        self.assertEqual(settings.SHORT_TIME_FORMAT, "H:i")
        self.assertIn("H:i", settings.DATETIME_FORMAT)
        self.assertIn("H:i", settings.SHORT_DATETIME_FORMAT)

    def test_templates_do_not_use_locale_default_time_format(self) -> None:
        template_root = Path(settings.BASE_DIR) / "templates"
        unsafe_calls: list[str] = []
        for path in template_root.rglob("*.html"):
            content = path.read_text(encoding="utf-8")
            if re.search(r"\.toLocale(?:Time)?String\(\s*\)", content):
                unsafe_calls.append(str(path.relative_to(template_root)))

        self.assertEqual(unsafe_calls, [])

    def test_explicit_locale_time_calls_disable_twelve_hour_output(self) -> None:
        template_root = Path(settings.BASE_DIR) / "templates"
        unsafe_calls: list[str] = []
        for path in template_root.rglob("*.html"):
            content = path.read_text(encoding="utf-8")
            for call in re.findall(
                r"\.toLocale(?:Time)?String\([^;\n]+",
                content,
            ):
                if "hour:" in call and "hour12:false" not in call:
                    unsafe_calls.append(f"{path.relative_to(template_root)}: {call}")

        self.assertEqual(unsafe_calls, [])
