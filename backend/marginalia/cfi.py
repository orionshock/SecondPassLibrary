"""Syntax-only validation for durable, compact EPUB CFIs."""

from django.core.exceptions import ValidationError


CFI_PROFILE_ERROR = "CFI must use the supported compact structural profile."

# Historical Reader ID assertions are 21-22 characters. Allow longer XML IDs,
# but keep the CFI a compact locator rather than a store for book text.
MAX_ASSERTION_LENGTH = 128
MAX_TOTAL_ASSERTION_LENGTH = 256

# XML 1.0 Fifth Edition, NameStartChar outside the ASCII letters and underscore.
# Colons are excluded: the Web Reader splits CFI components on ':'.
_XML_NAME_START_RANGES = (
    (0xC0, 0xD6),
    (0xD8, 0xF6),
    (0xF8, 0x2FF),
    (0x370, 0x37D),
    (0x37F, 0x1FFF),
    (0x200C, 0x200D),
    (0x2070, 0x218F),
    (0x2C00, 0x2FEF),
    (0x3001, 0xD7FF),
    (0xF900, 0xFDCF),
    (0xFDF0, 0xFFFD),
    (0x10000, 0xEFFFF),
)


def validate_durable_cfi(value: str) -> None:
    if not is_supported_durable_cfi(value):
        raise ValidationError(CFI_PROFILE_ERROR)


def is_supported_durable_cfi(value: object) -> bool:
    if (
        not isinstance(value, str)
        or not value.startswith("epubcfi(")
        or not value.endswith(")")
    ):
        return False
    parts = value[8:-1].split(",")
    if len(parts) not in (1, 3):
        return False

    common = _StructuralPath(parts[0])
    if not common.parse_absolute(allow_offset=len(parts) == 1):
        return False
    ends = [_StructuralPath(part) for part in parts[1:]]
    return (
        all(end.parse_range_end() for end in ends)
        and sum(path.assertion_length for path in [common, *ends])
        <= MAX_TOTAL_ASSERTION_LENGTH
    )


class _StructuralPath:
    def __init__(self, value: str):
        self.value = value
        self.position = 0
        self.assertion_length = 0

    def parse_absolute(self, *, allow_offset: bool) -> bool:
        first = self._steps()
        # Standard EPUB CFIs start at the package spine, an even element step.
        if first is None or first == "0" or first[-1] not in "02468":
            return False
        while self._take("!"):
            if self._steps() is None:
                return False
        if allow_offset and self._take(":") and self._integer() is None:
            return False
        return self.position == len(self.value)

    def parse_range_end(self) -> bool:
        steps = self._steps()
        if steps is None and not self._take(":"):
            return False
        if steps is None:
            return self._integer() is not None and self.position == len(self.value)
        if self._take(":") and self._integer() is None:
            return False
        return self.position == len(self.value)

    def _steps(self) -> str | None:
        first = None
        while self._take("/"):
            step = self._integer()
            if step is None:
                return None
            if self.position < len(self.value) and self.value[self.position] == "[":
                if step == "0" or step[-1] not in "02468":
                    return None
            if not self._id_assertion():
                return None
            if first is None:
                first = step
        return first

    def _id_assertion(self) -> bool:
        if not self._take("["):
            return True
        start = self.position
        close = self.value.find("]", start)
        if close < 0:
            return False
        identifier = self.value[start:close]
        if len(identifier) > MAX_ASSERTION_LENGTH or not _is_xml_ncname(identifier):
            return False
        self.assertion_length += len(identifier)
        self.position = close + 1
        return True

    def _integer(self) -> str | None:
        start = self.position
        if (
            self.position >= len(self.value)
            or self.value[self.position] not in "0123456789"
        ):
            return None
        self.position += 1
        if self.value[start] == "0":
            if (
                self.position < len(self.value)
                and self.value[self.position] in "0123456789"
            ):
                return None
        else:
            while (
                self.position < len(self.value)
                and self.value[self.position] in "0123456789"
            ):
                self.position += 1
        return self.value[start : self.position]

    def _take(self, token: str) -> bool:
        if self.position < len(self.value) and self.value[self.position] == token:
            self.position += 1
            return True
        return False


def _is_xml_ncname(value: str) -> bool:
    return (
        bool(value)
        and _is_xml_name_start(value[0])
        and all(_is_xml_name_char(char) for char in value[1:])
    )


def _is_xml_name_start(char: str) -> bool:
    point = ord(char)
    return (
        char == "_"
        or 0x41 <= point <= 0x5A
        or 0x61 <= point <= 0x7A
        or any(lower <= point <= upper for lower, upper in _XML_NAME_START_RANGES)
    )


def _is_xml_name_char(char: str) -> bool:
    point = ord(char)
    return (
        _is_xml_name_start(char)
        or char in "-."
        or 0x30 <= point <= 0x39
        or point == 0xB7
        or 0x300 <= point <= 0x36F
        or 0x203F <= point <= 0x2040
    )
