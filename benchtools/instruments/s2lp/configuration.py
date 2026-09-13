"""Register values read from a file, applied to a radio and checked against it.

A radio configuration is a list of register values. Keeping that list in a file
rather than in a test lets the two be reviewed and changed separately: the person
who worked out the settings is rarely the person writing the specification, and a
setting that moves should not require a code change.

The file is deliberately forgiving about its shape and strict about its content.
Forgiving, because these files are written by hand and exported by tools that
each punctuate differently::

    # 915 MHz, 38.4 kbps, basic packets
    PCKTCTRL3   0x20        # comments after a value are fine
    PCKTCTRL2 = 0x01
    MOD2: 27                 ; values are hexadecimal, 0x optional
    0x10, 27                 // an address instead of a name

Strict, because every one of those lines ends up written to a radio. An unknown
register name, a value that does not fit a byte, a register named twice, or a
write to a read-only register is an error that names the file and the line - not
something to interpret generously.

**Values are hexadecimal**, with or without ``0x``. That is what a register file
carries, and guessing per line - ``10`` as ten in one file and sixteen in the
next - would be the kind of ambiguity that produces a radio configured almost
right.

Traces to: S2LP-FR-017 .. S2LP-FR-019, S2LP-DD-CONFIG.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, Iterator, List, Optional, Sequence, Tuple, Union

from ...core.errors import ConfigurationError
from . import registers as reg

__all__ = [
    "RegisterSetting",
    "RegisterConfiguration",
    "ConfigurationCheck",
    "parse_register_file",
    "load_register_file",
    "format_register_file",
]

#: Everything from a comment marker to the end of the line.
_COMMENT = re.compile(r"(#|;|//).*$")

#: ``NAME = VALUE`` with any of space, ``=``, ``:`` or ``,`` between them.
#:
#: A C ``#define`` line is deliberately *not* accepted. It would have to be
#: distinguished from a comment by looking at what follows the ``#``, and a file
#: format in which ``#`` sometimes starts a comment and sometimes does not is
#: one where a typo turns a setting into a comment silently.
_LINE = re.compile(
    r"^\s*(?P<name>[A-Za-z_][A-Za-z0-9_]*|0[xX][0-9A-Fa-f]+|\d+)"
    r"\s*[=:,\s]\s*(?P<value>0[xX][0-9A-Fa-f]+|[0-9A-Fa-f]+)\s*$"
)


def _parse_value(text: str, where: str) -> int:
    """One register value: hexadecimal, with or without ``0x``."""
    cleaned = text.strip()
    body = cleaned[2:] if cleaned[:2].lower() == "0x" else cleaned
    try:
        value = int(body, 16)
    except ValueError:
        raise ConfigurationError("%s: %r is not a hexadecimal value" % (where, text)) from None
    if not 0 <= value <= 0xFF:
        raise ConfigurationError(
            "%s: 0x%X does not fit in a register, which is one byte" % (where, value)
        )
    return value


@dataclass(frozen=True)
class RegisterSetting:
    """One register and the value a file asks for."""

    register: reg.Register
    value: int
    line: int = 0

    @property
    def name(self) -> str:
        return self.register.name

    @property
    def address(self) -> int:
        return self.register.address

    def describe(self) -> str:
        """The setting as a dump line, with its fields decoded."""
        return self.register.describe(self.value)

    def as_dict(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "address": "0x%02X" % self.address,
            "value": "0x%02X" % self.value,
            "line": self.line,
            "fields": self.register.decode(self.value),
        }


@dataclass
class RegisterConfiguration:
    """The register values one file asks for, in the order it asked for them.

    Order is kept because it is occasionally load-bearing: some settings only
    take effect when written after another, and a file that was written in a
    working order should be applied in that order.
    """

    settings: Tuple[RegisterSetting, ...] = ()
    source: str = ""
    name: str = ""

    def __len__(self) -> int:
        return len(self.settings)

    def __iter__(self) -> Iterator[RegisterSetting]:
        return iter(self.settings)

    def __bool__(self) -> bool:
        return bool(self.settings)

    @property
    def names(self) -> List[str]:
        return [setting.name for setting in self.settings]

    @property
    def addresses(self) -> List[int]:
        return [setting.address for setting in self.settings]

    def as_map(self) -> Dict[int, int]:
        """Address to value."""
        return {setting.address: setting.value for setting in self.settings}

    def get(self, which: Union[int, str]) -> Optional[int]:
        """The value this configuration asks for, or ``None`` if it says nothing."""
        register = reg.lookup(which)
        return self.as_map().get(register.address)

    def describe(self) -> str:
        """Every setting as a dump line."""
        return "\n".join(setting.describe() for setting in self.settings)

    def as_dict(self) -> Dict[str, object]:
        return {
            "source": self.source,
            "name": self.name,
            "count": len(self.settings),
            "settings": [setting.as_dict() for setting in self.settings],
        }

    def __str__(self) -> str:
        return "%s (%d register(s) from %s)" % (
            self.name or "register configuration", len(self.settings), self.source or "text"
        )


@dataclass
class ConfigurationCheck:
    """What a radio's registers say, against what a file asked for.

    :param mismatches: Register name to ``(expected, actual)``, for registers the
        file named and the radio disagrees about.
    :param unexpected: Register name to ``(reset, actual)``, for registers the
        file did **not** name that are not at their reset value. Only collected
        for a strict check.
    """

    source: str = ""
    checked: int = 0
    mismatches: Dict[str, Tuple[int, int]] = field(default_factory=dict)
    unexpected: Dict[str, Tuple[int, int]] = field(default_factory=dict)
    strict: bool = False

    @property
    def matches(self) -> bool:
        """True when the radio holds the configuration that was asked for.

        For a strict check this also requires that nothing else has been
        changed from its reset value.
        """
        return not self.mismatches and not (self.strict and self.unexpected)

    def describe(self) -> str:
        """One line, or a short account of what differs."""
        if self.matches:
            return "%d register(s) match %s%s" % (
                self.checked, self.source or "the configuration",
                " and nothing else is set" if self.strict else "",
            )
        parts = []
        if self.mismatches:
            parts.append(
                "%d differ: %s"
                % (
                    len(self.mismatches),
                    ", ".join(
                        "%s expected 0x%02X, read 0x%02X" % (name, expected, actual)
                        for name, (expected, actual) in sorted(self.mismatches.items())
                    ),
                )
            )
        if self.strict and self.unexpected:
            parts.append(
                "%d set but not named by the file: %s"
                % (
                    len(self.unexpected),
                    ", ".join(
                        "%s = 0x%02X" % (name, actual)
                        for name, (_reset, actual) in sorted(self.unexpected.items())
                    ),
                )
            )
        return "; ".join(parts)

    def as_dict(self) -> Dict[str, object]:
        return {
            "source": self.source,
            "checked": self.checked,
            "matches": self.matches,
            "strict": self.strict,
            "mismatches": {
                name: {"expected": "0x%02X" % expected, "actual": "0x%02X" % actual}
                for name, (expected, actual) in sorted(self.mismatches.items())
            },
            "unexpected": {
                name: {"reset": "0x%02X" % reset, "actual": "0x%02X" % actual}
                for name, (reset, actual) in sorted(self.unexpected.items())
            },
            "summary": self.describe(),
        }


# ---------------------------------------------------------------------------
def parse_register_file(text: str, source: str = "", name: str = "") -> RegisterConfiguration:
    """Parse the text of a register file.

    :raises ConfigurationError: naming the file and the line, for a line that is
        not a setting, an unknown register, a value that does not fit a byte, a
        read-only register, or a register set twice.
    """
    settings: List[RegisterSetting] = []
    seen: Dict[int, int] = {}

    for number, raw in enumerate(text.splitlines(), start=1):
        line = _COMMENT.sub("", raw).strip()
        if not line:
            continue
        where = "%s line %d" % (source or "register file", number)

        match = _LINE.match(line)
        if match is None:
            raise ConfigurationError(
                "%s: cannot read %r as a register and a value. Expected a name "
                "or address, then a value, e.g. 'PCKTCTRL3 0x20'." % (where, raw.strip())
            )

        try:
            register = reg.lookup(match.group("name"))
        except KeyError as exc:
            raise ConfigurationError("%s: %s" % (where, exc.args[0])) from None

        if not register.writable:
            raise ConfigurationError(
                "%s: %s is read-only on this device, so a file cannot set it. "
                "The radio would ignore the write and read back its own value."
                % (where, register)
            )

        if register.address in seen:
            raise ConfigurationError(
                "%s: %s is already set on line %d. A file that sets a register "
                "twice does not say what it wants."
                % (where, register, seen[register.address])
            )

        seen[register.address] = number
        settings.append(
            RegisterSetting(register=register,
                            value=_parse_value(match.group("value"), where),
                            line=number)
        )

    return RegisterConfiguration(settings=tuple(settings), source=source, name=name)


def load_register_file(path: str) -> RegisterConfiguration:
    """Read a register file from disk.

    :raises ConfigurationError: if the file is missing, unreadable, or empty -
        an empty configuration would apply nothing and verify against nothing,
        and would do it silently.
    """
    try:
        with open(path, "r", encoding="utf-8") as handle:
            text = handle.read()
    except OSError as exc:
        raise ConfigurationError("cannot read the register file %s: %s" % (path, exc)) from exc

    configuration = parse_register_file(text, source=path, name=path)
    if not configuration:
        raise ConfigurationError(
            "%s names no registers. An empty configuration would be applied and "
            "verified without doing anything, and without saying so." % path
        )
    return configuration


def format_register_file(
    values: Dict[int, int],
    title: str = "",
    only_changed: bool = False,
) -> str:
    """Render register values as a file this module can read back.

    Written so a radio configured by hand - or by the vendor's GUI - can be
    captured and replayed. Read-only registers are left out: a file that names
    one cannot be applied, and a captured configuration that cannot be applied
    is a trap rather than a record.

    :param only_changed: Write only the registers that differ from their reset
        value, which is usually the interesting part and always the shorter one.
    """
    lines = []
    if title:
        lines.extend("# %s" % part for part in title.splitlines())
    lines.append("# register  value   (values are hexadecimal)")
    for address in sorted(values):
        register = reg.BY_ADDRESS.get(address)
        if register is None or not register.writable:
            continue
        value = values[address]
        if only_changed and value == register.reset:
            continue
        decoded = " ".join(
            "%s=%d" % (item.name, item.extract(value))
            for item in register.fields if item.extract(value)
        )
        lines.append(
            "%-22s 0x%02X%s" % (register.name, value, "   # %s" % decoded if decoded else "")
        )
    return "\n".join(lines) + "\n"
