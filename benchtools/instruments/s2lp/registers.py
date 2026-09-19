"""The S2-LP register map.

123 registers, by name and address, with their reset values and the bit fields
inside them. This is what turns "read all registers" into something a reviewer
can read: a dump of 123 hex bytes says nothing, and a dump that names
``PCKTCTRL3.PCKT_FRMT = 0 (basic)`` says what the radio was configured to do.

The table holds **facts about the silicon** - addresses, reset values, field
names and their bit positions - taken from the S2-LP register table published in
the device datasheet (DS11896) and cross-checked against ST's own published
register header (see ``docs/s2lp/S2LP_Devkit_Notes.md`` §6). No vendor source is
vendored here: ST's software is under a limited licence (SLA0072), and this
package interoperates with their firmware rather than redistributing it.

Two things are deliberately absent. **Field descriptions** are not reproduced -
they are the datasheet's prose, and the datasheet is where they belong.
**Reserved bits** are not fields: they are omitted, so anything this map names
is something the datasheet names too.

Traces to: S2LP-FR-010 .. S2LP-FR-014, S2LP-DD-REGS.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterator, List, Optional, Sequence, Tuple, Union

__all__ = [
    "Field",
    "Register",
    "REGISTERS",
    "BY_NAME",
    "BY_ADDRESS",
    "lookup",
    "contiguous_runs",
    "decode",
    "describe",
    "RW",
    "RO",
]

#: Access, as the datasheet states it.
RW = "rw"
RO = "r"


@dataclass(frozen=True)
class Field:
    """A named run of bits inside one register."""

    high: int
    low: int
    name: str

    @property
    def width(self) -> int:
        return self.high - self.low + 1

    @property
    def mask(self) -> int:
        """The field's bits, in place."""
        return ((1 << self.width) - 1) << self.low

    @property
    def bits(self) -> str:
        """``"7:3"``, or ``"4"`` for a single bit, as the datasheet writes it."""
        return "%d" % self.high if self.high == self.low else "%d:%d" % (self.high, self.low)

    def extract(self, value: int) -> int:
        """This field's value out of a whole register value."""
        return (int(value) & self.mask) >> self.low

    def insert(self, value: int, field_value: int) -> int:
        """*value* with this field replaced by *field_value*.

        :raises ValueError: if *field_value* does not fit the field. Truncating
            it silently would write a different configuration from the one that
            was asked for, and the register would read back "correct" against
            the truncated value.
        """
        field_value = int(field_value)
        if field_value < 0 or field_value >= (1 << self.width):
            raise ValueError(
                "%s is %d bit(s) wide, so it cannot hold %d (0 to %d)"
                % (self.name, self.width, field_value, (1 << self.width) - 1)
            )
        return (int(value) & ~self.mask) | (field_value << self.low)


@dataclass(frozen=True)
class Register:
    """One register of the S2-LP."""

    address: int
    name: str
    reset: int
    access: str
    fields: Tuple[Field, ...] = ()

    @property
    def writable(self) -> bool:
        return self.access == RW

    def field(self, name: str) -> Field:
        """The named field.

        :raises KeyError: naming the fields this register does have.
        """
        wanted = name.strip().upper()
        for item in self.fields:
            if item.name.upper() == wanted:
                return item
        raise KeyError(
            "%s has no field %r; it has %s"
            % (self.name, name, ", ".join(item.name for item in self.fields) or "none")
        )

    def decode(self, value: int) -> Dict[str, int]:
        """Field name to value, for one register reading."""
        return {item.name: item.extract(value) for item in self.fields}

    def describe(self, value: int) -> str:
        """One line: address, name, value, and the fields that are not zero.

        Non-zero fields only, because a dump in which every field of every
        register is listed is a dump nobody reads. ``reset`` is marked so that
        "this register has never been written" is visible at a glance.
        """
        parts = ["0x%02X %-22s = 0x%02X" % (self.address, self.name, value)]
        if value == self.reset:
            parts.append("(reset)")
        interesting = ["%s=%d" % (item.name, item.extract(value))
                       for item in self.fields if item.extract(value)]
        if interesting:
            parts.append(" ".join(interesting))
        return "  ".join(parts)

    def __str__(self) -> str:
        return "%s (0x%02X)" % (self.name, self.address)


# ---------------------------------------------------------------------------
# The table. (address, name, reset, access, ((high, low, field name), ...))
# ---------------------------------------------------------------------------
_TABLE: Tuple[tuple, ...] = (
    (0x00, "GPIO0_CONF", 0x0A, RW, ((7, 3, "GPIO_SELECT"), (1, 0, "GPIO_MODE"))),
    (0x01, "GPIO1_CONF", 0xA2, RW, ((7, 3, "GPIO_SELECT"), (1, 0, "GPIO_MODE"))),
    (0x02, "GPIO2_CONF", 0xA2, RW, ((7, 3, "GPIO_SELECT"), (1, 0, "GPIO_MODE"))),
    (0x03, "GPIO3_CONF", 0xA2, RW, ((7, 3, "GPIO_SELECT"), (1, 0, "GPIO_MODE"))),
    (0x04, "MCU_CK_CONF", 0x00, RW,
     ((7, 7, "EN_MCU_CLK"), (6, 5, "CLOCK_TAIL"), (4, 1, "XO_RATIO"), (0, 0, "RCO_RATIO"))),
    (0x05, "SYNT3", 0x42, RW, ((7, 5, "PLL_CP_ISEL"), (4, 4, "BS"), (3, 0, "SYNT_27_24"))),
    (0x06, "SYNT2", 0x16, RW, ((7, 0, "SYNT"),)),
    (0x07, "SYNT1", 0x27, RW, ((7, 0, "SYNT"),)),
    (0x08, "SYNT0", 0x62, RW, ((7, 0, "SYNT"),)),
    (0x09, "IF_OFFSET_ANA", 0x2A, RW, ((7, 0, "IF_OFFSET_ANA"),)),
    (0x0A, "IF_OFFSET_DIG", 0xB8, RW, ((7, 0, "IF_OFFSET_DIG"),)),
    (0x0C, "CH_SPACE", 0x3F, RW, ((7, 0, "CH_SPACE"),)),
    (0x0D, "CHNUM", 0x00, RW, ((7, 0, "CH_NUM"),)),
    (0x0E, "MOD4", 0x83, RW, ((7, 0, "DATARATE_M"),)),
    (0x0F, "MOD3", 0x2B, RW, ((7, 0, "DATARATE_M"),)),
    (0x10, "MOD2", 0x77, RW, ((7, 4, "MOD_TYPE"), (3, 0, "DATARATE_E"))),
    (0x11, "MOD1", 0x03, RW,
     ((7, 7, "PA_INTERP_EN"), (6, 6, "MOD_INTERP_EN"), (5, 4, "G4FSK_CONST_MAP"), (3, 0,
     "FDEV_E"))),
    (0x12, "MOD0", 0x93, RW, ((7, 0, "FDEV_M"),)),
    (0x13, "CHFLT", 0x23, RW, ((7, 4, "CHFLT_M"), (3, 0, "CHFLT_E"))),
    (0x14, "AFC2", 0xC8, RW,
     ((7, 7, "AFC_FREEZE_ON_SYNC"), (6, 6, "AFC_ENABLED"), (5, 5, "AFC_MODE"))),
    (0x15, "AFC1", 0x18, RW, ((7, 0, "AFC_FAST_PERIOD"),)),
    (0x16, "AFC0", 0x25, RW, ((7, 4, "AFC_FAST_GAIN"), (3, 0, "AFC_SLOW_GAIN"))),
    (0x17, "RSSI_FLT", 0xE3, RW, ((7, 4, "RSSI_FLT"), (3, 2, "CS_MODE"))),
    (0x18, "RSSI_TH", 0x28, RW, ((7, 0, "RSSI_TH"),)),
    (0x1F, "ANT_SELECT_CONF", 0x45, RW,
     ((6, 5, "EQU_CTRL"), (4, 4, "CS_BLANKING"), (3, 3, "AS_ENABLE"), (2, 0, "AS_MEAS_TIME"))),
    (0x20, "CLOCKREC1", 0x00, RW,
     ((7, 5, "CLK_REC_P_GAIN_SLOW"), (4, 4, "CLK_REC_ALGO_SEL"), (3, 0, "CLK_REC_I_GAIN_SLOW"))),
    (0x21, "CLOCKREC0", 0x58, RW,
     ((7, 5, "CLK_REC_P_GAIN_FAST"), (4, 4, "PSTFLT_LEN"), (3, 0, "CLK_REC_I_GAIN_FAST"))),
    (0x2B, "PCKTCTRL6", 0x80, RW, ((7, 2, "SYNC_LEN"), (1, 0, "PREAMBLE_LEN_9_8"))),
    (0x2C, "PCKTCTRL5", 0x10, RW, ((7, 0, "PREAMBLE_LEN"),)),
    (0x2D, "PCKTCTRL4", 0x00, RW, ((7, 7, "LEN_WID"), (3, 3, "ADDRESS_LEN"))),
    (0x2E, "PCKTCTRL3", 0x20, RW,
     ((7, 6, "PCKT_FRMT"), (5, 4, "RX_MODE"), (3, 3, "FSK4_SYM_SWAP"), (2, 2, "BYTE_SWAP"), (1,
     0, "PREAMBLE_SEL"))),
    (0x2F, "PCKTCTRL2", 0x00, RW,
     ((5, 5, "FCS_TYPE_4G"), (4, 4, "FEC_TYPE_4G"), (3, 3, "INT_EN_4G"), (2, 2,
     "MBUS_3OF6_EN"), (1, 1, "MANCHESTER_EN"), (0, 0, "FIX_VAR_LEN"))),
    (0x30, "PCKTCTRL1", 0x2C, RW,
     ((7, 5, "CRC_MODE"), (4, 4, "WHIT_EN"), (3, 2, "TXSOURCE"), (1, 1, "SECOND_SYNC_SEL"), (0,
     0, "FEC_EN"))),
    (0x31, "PCKTLEN1", 0x00, RW, ((7, 0, "PCKTLEN1"),)),
    (0x32, "PCKTLEN0", 0x14, RW, ((7, 0, "PCKTLEN0"),)),
    (0x33, "SYNC3", 0x88, RW, ((7, 0, "SYNC3"),)),
    (0x34, "SYNC2", 0x88, RW, ((7, 0, "SYNC2"),)),
    (0x35, "SYNC1", 0x88, RW, ((7, 0, "SYNC1"),)),
    (0x36, "SYNC0", 0x88, RW, ((7, 0, "SYNC0"),)),
    (0x37, "QI", 0x01, RW, ((7, 5, "SQI_TH"), (4, 1, "PQI_TH"), (0, 0, "SQI_EN"))),
    (0x38, "PCKT_PSTMBL", 0x00, RW, ((7, 0, "PCKT_PSTMBL"),)),
    (0x39, "PROTOCOL2", 0x40, RW,
     ((7, 7, "CS_TIMEOUT_MASK"), (6, 6, "SQI_TIMEOUT_MASK"), (5, 5, "PQI_TIMEOUT_MASK"), (4, 3,
     "TX_SEQ_NUM_RELOAD"), (2, 2, "FIFO_GPIO_OUT_MUX_SEL"), (1, 0, "LDC_TIMER_MULT"))),
    (0x3A, "PROTOCOL1", 0x00, RW,
     ((7, 7, "LDC_MODE"), (6, 6, "LDC_RELOAD_ON_SYNC"), (5, 5, "PIGGYBACKING"), (4, 4,
     "FAST_CS_TERM_EN"), (3, 3, "SEED_RELOAD"), (2, 2, "CSMA_ON"), (1, 1, "CSMA_PERS_ON"), (0,
     0, "AUTO_PCKT_FLT"))),
    (0x3B, "PROTOCOL0", 0x08, RW,
     ((7, 4, "NMAX_RETX"), (3, 3, "NACK_TX"), (2, 2, "AUTO_ACK"), (1, 1, "PERS_RX"))),
    (0x3C, "FIFO_CONFIG3", 0x30, RW, ((6, 0, "RX_AFTHR"),)),
    (0x3D, "FIFO_CONFIG2", 0x30, RW, ((6, 0, "RX_AETHR"),)),
    (0x3E, "FIFO_CONFIG1", 0x30, RW, ((6, 0, "TX_AFTHR"),)),
    (0x3F, "FIFO_CONFIG0", 0x30, RW, ((6, 0, "TX_AETHR"),)),
    (0x40, "PCKT_FLT_OPTIONS", 0x40, RW,
     ((6, 6, "RX_TIMEOUT_AND_OR_SEL"), (4, 4, "SOURCE_ADDR_FLT"), (3, 3,
     "DEST_VS_BROADCAST_ADDR"), (2, 2, "DEST_VS_MULTICAST_ADDR"), (1, 1,
     "DEST_VS_SOURCE_ADDR"), (0, 0, "CRC_FLT"))),
    (0x41, "PCKT_FLT_GOALS4", 0x00, RW, ()),
    (0x42, "PCKT_FLT_GOALS3", 0x00, RW, ()),
    (0x43, "PCKT_FLT_GOALS2", 0x00, RW, ()),
    (0x44, "PCKT_FLT_GOALS1", 0x00, RW, ()),
    (0x45, "PCKT_FLT_GOALS0", 0x00, RW, ((7, 0, "TX_SOURCE_ADDR"),)),
    (0x46, "TIMERS5", 0x01, RW, ((7, 0, "RX_TIMER_CNTR"),)),
    (0x47, "TIMERS4", 0x00, RW, ((7, 0, "RX_TIMER_PRESC"),)),
    (0x48, "TIMERS3", 0x01, RW, ((7, 0, "LDC_TIMER_PRESC"),)),
    (0x49, "TIMERS2", 0x00, RW, ((7, 0, "LDC_TIMER_CNTR"),)),
    (0x4A, "TIMERS1", 0x01, RW, ((7, 0, "LDC_RELOAD_PRSC"),)),
    (0x4B, "TIMERS0", 0x00, RW, ((7, 0, "LDC_RELOAD_CNTR"),)),
    (0x4C, "CSMA_CONF3", 0x4C, RW, ((7, 0, "BU_CNTR_SEED"),)),
    (0x4D, "CSMA_CONF2", 0x00, RW, ((7, 0, "BU_CNTR_SEED"),)),
    (0x4E, "CSMA_CONF1", 0x04, RW, ((7, 2, "BU_PRSC"), (1, 0, "CCA_PERIOD"))),
    (0x4F, "CSMA_CONF0", 0x00, RW, ((7, 4, "CCA_LEN"), (2, 0, "NBACKOFF_MAX"))),
    (0x50, "IRQ_MASK3", 0x00, RW, ((7, 0, "INT_MASK"),)),
    (0x51, "IRQ_MASK2", 0x00, RW, ((7, 0, "INT_MASK"),)),
    (0x52, "IRQ_MASK1", 0x00, RW, ((7, 0, "INT_MASK"),)),
    (0x53, "IRQ_MASK0", 0x00, RW, ((7, 0, "INT_MASK"),)),
    (0x54, "FAST_RX_TIMER", 0x00, RW, ((7, 0, "RSSI_SETTLING_LIMIT"),)),
    (0x5A, "PA_POWER8", 0x01, RW, ((6, 0, "PA_LEVEL8"),)),
    (0x5B, "PA_POWER7", 0x0C, RW, ((6, 0, "PA_LEVEL_7"),)),
    (0x5C, "PA_POWER6", 0x18, RW, ((6, 0, "PA_LEVEL_6"),)),
    (0x5D, "PA_POWER5", 0x24, RW, ((6, 0, "PA_LEVEL_5"),)),
    (0x5E, "PA_POWER4", 0x30, RW, ((6, 0, "PA_LEVEL_4"),)),
    (0x5F, "PA_POWER3", 0x48, RW, ((6, 0, "PA_LEVEL_3"),)),
    (0x60, "PA_POWER2", 0x60, RW, ((6, 0, "PA_LEVEL_2"),)),
    (0x61, "PA_POWER1", 0x00, RW, ((6, 0, "PA_LEVEL_1"),)),
    (0x62, "PA_POWER0", 0x47, RW,
     ((7, 7, "DIG_SMOOTH_EN"), (6, 6, "PA_MAXDBM"), (5, 5, "PA_RAMP_EN"), (4, 3,
     "PA_RAMP_STEP_LEN"), (2, 0, "PA_LEVEL_MAX_IDX"))),
    (0x63, "PA_CONFIG1", 0x03, RW, ((4, 4, "LIN_NLOG"), (3, 2, "FIR_CFG"), (1, 1, "FIR_EN"))),
    (0x64, "PA_CONFIG0", 0x8A, RW, ()),
    (0x65, "SYNTH_CONFIG2", 0xD0, RW, ((2, 2, "PLL_PFD_SPLIT_EN"),)),
    (0x68, "VCO_CONFIG", 0x02, RW,
     ((5, 5, "VCO_CALAMP_EXT_SEL"), (4, 4, "VCO_CALFREQ_EXT_SEL"))),
    (0x69, "VCO_CALIBR_IN2", 0x88, RW, ((7, 4, "VCO_CALAMP_TX"), (3, 0, "VCO_CALAMP_RX"))),
    (0x6A, "VCO_CALIBR_IN1", 0x40, RW, ((6, 0, "VCO_CALFREQ_TX"),)),
    (0x6B, "VCO_CALIBR_IN0", 0x40, RW, ((6, 0, "VCO_CALFREQ_RX"),)),
    (0x6C, "XO_RCO_CONF1", 0x6C, RW, ((4, 4, "PD_CLKDIV"),)),
    (0x6D, "XO_RCO_CONF0", 0x30, RW,
     ((7, 7, "EXT_REF"), (5, 4, "GM_CONF"), (3, 3, "REFDIV"), (1, 1, "EXT_RCO_OSC"), (0, 0,
     "RCO_CALIBRATION"))),
    (0x6E, "RCO_CALIBR_CONF3", 0x70, RW, ((7, 4, "RWT_IN"), (3, 0, "RFB_IN_4_1"))),
    (0x6F, "RCO_CALIBR_CONF2", 0x4D, RW, ()),
    (0x75, "PM_CONF4", 0x17, RW,
     ((7, 7, "TEMP_SENSOR_EN"), (6, 6, "TEMP_SENS_BUFF_EN"), (5, 5, "EXT_SMPS"))),
    (0x76, "PM_CONF3", 0x20, RW, ((7, 7, "KRM_EN"), (6, 0, "KRM_14_8"))),
    (0x77, "PM_CONF2", 0x00, RW, ((7, 0, "KRM"),)),
    (0x78, "PM_CONF1", 0x39, RW, ((6, 6, "BATTERY_LVL_EN"), (5, 4, "SET_BLD_TH"))),
    (0x79, "PM_CONF0", 0x42, RW, ((6, 4, "SET_SMPS_LVL"), (0, 0, "SLEEP_MODE_SEL"))),
    (0x8D, "MC_STATE1", 0x52, RO,
     ((4, 4, "RCO_CAL_OK"), (3, 3, "ANT_SEL"), (2, 2, "TX_FIFO_FULL"), (1, 1, "RX_FIFO_EMPTY"),
     (0, 0, "ERROR_LOCK"))),
    (0x8E, "MC_STATE0", 0x07, RO, ((7, 1, "STATE"), (0, 0, "XO_ON"))),
    (0x8F, "TX_FIFO_STATUS", 0x00, RO, ((6, 0, "NELEM_TXFIFO"),)),
    (0x90, "RX_FIFO_STATUS", 0x00, RO, ((6, 0, "NELEM_RXFIFO"),)),
    (0x94, "RCO_CALIBR_OUT4", 0x70, RO, ((7, 4, "RWT_OUT"), (3, 0, "RFB_OUT_4_1"))),
    (0x95, "RCO_CALIBR_OUT3", 0x00, RO, ()),
    (0x99, "VCO_CALIBR_OUT1", 0x00, RO, ((3, 0, "VCO_CAL_AMP_OUT"),)),
    (0x9A, "VCO_CALIBR_OUT0", 0x00, RO, ((6, 0, "VCO_CAL_FREQ_OUT"),)),
    (0x9C, "TX_PCKT_INFO", 0x00, RO, ((5, 4, "TX_SEQ_NUM"), (3, 0, "N_RETX"))),
    (0x9D, "RX_PCKT_INFO", 0x00, RO, ((2, 2, "NACK_RX"), (1, 0, "RX_SEQ_NUM"))),
    (0x9E, "AFC_CORR", 0x00, RO, ((7, 0, "AFC_CORR"),)),
    (0x9F, "LINK_QUALIF2", 0x00, RO, ((7, 0, "PQI"),)),
    (0xA0, "LINK_QUALIF1", 0x00, RO, ((7, 7, "CS"), (6, 0, "SQI"))),
    (0xA2, "RSSI_LEVEL", 0x00, RO, ((7, 0, "RSSI_LEVEL"),)),
    (0xA4, "RX_PCKT_LEN1", 0x00, RO, ((7, 0, "RX_PCKT_LEN"),)),
    (0xA5, "RX_PCKT_LEN0", 0x00, RO, ((7, 0, "RX_PCKT_LEN"),)),
    (0xA6, "CRC_FIELD3", 0x00, RO, ((7, 0, "CRC_FIELD3"),)),
    (0xA7, "CRC_FIELD2", 0x00, RO, ((7, 0, "CRC_FIELD2"),)),
    (0xA8, "CRC_FIELD1", 0x00, RO, ((7, 0, "CRC_FIELD1"),)),
    (0xA9, "CRC_FIELD0", 0x00, RO, ((7, 0, "CRC_FIELD0"),)),
    (0xAA, "RX_ADDRE_FIELD1", 0x00, RO, ((7, 0, "RX_ADDRE_FIELD1"),)),
    (0xAB, "RX_ADDRE_FIELD0", 0x00, RO, ((7, 0, "RX_ADDRE_FIELD0"),)),
    (0xEF, "RSSI_LEVEL_RUN", 0x00, RO, ((7, 0, "RSSI_LEVEL_RUN"),)),
    (0xF0, "DEVICE_INFO1", 0x00, RO, ((7, 0, "PARTNUM"),)),
    (0xF1, "DEVICE_INFO0", 0x41, RO, ((7, 0, "RSSI_LEVEL"),)),
    (0xFA, "IRQ_STATUS3", 0x00, RO, ((7, 0, "INT_LEVEL"),)),
    (0xFB, "IRQ_STATUS2", 0x09, RO, ((7, 0, "INT_LEVEL"),)),
    (0xFC, "IRQ_STATUS1", 0x05, RO, ((7, 0, "INT_LEVEL"),)),
    (0xFD, "IRQ_STATUS0", 0x00, RO, ((7, 0, "INT_LEVEL"),)),
)

REGISTERS: Tuple[Register, ...] = tuple(
    Register(
        address=address,
        name=name,
        reset=reset,
        access=access,
        fields=tuple(Field(high, low, field_name) for high, low, field_name in fields),
    )
    for address, name, reset, access, fields in _TABLE
)

#: By upper-case name, and by address. Both are one-to-one: a duplicate in
#: either direction is a defect in the table, and a test asserts it.
BY_NAME: Dict[str, Register] = {register.name.upper(): register for register in REGISTERS}
BY_ADDRESS: Dict[int, Register] = {register.address: register for register in REGISTERS}


def lookup(what: Union[int, str]) -> Register:
    """Find a register by name or by address.

    :raises KeyError: with something useful to do next - the nearest named
        registers for an unknown address, and nothing invented for an unknown
        name.
    """
    if isinstance(what, str):
        text = what.strip()
        if text.upper() in BY_NAME:
            return BY_NAME[text.upper()]
        try:
            what = int(text, 0)
        except ValueError:
            raise KeyError("no S2-LP register called %r" % what) from None
    address = int(what)
    if address in BY_ADDRESS:
        return BY_ADDRESS[address]
    below = max((r for r in REGISTERS if r.address < address), key=lambda r: r.address, default=None)
    above = min((r for r in REGISTERS if r.address > address), key=lambda r: r.address, default=None)
    neighbours = ", ".join(str(r) for r in (below, above) if r is not None)
    raise KeyError(
        "0x%02X is not a documented S2-LP register%s"
        % (address, "; it lies between %s" % neighbours if neighbours else "")
    )


def contiguous_runs(addresses: Optional[Sequence[int]] = None) -> List[Tuple[int, int]]:
    """Group *addresses* into ``(start, count)`` runs that can be read in one go.

    The map is sparse - the documented registers are in blocks with gaps between
    them - and the radio answers a burst read of consecutive addresses. Reading
    the whole map as runs is a handful of commands instead of 123, which on a
    115200 baud link is the difference between a dump that feels instant and one
    that does not.
    """
    if addresses is None:
        addresses = [register.address for register in REGISTERS]
    ordered = sorted(set(int(address) for address in addresses))
    runs: List[Tuple[int, int]] = []
    for address in ordered:
        if runs and address == runs[-1][0] + runs[-1][1]:
            runs[-1] = (runs[-1][0], runs[-1][1] + 1)
        else:
            runs.append((address, 1))
    return runs


def decode(address: int, value: int) -> Dict[str, int]:
    """Field name to value for one register reading, by address."""
    return lookup(address).decode(value)


def describe(values: Dict[int, int]) -> Iterator[str]:
    """One readable line per register in *values*, in address order."""
    for address in sorted(values):
        try:
            register = lookup(address)
        except KeyError:
            yield "0x%02X %-22s = 0x%02X" % (address, "(undocumented)", values[address])
            continue
        yield register.describe(values[address])
