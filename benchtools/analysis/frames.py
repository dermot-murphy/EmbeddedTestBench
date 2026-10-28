"""Measures over decoded radio frames: filters, intervals, copies, groups, census (#243).

A device's frames are decoded by its plugin (#238); everything here works on
the decode, a dictionary, and knows no device. A field is named by a dotted
path into it - ``mux``, ``status.phase``, ``values.2`` - and a frame is chosen
by its type, its source and a ``where`` of such paths.

Three facts about a received frame are used, and each is a key the decoder
gives or the bench records:

* ``type`` and ``sensor_id`` in the decode name what a frame is and who sent
  it.
* ``frame.repeat`` in the decode counts the copies of one transmission: a
  sensor may send each frame several times, and a copy starts a new
  transmission when its repeat number is not higher than the last copy's
  from the same source and of the same type (:func:`transmissions`).
* :attr:`Frame.time_s` is when the host read it: the host's monotonic clock
  for a frame received in this process, or the wall clock for one read back
  from a packet log written before #243. Either way only differences are used.

Where a measure needs to know where a copy's values belong in a longer
sequence - the samples of a waveform, the parameters of a configuration - it
asks the plugin's ``frame_positions`` hook (:func:`compare_copies`); without
one, those measures are not taken.

Traces to: S2LP-FR-088 .. S2LP-FR-092, ANA-DD-FRAMES.
"""

from __future__ import annotations

import datetime
import json
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from ..core.errors import ConfigurationError, MeasurementError

__all__ = [
    "Frame", "MISSING", "field_value", "matches", "check_where", "select", "frames_from_log",
    "transmissions", "intervals", "census", "compare_copies", "distinct_per_group",
]

#: What :func:`field_value` gives for a path the decode does not have.
MISSING = object()


@dataclass
class Frame:
    """One received frame, as the measures read it.

    :param data: The payload.
    :param decoded: The decode, or None if there is none.
    :param time_s: When the host read it, in seconds on one clock.
    :param error: The receiver's error code; 0 for a frame received intact.
    :param decode_error: Why the payload could not be decoded, if it could not.
    :param board_s: The receiver board's own timer when it reported the
        frame, in seconds, or None. It has no USB in it, but it is the
        board's: it restarts with the board, and nothing else shares it.
    """

    data: bytes
    decoded: Optional[Dict[str, Any]]
    time_s: Optional[float]
    error: int = 0
    decode_error: str = ""
    board_s: Optional[float] = None

    @property
    def ok(self) -> bool:
        """Received intact and decoded."""
        return self.error == 0 and bool(self.decoded)

    @property
    def frame_type(self) -> Optional[str]:
        """The decode's ``type``."""
        return (self.decoded or {}).get("type")

    @property
    def source(self) -> Optional[str]:
        """The decode's ``sensor_id``, as text."""
        value = (self.decoded or {}).get("sensor_id")
        return None if value is None else str(value)

    @property
    def repeat(self) -> Optional[int]:
        """The decode's ``frame.repeat``: which copy of its transmission this is."""
        value = ((self.decoded or {}).get("frame") or {}).get("repeat")
        return None if value is None else int(value)

    @classmethod
    def from_packet(cls, packet: Any) -> "Frame":
        """A frame from an S2-LP :class:`~benchtools.instruments.s2lp.packets.Packet`."""
        board = getattr(packet, "board_time_us", None)
        return cls(data=bytes(packet.data), decoded=packet.decoded,
                   time_s=getattr(packet, "monotonic_s", None), error=packet.error,
                   decode_error=packet.decode_error,
                   board_s=None if board is None else board / 1e6)


def field_value(decoded: Optional[Mapping[str, Any]], path: str) -> Any:
    """The value at dotted *path* in *decoded*, or :data:`MISSING`.

    A part that is a whole number indexes a list: ``values.2`` is the third
    of ``values``.
    """
    value: Any = decoded if decoded is not None else {}
    for part in str(path).split("."):
        if isinstance(value, Mapping) and part in value:
            value = value[part]
        elif isinstance(value, (list, tuple)) and part.lstrip("-").isdigit() \
                and -len(value) <= int(part) < len(value):
            value = value[int(part)]
        else:
            return MISSING
    return value


def _same(actual: Any, wanted: Any) -> bool:
    """Whether a decoded value is the one a specification wrote.

    Equal values match, and so do two whose text is the same, ignoring case:
    a specification's ``axis: z`` matches a decode's ``"Z"``, and ``mux: "3"``
    a decode's 3. A true or false matches only itself.
    """
    if actual is MISSING:
        return False
    if isinstance(actual, bool) or isinstance(wanted, bool):
        return actual == wanted
    if actual == wanted:
        return True
    return str(actual).strip().lower() == str(wanted).strip().lower()


def matches(decoded: Optional[Mapping[str, Any]], where: Optional[Mapping[str, Any]]) -> bool:
    """Whether *decoded* has every value *where* asks for.

    *where* maps a dotted path to a value, or to a list of values any of
    which will do.
    """
    for path, wanted in (where or {}).items():
        actual = field_value(decoded, path)
        options = wanted if isinstance(wanted, (list, tuple)) else [wanted]
        if not any(_same(actual, option) for option in options):
            return False
    return True


def check_where(where: Any) -> Dict[str, Any]:
    """*where* as a mapping, or a refusal that says what it must be."""
    if where is None:
        return {}
    if not isinstance(where, Mapping):
        raise ConfigurationError(
            "where must map a field to the value it must have, e.g. {mux: 3}; got %r"
            % (where,))
    return dict(where)


def select(frames: Iterable[Frame], frame_type: Optional[str] = None,
           source: Optional[str] = None,
           where: Optional[Mapping[str, Any]] = None) -> List[Frame]:
    """The frames received intact, decoded, and of *frame_type* from *source* with *where*."""
    return [frame for frame in frames
            if frame.ok
            and (frame_type is None or frame.frame_type == frame_type)
            and (source is None or frame.source == str(source))
            and matches(frame.decoded, where)]


def _epoch_s(text: Any) -> Optional[float]:
    try:
        return datetime.datetime.fromisoformat(str(text)).timestamp()
    except (TypeError, ValueError):
        return None


def frames_from_log(path: str,
                    decoder: Optional[Callable[[bytes], Dict[str, Any]]] = None) -> List[Frame]:
    """The frames an S2-LP packet log received, in order.

    Each payload is decoded again with *decoder* when one is given, so a log
    is read by the plugin loaded now; otherwise the decode the log carries is
    used. The times are the log's ``monotonic_s`` when every received frame
    has one, else its ``host_time``: one clock for the whole log either way.
    A log appended to by two runs can still go backwards where the second
    starts; :func:`intervals` refuses that rather than measure it. A
    truncated last line is skipped, as :class:`PacketLog` reads it.
    """
    records = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except ValueError:
                continue
            if isinstance(record, dict) and record.get("direction") == "rx":
                records.append(record)
    monotonic = bool(records) and all(record.get("monotonic_s") is not None
                                      for record in records)
    frames = []
    for record in records:
        data = bytes.fromhex(record.get("hex") or "")
        error = int(record.get("error") or 0)
        decoded, decode_error = record.get("decoded"), record.get("decode_error") or ""
        if decoder is not None and data and not error:
            try:
                decoded, decode_error = decoder(data), ""
            except Exception as exc:  # pylint: disable=broad-except
                decoded, decode_error = None, str(exc) or type(exc).__name__
        when = (float(record["monotonic_s"]) if monotonic
                else _epoch_s(record.get("host_time")))
        board = record.get("board_time_us")
        frames.append(Frame(data=data, decoded=decoded, time_s=when, error=error,
                            decode_error=decode_error,
                            board_s=None if board is None else float(board) / 1e6))
    return frames


#: The longest time between two copies of one transmission, in seconds. The
#: copies of one packet from Kepler 5C1712 came 31 to 229 ms apart (#293); a
#: copy later than this after the last is a new transmission whatever its
#: repeat number, so a lost first copy does not join two transmissions.
COPY_GAP_S = 2.0


def transmissions(frames: Sequence[Frame],
                  copy_gap: Optional[float] = COPY_GAP_S) -> List[List[Frame]]:
    """*frames* grouped into transmissions: each a list of its copies, in order.

    A copy belongs to the last transmission from the same source and of the
    same type when its repeat number is higher than the last copy's there,
    and, with both timed, it came within *copy_gap* seconds of it; otherwise
    it starts a new one. A frame with no repeat number is a transmission of
    its own. One case is still read as one transmission when it was two:
    only an early copy of one heard, then within *copy_gap* only later
    copies of the next.
    """
    groups: List[List[Frame]] = []
    open_group: Dict[Tuple[Optional[str], Optional[str]], List[Frame]] = {}
    for frame in frames:
        key = (frame.source, frame.frame_type)
        last = open_group.get(key)
        repeat = frame.repeat
        if last is not None and repeat is not None and last[-1].repeat is not None \
                and repeat > last[-1].repeat and _close(last[-1], frame, copy_gap):
            last.append(frame)
            continue
        group = [frame]
        groups.append(group)
        open_group[key] = group
    return groups


def _close(earlier: Frame, later: Frame, gap: Optional[float]) -> bool:
    """Whether *later* came within *gap* seconds of *earlier*, or either is untimed."""
    if gap is None or earlier.time_s is None or later.time_s is None:
        return True
    return later.time_s - earlier.time_s <= float(gap)


def _stats(values: Sequence[float]) -> Dict[str, Optional[float]]:
    return {
        "minimum": min(values) if values else None,
        "maximum": max(values) if values else None,
        "mean": sum(values) / len(values) if values else None,
    }


#: The clocks :func:`intervals` can time by.
CLOCKS = ("host", "board")


def intervals(  # pylint: disable=too-many-arguments,too-many-locals
        frames: Sequence[Frame], burst_gap: Optional[float] = None,
        above: Optional[float] = None, below: Optional[float] = None,
        clock: str = "host") -> Dict[str, Any]:
    """The time between transmissions, or between bursts of them.

    Each transmission is timed by its first copy heard. With *burst_gap*,
    a transmission that starts less than *burst_gap* seconds after the one
    before joins its burst - a command and its retries - so a chain of
    transmissions each closer than that to the last is one burst, however
    long. The intervals are between the bursts' starts.

    :param clock: ``"host"`` (the default), when the host read each frame:
        the clock BLE dongle events are on, so a frame can be timed from one,
        and the one every packet log has. ``"board"``, the receiver board's
        own timer: free of the USB link's jitter, but it restarts with the
        board and nothing else shares it.

    :returns: ``frames``, ``transmissions``, ``bursts``, ``count`` (intervals),
        ``minimum``, ``maximum``, ``mean``, ``above`` and ``below`` (how many
        intervals are longer than *above* or shorter than *below*; None when
        not asked), ``largest_burst`` (transmissions), ``first_s`` and
        ``last_s`` (on the frames' clock), and ``intervals`` themselves.
    :raises MeasurementError: if a frame has no time on *clock*, or the times
        go backwards - a log appended to by two runs, or a board that
        restarted.
    :raises ConfigurationError: for a clock that is not one of :data:`CLOCKS`.
    """
    if clock not in CLOCKS:
        raise ConfigurationError("%r is not a clock; they are %s" % (clock, ", ".join(CLOCKS)))
    groups = transmissions(frames)
    starts = []
    for group in groups:
        when = group[0].time_s if clock == "host" else group[0].board_s
        if when is None:
            raise MeasurementError("a frame has no %s time to measure an interval from" % clock)
        if starts and when < starts[-1]:
            raise MeasurementError(
                "the %s times go backwards, from %.6f s to %.6f s: a log appended to by "
                "two runs, or a board that restarted, has no single interval to measure"
                % (clock, starts[-1], when))
        starts.append(when)
    bursts: List[List[float]] = []
    for start in starts:
        if bursts and burst_gap is not None and start - bursts[-1][-1] < float(burst_gap):
            bursts[-1].append(start)
        else:
            bursts.append([start])
    gaps = [later[0] - earlier[0] for earlier, later in zip(bursts, bursts[1:])]
    result: Dict[str, Any] = {
        "frames": len(frames), "transmissions": len(groups), "bursts": len(bursts),
        "count": len(gaps),
        "above": None if above is None else sum(1 for gap in gaps if gap > float(above)),
        "below": None if below is None else sum(1 for gap in gaps if gap < float(below)),
        "largest_burst": max((len(burst) for burst in bursts), default=0),
        "first_s": starts[0] if starts else None,
        "last_s": starts[-1] if starts else None,
        "intervals": [round(gap, 6) for gap in gaps],
    }
    result.update(_stats(gaps))
    return result


def _distinct(values: Iterable[Any]) -> List[Any]:
    """The distinct values, in the order first seen; unhashable ones by their text."""
    seen, out = set(), []
    for value in values:
        key = json.dumps(value, sort_keys=True, default=str)
        if key not in seen:
            seen.add(key)
            out.append(value)
    return out


def census(frames: Sequence[Frame], fields: Sequence[str] = (),  # pylint: disable=too-many-locals
           expected: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    """What was heard: frames by type, with their lengths and the values of *fields*.

    :param fields: Dotted paths whose distinct values are listed per type,
        e.g. ``rf_capability``.
    :param expected: The only types that should be heard. Every other type,
        and every frame the decoder could not read, is counted as unexpected.
    :returns: ``frames``, ``transmissions``, ``rejected`` (receptions with a
        receiver error), ``undecoded``, ``type_names`` (sorted), ``types``
        (per type: ``count``, ``transmissions``, ``lengths``, and ``fields``:
        each field's distinct values), and with *expected*: ``unexpected``
        (frames) and ``unexpected_types``.
    """
    types: Dict[str, Dict[str, Any]] = {}
    rejected = sum(1 for frame in frames if frame.error)
    undecoded = [frame for frame in frames if not frame.error and not frame.decoded]
    intact = [frame for frame in frames if frame.ok]
    for frame in intact:
        name = str(frame.frame_type)
        entry = types.setdefault(name, {"count": 0, "transmissions": 0, "lengths": [],
                                        "fields": {path: [] for path in fields}})
        entry["count"] += 1
        if len(frame.data) not in entry["lengths"]:
            entry["lengths"].append(len(frame.data))
        for path in fields:
            value = field_value(frame.decoded, path)
            if value is not MISSING and value not in entry["fields"][path]:
                entry["fields"][path].append(value)
    for group in transmissions(intact):
        types[str(group[0].frame_type)]["transmissions"] += 1
    for entry in types.values():
        entry["lengths"].sort()
    result: Dict[str, Any] = {
        "frames": len(frames), "transmissions": sum(e["transmissions"] for e in types.values()),
        "rejected": rejected, "undecoded": len(undecoded),
        "decode_errors": _distinct(frame.decode_error for frame in undecoded),
        "type_names": sorted(types), "types": types,
    }
    if expected is not None:
        allowed = {str(name) for name in expected}
        others = sorted(name for name in types if name not in allowed)
        result["unexpected_types"] = others
        result["unexpected"] = sum(types[name]["count"] for name in others) + len(undecoded)
    return result


def _text(value: Any) -> str:
    """*value* as text that two equal values share, for comparing and hashing."""
    return json.dumps(value, sort_keys=True, default=str)


def _values_at(decoded: Optional[Mapping[str, Any]], paths: Sequence[str]) -> List[Any]:
    """The values at *paths*, None for each one missing."""
    values = []
    for path in paths:
        value = field_value(decoded, path)
        values.append(None if value is MISSING else value)
    return values


def _bytes_equal(first: bytes, second: bytes, ignore: Sequence[int]) -> bool:
    if len(first) != len(second):
        return False
    skip = {offset % len(first) for offset in ignore} if first else set()
    return all(a == b for index, (a, b) in enumerate(zip(first, second)) if index not in skip)


#: A plugin's answer to "where does this copy's content belong": the length
#: of the whole sequence, and the values this copy carries by position.
Positions = Optional[Tuple[int, Dict[int, Any]]]


def _ascends(value: Any, previous: Any, restart_at: Any) -> bool:
    """Whether *value* may follow *previous* in an ascending field."""
    if previous is MISSING:
        return True
    if value is MISSING:
        return False
    if restart_at is not None and _same(value, restart_at):
        return True
    try:
        return bool(value > previous)
    except TypeError:
        return False


def compare_copies(  # pylint: disable=too-many-locals,too-many-branches,too-many-statements,too-many-arguments
        frames: Sequence[Frame], ignore_offsets: Sequence[int] = (),
        same_fields: Sequence[str] = (),
        positions: Optional[Callable[[Dict[str, Any]], Positions]] = None,
        ascending: Optional[str] = None, *, sequence: Sequence[str] = (),
        restart_at: Any = None) -> Dict[str, Any]:
    """Compare the copies of each transmission, and what they carry together.

    :param ignore_offsets: Byte offsets to leave out when comparing copies -
        a count byte that differs in every copy by design.
    :param same_fields: Dotted paths that must be the same in every copy.
    :param positions: Where each copy's values belong in a longer sequence:
        called with a decode, it returns ``(length, {position: value})``, or
        None for a frame it does not place. A plugin provides it as its
        ``frame_positions`` hook.
    :param ascending: A dotted path that must increase from one transmission
        to the next of the same sequence, e.g. a packet number. A value that
        cannot be compared with the one before does not.
    :param sequence: Dotted paths that tell the sequences apart - one
        waveform's axis and buffer, say. Each combination of their values is
        a sequence of its own, with its own positions and its own ascending
        order. Without, all the frames are one sequence.
    :param restart_at: A value of *ascending* that starts the order afresh,
        such as packet number 0 of the next capture.
    :returns: ``transmissions``, ``copies``, ``copies_per_transmission``
        (min and max), ``identical`` and ``not_identical`` (transmissions
        whose copies are, or are not, the same bytes outside
        *ignore_offsets*), ``fields_differ`` (transmissions where a
        *same_fields* field differs between copies), ``not_ascending``; and
        with *positions*: ``distinct_blocks`` and ``repeated_blocks``
        (transmissions whose copies all carry different positions, or where
        two carry the same), ``overlapping`` (positions carried by more than
        one copy of one transmission), ``covered``, ``length``, ``missing``
        (positions of the whole sequence nobody carried), ``conflicts``
        (positions given two different values) and ``placed`` (copies the
        hook placed); ``covered``, ``length``, ``missing`` and ``conflicts``
        are summed over the sequences, and ``sequences`` counts them.
        ``detail`` lists each transmission.
    """
    groups = transmissions(frames)
    identical = fields_differ = not_ascending = 0
    distinct_blocks = repeated_blocks = overlapping = placed = 0
    wholes: Dict[str, Dict[int, Any]] = {}
    conflicts: Dict[str, set] = {}
    lengths: Dict[str, int] = {}
    previous: Dict[str, Any] = {}
    detail = []
    for group in groups:
        key = _text(_values_at(group[0].decoded, sequence))
        same_bytes = all(_bytes_equal(group[0].data, copy.data, ignore_offsets)
                         for copy in group[1:])
        identical += same_bytes
        differing = [path for path in same_fields
                     if len({json.dumps(field_value(copy.decoded, path), sort_keys=True,
                                        default=str) for copy in group}) > 1]
        fields_differ += bool(differing)
        row: Dict[str, Any] = {"copies": len(group), "identical": same_bytes,
                               "repeats": [copy.repeat for copy in group]}
        if differing:
            row["fields_differ"] = differing
        if sequence:
            row["sequence"] = _values_at(group[0].decoded, sequence)
        if ascending is not None:
            value = field_value(group[0].decoded, ascending)
            row[ascending] = None if value is MISSING else value
            if not _ascends(value, previous.get(key, MISSING), restart_at):
                not_ascending += 1
            previous[key] = value
        if positions is not None:
            whole = wholes.setdefault(key, {})
            blocks = []
            counted: Dict[int, int] = {}
            for copy in group:
                answer = positions(copy.decoded or {})
                if answer is None:
                    continue
                size, values = answer
                placed += 1
                lengths[key] = max(lengths.get(key, 0), int(size))
                blocks.append(frozenset(values))
                for position, value in values.items():
                    counted[position] = counted.get(position, 0) + 1
                    if position in whole and whole[position] != value:
                        conflicts.setdefault(key, set()).add(position)
                    whole.setdefault(position, value)
            if blocks:
                distinct = len(set(blocks)) == len(blocks)
                distinct_blocks += distinct
                repeated_blocks += not distinct
                shared = sum(1 for count in counted.values() if count > 1)
                overlapping += shared
                row.update({"distinct_blocks": distinct, "overlapping": shared})
        detail.append(row)
    sizes = [len(group) for group in groups]
    result: Dict[str, Any] = {
        "transmissions": len(groups), "copies": sum(sizes),
        "copies_per_transmission": {"minimum": min(sizes, default=None),
                                    "maximum": max(sizes, default=None)},
        "identical": identical, "not_identical": len(groups) - identical,
        "fields_differ": fields_differ, "not_ascending": not_ascending,
        "detail": detail,
    }
    if positions is not None:
        covered = {key: sum(1 for position in whole if 0 <= position < lengths.get(key, 0))
                   for key, whole in wholes.items()}
        result.update({
            "placed": placed, "distinct_blocks": distinct_blocks,
            "repeated_blocks": repeated_blocks, "overlapping": overlapping,
            "sequences": sum(1 for key in wholes if lengths.get(key)),
            "covered": sum(covered.values()), "length": sum(lengths.values()),
            "missing": sum(max(0, lengths.get(key, 0) - covered[key]) for key in wholes),
            "conflicts": sum(len(found) for found in conflicts.values()),
        })
    return result


def distinct_per_group(  # pylint: disable=too-many-locals,too-many-arguments
        frames: Sequence[Frame], value: str, group: str, item: Sequence[str] = (), *,
        wrap_after: Optional[int] = None, wrap_to: Optional[int] = None) -> Dict[str, Any]:
    """Whether *value* differs between the items of each *group*.

    A group is a run of consecutive transmissions with the same *group*
    value - one capture, say. An item is one transmission, or with *item*
    every transmission of the group with the same values at those dotted
    paths - one waveform of a capture, whose packets all carry its value.
    Each item's value is taken from its first transmission, by its first
    copy.

    :param wrap_after: With *wrap_to*: the group value after which the next
        is *wrap_to* rather than one more, for a counter that wraps.
    :returns: ``groups``, ``items`` (in all groups), ``all_distinct`` and
        ``not_distinct`` (groups whose items' values are, or are not,
        pairwise different), ``inconsistent`` (items whose transmissions
        carry different values), ``repeated_sets`` (groups with the same set
        of values as the group before), ``not_incrementing`` (groups whose
        value is not one more than the group before's, allowing the wrap),
        ``group_values`` and ``detail``.
    """
    runs: List[Tuple[Any, Dict[str, Any]]] = []
    inconsistent = 0
    for transmission in transmissions(frames):
        decoded = transmission[0].decoded
        key = field_value(decoded, group)
        found = field_value(decoded, value)
        if key is MISSING or found is MISSING:
            continue
        if not runs or not _same(runs[-1][0], key):
            runs.append((key, {}))
        items = runs[-1][1]
        ident = _text(_values_at(decoded, item)) if item else str(len(items))
        if ident in items:
            if _text(items[ident]["value"]) != _text(found):
                if not items[ident]["inconsistent"]:
                    inconsistent += 1
                items[ident]["inconsistent"] = True
            continue
        items[ident] = {"value": found, "inconsistent": False}
    all_distinct = repeated_sets = not_incrementing = 0
    detail = []
    previous_set = None
    for index, (key, items) in enumerate(runs):
        values = [entry["value"] for entry in items.values()]
        texts = [json.dumps(entry, sort_keys=True, default=str) for entry in values]
        distinct = len(set(texts)) == len(texts)
        all_distinct += distinct
        this_set = frozenset(texts)
        repeated_sets += previous_set is not None and this_set == previous_set
        previous_set = this_set
        if index:
            before = runs[index - 1][0]
            try:
                steps = int(key) == int(before) + 1 or (
                    wrap_after is not None and wrap_to is not None
                    and int(before) == int(wrap_after) and int(key) == int(wrap_to))
            except (TypeError, ValueError):
                steps = False
            not_incrementing += not steps
        detail.append({"group": key, "values": values, "distinct": distinct})
    return {
        "groups": len(runs), "items": sum(len(items) for _key, items in runs),
        "all_distinct": all_distinct, "not_distinct": len(runs) - all_distinct,
        "inconsistent": inconsistent, "repeated_sets": repeated_sets,
        "not_incrementing": not_incrementing,
        "group_values": [key for key, _items in runs], "detail": detail,
    }
