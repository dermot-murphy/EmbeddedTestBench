"""Measures over a window of received frames, or a packet log (#243).

Split from :mod:`traffic` so that its receive path and these measures can each
be read on their own. :class:`FrameMeasuresMixin` is not used alone:
:class:`~.s2lp.S2lpDevkit` provides :meth:`~.traffic.TrafficMixin.stream`,
which it receives with. The measures themselves are
:mod:`benchtools.analysis.frames`, which knows no device; a decoder and any
``frame_positions`` hook come from the plugins loaded (#238).

Traces to: S2LP-FR-089 .. S2LP-FR-092, S2LP-DD-MEASURES.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Sequence

from ...analysis import frames as fr
from ...core import plugins
from ...core.errors import ConfigurationError
from ...core.paths import input_paths
from .traffic import DecoderChoice, _decoder

__all__ = ["FrameMeasuresMixin"]


class FrameMeasuresMixin:
    """``dut_intervals``, ``dut_census``, ``dut_transmissions``, ``dut_distinct``."""

    #: Provided by :class:`~.traffic.TrafficMixin`.
    stream: Callable[..., Any]

    def _frames_for(self, decoder: DecoderChoice, window: float,
                    log: Optional[str],
                    enough: Optional[Callable[[List["fr.Frame"]], bool]] = None
                    ) -> List["fr.Frame"]:
        """The frames heard in *window* seconds, or those packet log *log* holds.

        Live, the board receives for *window* seconds, or until *enough*
        says so. From a log, the payloads are decoded again by *decoder* when
        a decoder is loaded, else the log's own decode is used; the board is
        not touched.
        """
        if log is not None:
            try:
                function = _decoder(decoder)
            except ConfigurationError:
                if decoder is not None:
                    raise
                function = None
            return fr.frames_from_log(log, function)
        heard: List[fr.Frame] = []
        for packet in self.stream(decoder=_decoder(decoder), timeout=float(window)):
            heard.append(fr.Frame.from_packet(packet))
            if enough is not None and enough(heard):
                break
        return heard

    @input_paths("log")
    def dut_intervals(  # pylint: disable=too-many-arguments
            self, frame_type: Optional[str] = None, source: Optional[str] = None, *,
            where: Optional[Dict[str, Any]] = None, window: float = 60.0,
            burst_gap: Optional[float] = None, above: Optional[float] = None,
            below: Optional[float] = None, clock: str = "host",
            copy_gap: Optional[float] = fr.COPY_GAP_S, log: Optional[str] = None,
            decoder: DecoderChoice = None) -> Dict[str, Any]:
        """The time between one kind of frame's transmissions, over a window.

        Frames of *frame_type* from *source* with *where* are taken from a
        receive of *window* seconds, or from packet log *log*. Each
        transmission is timed by its first copy heard, on the host's clock.
        With *burst_gap*, transmissions closer together than that are one
        burst - a command and its retries - and the intervals are between
        the bursts.

        :param above: Count the intervals longer than this, in seconds.
        :param below: Count the intervals shorter than this.
        :param clock: ``"host"``, the host's arrival time, shared with the BLE
            dongle's events and in every packet log; or ``"board"``, the S2-LP
            board's timer, without the USB link's jitter. See
            :func:`benchtools.analysis.frames.intervals`.
        :param copy_gap: The longest time between two copies of one
            transmission, in seconds; a copy later than that after the last
            starts a new one.
        :returns: See :func:`benchtools.analysis.frames.intervals`: ``count``,
            ``minimum``, ``maximum``, ``mean``, ``above``, ``below``,
            ``bursts``, ``transmissions``, ``largest_burst``, ``runs``,
            ``intervals``. ``runs`` above 1 means *log* holds more than one
            run, between which nothing is measured: a specification that
            must cover a whole window should require it to be 1.

        Traces to: S2LP-FR-089.
        """
        copy_gap = fr.check_copy_gap(copy_gap)
        heard = self._frames_for(decoder, window, log)
        chosen = fr.select(heard, frame_type, source, fr.check_where(where))
        return fr.intervals(chosen, burst_gap=burst_gap, above=above, below=below, clock=clock,
                            copy_gap=copy_gap)

    @input_paths("log")
    def dut_census(  # pylint: disable=too-many-arguments
            self, window: float = 60.0, *, source: Optional[str] = None,
            fields: Sequence[str] = (), expected: Optional[Sequence[str]] = None,
            copy_gap: Optional[float] = fr.COPY_GAP_S,
            log: Optional[str] = None, decoder: DecoderChoice = None) -> Dict[str, Any]:
        """What was on the air: every frame by type, over a window or a packet log.

        :param source: Only frames from this sensor; a frame that cannot be
            decoded has no source and is counted whatever this is.
        :param fields: Dotted paths whose distinct values are listed per
            type, e.g. ``rf_capability``.
        :param expected: The types that should be heard; any other, and any
            frame the decoder cannot read, counts as ``unexpected``.
        :param copy_gap: As for :meth:`dut_intervals`, for counting
            transmissions.
        :returns: See :func:`benchtools.analysis.frames.census`.

        Traces to: S2LP-FR-090.
        """
        copy_gap = fr.check_copy_gap(copy_gap)
        heard = self._frames_for(decoder, window, log)
        if source is not None:
            heard = [frame for frame in heard if not frame.ok or frame.source == str(source)]
        return fr.census(heard, fields=fields, expected=expected, copy_gap=copy_gap)

    @input_paths("log")
    def dut_transmissions(  # pylint: disable=too-many-arguments,too-many-locals
            self, frame_type: Optional[str] = None, source: Optional[str] = None, *,
            where: Optional[Dict[str, Any]] = None, count: Optional[int] = None,
            window: float = 60.0, ignore_offsets: Sequence[int] = (),
            same_fields: Sequence[str] = (), positions: bool = False,
            ascending: Optional[str] = None, sequence: Sequence[str] = (),
            restart_at: Any = None, copy_gap: Optional[float] = fr.COPY_GAP_S,
            log: Optional[str] = None,
            decoder: DecoderChoice = None) -> Dict[str, Any]:
        """Every copy of each transmission, and how the copies compare.

        Where :meth:`dut_samples` keeps one copy of each transmission, this
        keeps them all, grouped by the repeat number the decoder gives.

        :param count: Stop after this many transmissions. Live, the receive
            runs until the first copy of the one after them is heard, so the
            last is complete, or until *window* ends.
        :param ignore_offsets: Byte offsets left out when comparing copies,
            e.g. ``[9]`` for a repeat-count byte.
        :param same_fields: Dotted paths that must be the same in every copy.
        :param positions: Place each copy's values in the whole sequence they
            belong to, by the plugin's ``frame_positions`` hook, and report
            the blocks, their overlap and what is missing.
        :param ascending: A dotted path that must increase from one
            transmission to the next of the same sequence.
        :param sequence: Dotted paths that tell sequences apart, e.g.
            ``[axis, param.twfb]`` for the waveforms of one capture: each has
            its own positions and order. Without, the frames chosen are one
            sequence, so choose one with *where*.
        :param restart_at: A value of *ascending* that starts it afresh.
        :param copy_gap: As for :meth:`dut_intervals`.
        :returns: See :func:`benchtools.analysis.frames.compare_copies`.
        :raises ConfigurationError: if *positions* is asked for and no loaded
            plugin has a ``frame_positions`` hook.

        Traces to: S2LP-FR-091.
        """
        copy_gap = fr.check_copy_gap(copy_gap)
        where = fr.check_where(where)
        hook = None
        if positions:
            hook = plugins.hook("frame_positions")
            if hook is None:
                raise ConfigurationError(
                    "positions needs a plugin with a frame_positions hook, which says "
                    "where each copy's values belong; none of the plugins loaded has one")

        def enough(heard: List[fr.Frame]) -> bool:
            return count is not None and len(fr.transmissions(
                fr.select(heard, frame_type, source, where), copy_gap)) > int(count)

        chosen = fr.select(self._frames_for(decoder, window, log,
                                            None if log is not None else enough),
                           frame_type, source, where)
        if count is not None:
            groups = fr.transmissions(chosen, copy_gap)[:int(count)]
            kept = {id(frame) for group in groups for frame in group}
            chosen = [frame for frame in chosen if id(frame) in kept]
        result = fr.compare_copies(chosen, ignore_offsets=ignore_offsets,
                                   same_fields=same_fields, positions=hook,
                                   ascending=ascending, sequence=sequence,
                                   restart_at=restart_at, copy_gap=copy_gap)
        result["requested"] = count
        return result

    @input_paths("log")
    def dut_distinct(  # pylint: disable=too-many-arguments
            self, value: str, group: str, frame_type: Optional[str] = None,
            source: Optional[str] = None, *, where: Optional[Dict[str, Any]] = None,
            item: Sequence[str] = (), window: float = 60.0, wrap_after: Optional[int] = None,
            wrap_to: Optional[int] = None, copy_gap: Optional[float] = fr.COPY_GAP_S,
            log: Optional[str] = None,
            decoder: DecoderChoice = None) -> Dict[str, Any]:
        """Whether *value* differs between the transmissions of each *group*.

        For a field that must be unique within one capture and change between
        captures: the sync attribute of each TWF frame of one group ID, say.
        A group is a run of consecutive transmissions with the same *group*
        value.

        :param item: Dotted paths that make one item of a group: each
            combination of their values is counted once, e.g. ``[axis,
            param.twfb]`` for one waveform of a capture. Without, each
            transmission is an item.
        :param wrap_after: With *wrap_to*, a group counter's wrap: after
            *wrap_after* the next group is *wrap_to*.
        :param copy_gap: As for :meth:`dut_intervals`.
        :returns: See :func:`benchtools.analysis.frames.distinct_per_group`.

        Traces to: S2LP-FR-092.
        """
        copy_gap = fr.check_copy_gap(copy_gap)
        heard = self._frames_for(decoder, window, log)
        chosen = fr.select(heard, frame_type, source, fr.check_where(where))
        return fr.distinct_per_group(chosen, value, group, item=item,
                                     wrap_after=wrap_after, wrap_to=wrap_to, copy_gap=copy_gap)
