# VISA Determination Report — Tektronix TDS3014B over Ethernet

| Field | Value |
|---|---|
| Document ID | TEK3014B-VISA-001 |
| Version | 1.0 |
| Date | 2026-09-12 |
| Status | Released for review |
| Question | Must VISA be used to drive a TDS3014B over Ethernet? |

---

## 1. Executive answer

**No. VISA is not required.**

But the corollary matters just as much, and is the part that usually bites:

**A plain TCP socket is not sufficient either.**

The TDS3014B's Ethernet port does not speak SCPI over a bare TCP stream. It exposes an
**ONC-RPC (Sun RPC) server implementing the VXI-11 TCP/IP Instrument Protocol**. What a
driver actually needs is therefore a **VXI-11 client** — not a VISA installation.

VXI-11 is an open, published specification. It can be, and in this deliverable **has been**,
implemented directly on top of the Python standard library's `socket` and `struct` modules.
The result is a driver with **zero mandatory third-party dependencies**.

| Claim | Verdict |
|---|---|
| A VISA library (NI-VISA / TekVISA / Keysight IO) is mandatory | **False** |
| A raw TCP socket carrying SCPI text is sufficient | **False** — no such service on this model |
| A VXI-11 / ONC-RPC client is required | **True** |
| That client must come from a third party | **False** — implemented here in ~320 lines of stdlib Python |

---

## 2. Why the "VISA is required" belief exists

Tektronix's own programmer documentation for the TDS3000/TDS3000B series states that
applications communicating with the instrument over Ethernet must use a VISA, and points
users at TekVISA. That statement is accurate as a description of **Tektronix's supported
toolchain**; it is not a statement about the **protocol**.

The distinction is the whole answer:

- **VISA** is an *API standard* (VPP-4.3, IVI Foundation). It is one way for application
  code to reach an instrument. It is a library on the host, not something the instrument
  is aware of.
- **VXI-11** is a *wire protocol* (VXIbus Consortium, 1995; now maintained under the IVI
  Foundation / LXI umbrella). It is what actually travels over the Ethernet cable.

A VISA library, when given a `TCPIP::…::INSTR` resource, implements VXI-11 internally.
Nothing about VXI-11 is proprietary or undocumented, so an application can implement the
same protocol itself and reach the instrument identically. The instrument cannot tell the
difference, because there is no difference on the wire.

---

## 3. What the instrument actually exposes

| Service | Port | Protocol | Usable for programmatic control? |
|---|---|---|---|
| VXI-11 portmapper | 111/tcp, 111/udp | ONC-RPC `PMAP` (prog 100000 v2) | Indirectly — resolves the core channel port |
| VXI-11 core channel | dynamic | ONC-RPC prog `0x0607AF` v1 | **Yes — this is the control interface** |
| e*Scope web server | 80/tcp | HTTP | Browser control and screen viewing only; not a SCPI interface |
| Raw SCPI socket | — | — | **Not present on this model** |

### 3.1 On the absence of a raw socket

Port 4000 raw-socket SCPI is a genuinely useful and much simpler interface, and it *does*
exist on later Tektronix instruments sharing this command set (TDS3000C, DPO/MSO 2000/3000/4000
series). It is **not** available on the TDS3000B generation. Anyone planning to use
`socket.connect((ip, 4000))` with this instrument should stop there.

The driver still ships a raw-socket transport (`tek3014b.transport.socket_raw`), for three
reasons: it drives those later instruments unchanged, it allows a SCPI gateway to be placed
in front of the scope, and it keeps the transport abstraction honest by having more than one
real implementation behind it.

### 3.2 Why the raw socket would be inferior here anyway

Worth recording, because it explains a design decision in the driver: a raw TCP stream has
**no end-of-message indication**. VXI-11 carries an explicit END flag on `device_read`.
This matters for exactly one operation — **hardcopy** — where the instrument streams an
image with no length prefix and no usable terminator. Over VXI-11 the transfer ends
deterministically at END; over a raw socket it can only be bounded by an inter-byte idle
timeout, which is a heuristic. Waveform transfers are unaffected, because `CURVe?` carries
an IEEE 488.2 length prefix.

---

## 4. Protocol detail implemented

The core channel is ONC-RPC (RFC 5531) with XDR-encoded arguments (RFC 4506), over TCP with
record marking. The driver implements:

| Procedure | Number | Used for |
|---|---|---|
| `create_link` | 10 | Opening the session |
| `device_write` | 11 | Sending SCPI, chunked to the link's `maxRecvSize` |
| `device_read` | 12 | Reading responses until the END flag |
| `device_readstb` | 13 | Status byte while the instrument is busy |
| `device_trigger` | 14 | GPIB GET equivalent |
| `device_clear` | 15 | GPIB DCL equivalent |
| `device_remote` / `device_local` | 16 / 17 | Front-panel lockout |
| `destroy_link` | 23 | Closing the session cleanly |

### 4.1 The logical device name trap

`create_link` takes a logical device name, and this is the single most common cause of
"it won't connect" on this instrument family:

- **VXI-11.3** (instrument) devices use `inst0`.
- **VXI-11.2** (GPIB emulation) devices use `gpib0,1`.

Reports on the TDS3000B family are inconsistent — some units and firmware revisions are
described as behaving as VXI-11.2 devices, while working configurations elsewhere use
`inst0`. Rather than pick one and be wrong half the time, the driver **probes** them in
order (`inst0`, `gpib0,1`, `hpib,7`, `inst`) and reports which one was accepted via
`Vxi11Transport.device_name`. A specific name can be forced with
`vxi11://<host>/<name>`.

### 4.2 Other practical constraints

- The instrument supports a **limited number of simultaneous VXI-11 links** (in practice
  one). The driver always issues `destroy_link` on close, and is usable as a context
  manager so an exception cannot leak the link. If a connection is refused after a crashed
  session, power-cycling the instrument's Ethernet interface clears the stale link.
- `*OPC?` returns as soon as the command is **parsed**, not when the acquisition finishes.
  Acquisition completion must be polled with `BUSY?`. The driver does this.
- Hardcopy must have `HARDCopy:PORT` set to the command interface (`GPIb`), otherwise the
  image goes to a printer port and the read hangs until it times out.

---

## 5. Verification performed

| # | What was verified | How | Result |
|---|---|---|---|
| V1 | XDR codec round-trips all used types, with correct 4-byte padding | Unit tests, incl. every payload length mod 4 | Pass |
| V2 | Client interoperates with an **independently implemented** RPC server | `tests/vxi11_server.py` — written against the spec, not sharing the client's codec | Pass |
| V3 | Device-name probing recovers a VXI-11.2-only instrument | Server configured to accept only `gpib0,1` | Pass |
| V4 | Large transfers reassemble across `maxRecvSize` chunks | 10 000-point record over a 1 kB link | Pass |
| V5 | Long commands are split and reassembled server-side | Command exceeding `maxRecvSize` | Pass |
| V6 | Portmapper `GETPORT` is correctly formed | Loopback portmapper | Pass |
| V7 | The complete driver works over a real VXI-11 socket | Configure, trigger, capture 10 000 points | Pass |
| V8 | **The same driver works unmodified through PyVISA** | `pyvisa` + `pyvisa-py` against the same server | Pass |

V8 is the cross-check that closes the argument: pyvisa-py contains its own, independent
VXI-11 implementation. Both it and the built-in transport drive the same instrument model
to the same result over the same protocol. The VISA layer is demonstrably **optional
middleware**, not a requirement.

### 5.1 Limits of this verification — read this before the bench

These results were obtained against a **protocol-level simulator**, not against physical
hardware. That is sufficient to prove the protocol implementation is correct and
self-consistent, and it is what makes the test suite reproducible in CI. It is **not**
sufficient to prove firmware-specific behaviour.

The following must be confirmed on a real TDS3014B before this driver is used for
qualification work:

1. **Which logical device name the unit accepts.** Run `tek3014b -r <ip> -v idn` and read
   the logged device name. Probing should handle it, but confirm.
2. **Whether the portmapper answers over TCP or only UDP.** The driver tries TCP then UDP.
   If both fail, pass `core_port=` explicitly.
3. **That `HARDCopy:FORMat PNG` is accepted by the installed firmware.** Older firmware may
   not offer PNG; the driver reads the format back and falls back to `BMPCOLOR`, but the
   fallback path should be exercised once deliberately.
4. **Measurement settling.** The instrument's measurement engine may need time to refresh
   after `MEASUrement:IMMed:TYPe` changes. `measure(..., settle=)` exists for this; the
   required value is firmware- and timebase-dependent and defaults to 0.
5. **Record length options.** Confirm `HORizontal:RECOrdlength?` reports 500/10000 as
   assumed by `ModelLimits`.

Additionally, the Tektronix programmer manual could not be retrieved during this work
(the network policy of the build environment blocks those hosts), so the SCPI command
spellings were taken from established knowledge of the TDS3000 command set rather than
transcribed from the manual. They are internally consistent and the simulator rejects
anything it does not recognise into the event queue — so a wrong spelling surfaces as an
`InstrumentError` rather than silently — but **the command set should be spot-checked
against the manual on first bench use**.

---

## 6. Options compared

| Option | Third-party deps | Works on TDS3014B | Notes |
|---|---|---|---|
| **Built-in VXI-11 transport** (default) | **None** | Yes | Recommended. Deployable anywhere Python runs, including locked-down CI. |
| `pyvisa` + `pyvisa-py` | 2 pure-Python | Yes | Reasonable if the site already standardises on the VISA API. |
| `pyvisa` + NI-VISA / TekVISA | 1 Python + a large native install | Yes | Only worth it where a licence server, instrument inventory or existing LabVIEW rig already depends on it. Adds a heavyweight platform-specific install. |
| Raw TCP socket | None | **No** | No such service on this model. |
| e*Scope (HTTP) | None | Partially | Human-operated browser control and screen grabs; not a programmable SCPI path. |

---

## 7. Recommendation

Use the **built-in VXI-11 transport**. It is the default, so a bare address is enough:

```python
from tek3014b import Tek3014B

with Tek3014B.connect("192.168.1.50") as scope:   # no VISA anywhere
    print(scope.identity())
```

Keep the PyVISA transport available as an opt-in (`pip install tek3014b[visa]`,
`backend="visa"`) so a site with an existing VISA estate is not forced off it. Do not make
it the default: it turns a dependency-free driver into one that needs a native library
installed on every test host, for no capability gain on this instrument.

---

## 8. References

- VXIbus Consortium, *VXI-11: TCP/IP Instrument Protocol Specification* (and VXI-11.2,
  VXI-11.3), 1995 — the protocol implemented here.
- IETF RFC 5531, *RPC: Remote Procedure Call Protocol Specification Version 2*.
- IETF RFC 4506, *XDR: External Data Representation Standard*.
- IVI Foundation, *VPP-4.3: The VISA Library* — the API standard shown here to be optional.
- Tektronix, *TDS3000, TDS3000B and TDS3000C Series Digital Phosphor Oscilloscopes
  Programmer Manual*, 071-0381-03 — SCPI command set (see §5.1 caveat).
