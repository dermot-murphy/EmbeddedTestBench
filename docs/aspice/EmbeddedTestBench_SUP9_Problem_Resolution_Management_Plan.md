<img src="../../assets/brand/svg/logos/embeddedtestbench-logo-compact.svg" alt="Embedded Test Bench" width="240">

# Problem Resolution Management Plan

*Automotive SPICE® PAM v4.0 | SUP.9 — Problem Resolution Management*

---

## 1. Document Identification & Control

| Field | Value | Field | Value |
|---|---|---|---|
| **Document ID** | ETB-SUP9-001 | **Version** | [latest, §2](#2-revision-history) |
| **Project** | Embedded Test Bench | **Date** | [latest, §2](#2-revision-history) |
| **Status** | [by location, ETB-SUP1-001 §6.3](EmbeddedTestBench_SUP1_Quality_Assurance_Plan.md#63-document-status) | **Classification** | Internal |
| **Author** | Claude | **Reviewer** | Dermot Murphy |
| **Approver** | Dermot Murphy | **Related Process** | SUP.9 |

> Reviewer and Approver are the same person; see ETB-DEV-002.

---

## 2. Revision History

| Version | Date | Author | Description of Change |
|---|---|---|---|
| 0.1 | 2026-09-19 | Claude | Initial |
| 0.2 | 2026-10-04 | Claude | #183: product renamed to Embedded Test Bench - document file name prefix `EmbeddedTestBench_`, identifier prefix `ETB-` (was `TB-`), product name in prose. Earlier revision rows keep the names in use when they were written. |
| 0.3 | 2026-10-05 | Claude | #204: Review & Approval table points to the merge of the pull request that last changed the document, which is the review and approval (ETB-SUP8-001 §5.7); no per-change signatures or dates. |
| 0.4 | 2026-10-05 | Claude | #194: the compact brand logo added above the title, the same line in every controlled document (ETB-SUP8-001 §6.3). |
| 0.5 | 2026-10-25 | Claude | #210: Version and Date in the identification table are links to the last revision history row, which holds them (ETB-SUP8-001 §6.2). |
| next | 2026-11-17 | Claude | #371: the Status cell links to the status rule, ETB-SUP1-001 §6.3. A document's status follows from where it is in the repository (Released, Agreed, In review, In work) and is not written in by hand. |
| next | 2026-11-17 | Claude | #377: Referenced Documents cite each controlled document at the version of its last numbered revision row, kept by `scripts/doc_versions.py` (ETB-SUP8-001 §6.2). |
| next | 2026-11-17 | Claude | #375: the plan follows the practice. §5 records severity by `severity: S1` to `S4` label and priority by milestone; §5.1 authorises urgent resolution of an S1; §5.2 alert notifications. §6 - a problem is an issue labelled `bug`, its ID the issue number. §7 - each state as the issue shows it. §9 - trend analysis per milestone and release, the first in §9.1. |

---

## 3. Purpose & Scope

### 3.1 Purpose

This plan says what counts as a problem in Embedded Test Bench, how problems are recorded,
classified, resolved and closed, and what may never be done to make one go away.

### 3.2 Referenced Documents

| Document ID | Title | Version |
|---|---|---|
| ETB-SUP1-001 | Embedded Test Bench Quality Assurance Plan | 0.5 |
| ETB-SUP8-001 | Embedded Test Bench Configuration Management Plan | 0.21 |
| ETB-SUP10-001 | Embedded Test Bench Change Request Management Plan | 0.5 |
| ETB-MAN5-001 | Embedded Test Bench Risk Management Plan | 0.7 |
| ETB-TMPL-001 | Embedded Test Bench Work Product Review Record — Template | 0.6 |

### 3.3 Scope

Problems found anywhere: in the code, the firmware, the documents, the bench
specifications, the CI workflows, or in an instrument's behaviour that Embedded Test Bench
must accommodate.

---

## 4. What Is a Problem

A problem is any observed difference between what Embedded Test Bench does and what its
documents say it does, or any observation that a Embedded Test Bench result cannot be
trusted. Specifically:

| Kind | Examples |
|---|---|
| Functional defect | A driver returns a wrong value; a limit compares the wrong way round |
| Evidence defect | A report omits an instrument identity; a simulated run is not labelled as such |
| Document defect | A requirement contradicts another; the design describes an interface that does not exist |
| Process defect | A change merged with a red build; a document not updated with its code |
| External behaviour | An instrument does something its documentation does not describe |
| Test defect | A test passes when the thing it tests is broken; a test asserts the simulator |

A **failing test is a problem**, always. It is never an infrastructure flake
until that has been shown, and showing it means identifying what failed and why
it was unrelated to the change.

---

## 5. Classification

| Severity | Meaning | Response |
|---|---|---|
| S1 Critical | A measurement produced by Embedded Test Bench could be wrong and be believed | Stop other work; fix before anything else is merged |
| S2 Major | A documented capability does not work, or evidence is missing from a result | Fix before the affected capability is used or released |
| S3 Minor | Incorrect but not misleading; a workaround exists | Scheduled against a milestone |
| S4 Cosmetic | Wording, formatting, a broken link | Fixed opportunistically |

| Priority | Meaning |
|---|---|
| P1 | Blocking work now |
| P2 | Needed for the next milestone |
| P3 | Whenever convenient |

Severity is about consequence and is not negotiable. Priority is about order of
work and is the project lead's call.

Severity is recorded on the issue with one of the labels `severity: S1` to
`severity: S4`, set when the problem is raised and changed, with the reason in a
comment, if the analysis shows it was wrong. Priority is recorded by the
issue's milestone (ETB-MAN3-001 §7): a P1 problem is in the current milestone
and named in the plan (§11), and P2 and P3 are in the next milestone or none.

### 5.1 Urgent Resolution (S1)

An S1 problem stops other work. When one is raised:

1. it is labelled `severity: S1` and pinned on the repository's issue list;
2. no other pull request is merged into `develop` or `main` until it is resolved,
   except one that resolves it or one the owner instructs, with the reason on
   the S1 issue;
3. any bench result that the defect could have made wrong is listed on the issue,
   and each is rerun or withdrawn before the issue closes.

The owner authorises the urgent action by instructing the fix. The session
records that instruction on the issue, quoting it with its date. An S2 problem
in a released baseline is handled the same way through a hotfix
(ETB-SUP8-001 §5.6).

### 5.2 Alert Notifications

| Event | Alert | Who receives it |
|---|---|---|
| A problem is raised | GitHub notifies the repository's watchers of the new issue | The owner, who watches the repository |
| `severity: S1` or `severity: S2` is applied | The issue is pinned, and a comment states the severity and what is affected | The owner, and every session that reads the open issues |
| A required check fails on `develop` or `main` | GitHub's failed-workflow notification for the run | The owner |
| A problem is found in a released baseline | The issue names the tag; ETB-SVD-001 lists it as a known problem in the next release | Readers of the release |

---

## 6. Problem Record

A problem is recorded as a repository issue labelled `bug`. Its ID is the issue
number, `#n`; there is no separate ETB-PR-nnn number, and no copy is kept under
`docs/aspice/`. A problem found during a review is raised in the review (the QA
review on the pull request, ETB-SUP1-001 §6.5, or ETB-TMPL-001 §7), and as an
issue when it is Critical or Major. The issue carries the fields below: in its
body when it is raised, and in comments as the analysis and resolution happen.

| Field | Content |
|---|---|
| **Problem ID** | The issue number, `#n` |
| **Raised by / date** | |
| **Found in** | Revision, document ID and version, or bench run |
| **Severity / Priority** | The `severity:` label and the milestone (§5) |
| **Observed** | What happened, verbatim where possible — output, failing assertion, instrument reply |
| **Expected** | What should have happened, and which requirement says so |
| **Reproduction** | The exact steps or command; "intermittent" is recorded as such with the frequency observed |
| **Analysis** | The cause, once known — not the symptom |
| **Resolution** | The change made, by revision |
| **Verification** | The test that now fails without the fix |
| **Related** | Risk ID if it materialised a risk; change request ID if one was needed |

---

## 7. Lifecycle

Each state is read from the issue as GitHub holds it, so no state is recorded by
hand that the tracker already shows.

| State | How it shows on the issue | Exit |
|---|---|---|
| Open | Open; no cause stated yet | A comment states the cause (Analysis) |
| Analysed | Open; the cause is stated and the severity label is confirmed | A pull request is linked |
| In progress | Open, with a linked open pull request | The pull request merges |
| Resolved | The linked pull request is merged, with a test that fails without the fix | Verified on the affected configuration |
| Closed | Closed as completed, with a closing comment naming the merged pull request and the test (Verification) | — |
| Rejected | Closed as not planned, with the reason in a comment | — |
| Deferred | Open, labelled `blocked`, with the reason and the milestone in a comment | Picked up at that milestone |

A problem fixed by the pull request that closes it is Resolved and Closed in one
step. Its closing comment is then the verification record.

A problem is closed only when there is a test that would catch it again. A fix
without such a test leaves the problem free to return unnoticed, which is the
same as not having fixed it.

---

## 8. Prohibited Resolutions

None of the following closes a problem:

1. Skipping, `xfail`-ing, deleting or weakening the test that found it.
2. Re-running CI until it passes, without identifying why it failed.
3. Widening a tolerance so a measurement fits, unless the wider tolerance is
   justified against the instrument's specification and the requirement is
   changed to match, through ETB-SUP10-001.
4. Recording an unexplained failure as a flake.
5. Changing the document to match the code when the code is what is wrong.

Item 5 has a legitimate mirror image: when the *document* is wrong, changing it
is the correct fix — and it goes through the same record, so the decision about
which was wrong is visible.

---

## 9. Trend Analysis

At each milestone and each release the open and closed problems are looked at
together for patterns: repeated problems in one element, repeated problems of
one kind, problems found late that earlier checks should have caught. A pattern
is treated as a defect in the process and raised against this plan or
ETB-SUP1-001, not as a run of bad luck. The analysis is recorded in §9.1, one
entry per milestone or release, newest last.

### 9.1 Trend Analyses

#### Release `v0.03.0000` (2026-11-17, #375)

The first trend analysis, covering every problem recorded up to the release: the
39 issues labelled `bug`, all closed. Before #375 only 5 of them stated a
severity, all as words ("Major", "Minor"), and 35 stated their cause in the
issue or its comments. The severity and the cause of each are therefore
assigned here, after the fact, from the issue, its comments and the pull
request that fixed it. Where the record does not show the cause, that is said.
The `severity:` labels were not applied to these closed issues; this table is
the record of their severity.

| Measure | Count |
|---|---|
| Problems | 39, all closed |
| By severity | S1 5, S2 16, S3 18, S4 0 |
| By kind | Functional 31, External behaviour 3, Test 2, Process 1, Document 1, Evidence 1 |
| By element | Nordic dongle driver 9, J-Link driver 7, dongle firmware 7, S2-LP driver 4, Kepler plugin and specifications 4, core, scripts and tests 4, GPD-3303D 2, TTi 1604 1, procedure 1 |
| Cause not determinable from the record | 2 (#237, a sensor firmware defect moved to Jira; #305, the "Permission denied" is unverified) |

**Patterns.**

1. **First contact with hardware.** At least ten problems are a driver or its
   simulator built on the same wrong assumption about an instrument, which
   passed every test until it met the real one: #30, #38, #61, #64, #69, #76,
   #177, #179, #256 and #314. Three of the five S1 problems (#76, #178, #256)
   are in this group or next to it. The control already in place is to treat a
   simulated pass as unconfirmed (ETB-SUP1-001 §7, ETB-RISK-001) and to run the
   driver on the bench before relying on it. The pattern says that control is
   the one that finds these. No change to this plan follows; the SYS.4 and
   SYS.5 hardware runs (#362, #363) are where it acts.
2. **Windows only.** Four problems appeared only on Windows: #79, #81, #214 and
   #305. A fifth, #384, was raised on 2026-11-17. CI runs on Linux only, and the
   bench PC runs Windows. Corrective action: a Windows leg in CI is proposed on
   #385.
3. **GDB Server state hidden from GDB.** #178, #349 and #352 are each the J-Link
   driver trusting GDB's view of the target after a `monitor` command that GDB
   does not see. They are fixed one at a time. ETB-SWE3-001's J-Link design is
   where the rule belongs, and it is carried there by #367.

| Problem | Severity | Kind | Element | Cause | Fixed by |
|---|---|---|---|---|---|
| #30 | S3 | Functional | firmware/nordic_dongle/ses (SES project, flash_placement.xml); docs/ble/BLE_Dongle_Notes.md | The SES project had never been built, since CI builds only the Makefile: no solution-level configurations, a project macro overriding -D SDK_ROOT, missing log include paths, a flash_placement.xml not matching SES linker conventions, no thumb_crt0.s or hex output, and an int-only printf. Fixed by PR #31 (c1a84db). | #31 |
| #32 | S2 | Functional | firmware/nordic_dongle/scripts/package_dfu.bat, package_dfu.sh; firmware/nordic_dongle/Makefile; docs/ble/BLE_Dongle_Notes.md | The scripts, Makefile and notes used SoftDevice ID 0xCA, which nrfutil lists as S140 7.0.1; S140 7.2.0 is 0x100. Fixed by PR #35 (c67d955). | #35 |
| #33 | S3 | Functional | firmware/nordic_dongle (bootloader_enter_dfu, command_dfu) | From PR #37: the PCA10059 open bootloader in SDK 17.1.0 is built with NRF_BL_DFU_ENTER_METHOD_PINRESET 1 and GPREGRET 0, so it ignored the 0xB1 written to GPREGRET; and one cdc_acm_process() pass only starts the USB transfer, so the reset lost the reply. Fixed by a pin reset via P0.19 and a bounded reply flush (PR #37, bb12beb). | #37 |
| #34 | S3 | Functional | firmware/nordic_dongle/include/firmware_version.h | The fallback build stamp '"local:" __DATE__ " " __TIME__' contains spaces, and the host splits reply fields on spaces. Fixed by PR #36 (2858526). | #36 |
| #38 | S2 | Functional | firmware/nordic_dongle/src (main.c, nus_client.c) | Nothing called ble_db_discovery_start() on BLE_GAP_EVT_CONNECTED, so discovery-complete never arrived (unit tests faked that event); once discovery was started a second cause appeared: events were forwarded by hand to modules that register their own observers, so each GATT response was handled twice. Fixed by PR #41 (807852f). | #41 |
| #39 | S3 | Functional | firmware/nordic_dongle/src/nus_client.c (nus_client_connect) | The connect scan used scan_params.timeout = 500 (5 s) and a window of 80 in an interval of 160 (50 % duty), too short for sensors advertising up to 9 s apart, and the host could not set the timeout. Fixed by PR #43 (3ed29e6). | #43 |
| #40 | S2 | Functional | benchtools/instruments/nordic_dongle/dongle.py (NordicDongle.open_link) | open_link raised without sending disconnect when the link never reached ready, and it waited its full timeout and used the 'linked but not ready' message even when the dongle had reported +disc with no +conn linked. Fixed by PR #42 (777f269). | #42 |
| #50 | S3 | Functional | benchtools/instruments/nordic_dongle/script.py (_cells) | _cells() split a table row on every '\|' (stripped.split('\|')), so an escaped '\\|' still split the cell. Fixed by splitting only on unescaped pipes (PR #55, 9629931). | #55 |
| #51 | S2 | Evidence | benchtools/instruments/nordic_dongle (run_script, NordicDongle.is_linked); event log (BLE-FR-115) | run_script read dongle events only while a step waited for its own reply, so a +disc during a delay or between steps went unnoticed, no DISCONNECT event was logged, and is_linked was never cleared. Fixed by PR #58 (2051d83). | #58 |
| #61 | S2 | Functional | benchtools/instruments/gpd3303d (driver, simulator); serial transport | The driver and simulator were written from assumptions rather than the V1.09 supply: reply terminator \r not \n, STATUS? as spaced fields plus two legend lines, output on bit 6, tracking bits in the opposite order, and 0.1 V / 0.01 A read-back resolution against a 50 mV regulation tolerance. Fixed by PR #62 (7708be3). | #62 |
| #64 | S3 | Document | PSU-FR-002, PSU-FR-003; TB-SWE3-001; READMEs; GPD-3303D notes; GPD-3303D simulator | Requirements, design, docs and simulator were written assuming the supply clamps an out-of-range setting; the V1.09 supply keeps the setpoint and reports 'Data out of range.' (and read-back resolution is 0.1 V, contradicting PSU-FR-003's equality). Corrected by PR #65 (3506aea). | #65 |
| #69 | S2 | Functional | benchtools/instruments/jlink (GdbServer, find_gdb, JLinkProbe, CLI) | Written and tested only against a simulator: the spawned server used -singlerun and exited after the TCP readiness probe, find_gdb accepted a non-ARM gdb, only PATH was searched, no erase command existed, and the GDB Server halts on attach while -target-detach does not resume. Further hardware faults (flash erase reported O.K. while firmware ran, MI parser, structure values, UICR ID erased by the HEX) were fixed on the way. Fixed by PRs #72 and #73. | #72, #73 |
| #76 | S1 | Functional | benchtools/instruments/s2lp (driver, reply parser, register map); docs/s2lp/S2LP_Devkit_Notes.md | The driver was written against ST's published CLI source and a simulator and had never been run on a kit, so it assumed tag names, number formats, a board identification reply, a millisecond timer and gap-free capture that the real firmware does not provide. Fixed, with further hardware faults (nIRQ routing, PN9 TX source, port timeout), by PR #78 (44a06c0). | #78 |
| #79 | S3 | Functional | benchtools/core/transport (ProcessTransport.read_message); tests/test_layering.py | From PR #92: on Windows a child's text-mode stdout ends lines with CR LF and ProcessTransport split on LF, returning b'done\r'; and the layering test's pre-3.10 standard-library fallback looked only under Lib, while Windows extension modules such as select live in DLLs. Fixed in the transport and the helper (PR #92, 0027d12). | #92 |
| #81 | S3 | Functional | scripts/lint.py (key_of) | key_of keyed findings on pylint's path, which has backslashes on Windows, while .pylint-baseline.json uses forward slashes, so no finding matched its baseline entry. Fixed by normalising the path to POSIX form (PR #91, d759034). | #91 |
| #99 | S2 | Functional | benchtools/instruments/s2lp (prepare_traffic, receive set-up) | Stopping a receive leaves an interrupt pending in IRQ_STATUS, holding the active-low nIRQ line (GPIO3) low, so the firmware never sees the falling edge it waits for; prepare_traffic cleared IRQ_STATUS only once per session. Fixed by clearing IRQ_STATUS and checking the line before every send and receive (PR #100, 148fc41). | #100 |
| #108 | S2 | Functional | benchtools/instruments/jlink/rtt.py (RttClient._pump) | _pump runs on both the reader thread and the caller's thread and called self._backend.rtt_poll() before taking self._lock, so two pumps could poll at once and the simulator's check-then-pop drain raised. Fixed by polling under the lock (PR #107, 67ba78e; D-42). | #107 |
| #109 | S3 | Process | Configuration management procedure (CLAUDE.md / ETB-SUP8-001 section 5); main branch | PR #106 was merged into main (a9c813f) although work merges to develop first, putting a second, independently written TTi 1604 driver on main. Why its base was main is not recorded beyond the rule being broken (the rule was then written down by #113). Reverted by PR #110 (a110e95). | #110 |
| #124 | S3 | Functional | benchtools/instruments/nordic_dongle/cli.py (_select, _cmd_cmd) | _select scanned with a substring name filter but then called dongle.select(), whose find_sensor matches names exactly and treats a non-match as an address; _cmd_cmd never read args.addr. Fixed by resolving names and fragments through select_by_name and honouring --addr (commit e24ee5c, PR #125). | #125 |
| #177 | S2 | Functional | benchtools/instruments/jlink/probe.py (JLinkProbe.reset) | reset(halt=False) sent 'monitor reset 0' and nothing resumed the core, because SEGGER's GDB Server halts after any monitor reset; the simulator had modelled reset 0 as reset-and-run since D-39, which hid it. Fixed by resuming with -exec-continue after the reset (PR #212, ba8932a). | #212 |
| #178 | S1 | Functional | benchtools/instruments/jlink/probe.py (JLinkProbe.reset) | reset() resets and halts through GDB Server 'monitor' commands that GDB does not see, so GDB kept its pre-reset register cache; confirmed on the bench (monitor reg pc gave 0xA80 while GDB returned the old PC). Fixed by 'maintenance flush register-cache' after every reset (PR #213, c125230). | #213 |
| #179 | S2 | Functional | benchtools/instruments/s2lp (restore_defaults, power_cycle, receive set-up) | The issue's suspected cause (the transmit) was wrong: the defaults reset before the receive put GPIO3_CONF back to 0xA2 (a GND output) and IRQ_MASK to 0 while the driver still trusted the interrupt routing from the earlier send, shown on the kit with no transmit. Fixed by having both resets make the next send or receive route the interrupt again (PR #278, ef3e7d23b). | #278 |
| #180 | S3 | Functional | benchtools/instruments/nordic_dongle (NordicDongle.open_link) | open_link made a single attempt, while a command document's connect step already retried up to three times, so the two paths into a link differed. Fixed by a bounded 0x3E retry shared through CONNECT_ATTEMPTS, each attempt logged (PR #234, c91e95d). | #234 |
| #181 | S2 | External behaviour | benchtools/instruments/tti1604 (select_hertz, measure); TTi 1604 multimeter | The meter's behaviour was unhandled: in Hz with no signal it sends no frames and ignores every key over the link until V is pressed on the front panel, and on open ohms it sends six blank frames over 2.8 s while auto-ranging; the driver confirmed a mode only from frames and the test read a single frame. Fixed by waiting past blank frames and reporting the Hz stall (PR #317, b197cd0). | #317 |
| #214 | S3 | Functional | benchtools/instruments/nordic_dongle (NordicDongle.sample_command); tests/instruments/nordic_dongle/test_sampling.py | sample_command scheduled commands from time.monotonic(), which on Windows CPython before 3.13 is GetTickCount64 with 15.625 ms resolution, and did not repeat a sleep that ended early. Fixed by timing with perf_counter and sleeping until each command is due (PR #227, 2e7550d). | #227 |
| #236 | S3 | External behaviour | Kepler sensor firmware (innovateuk-sensor, APP_Normal_RadioVersionStringBuild); specs/kepler_version.yaml | The V11 firmware builds the VERSION frame's version field with '%s %s' from API_PARAM_VERSION and API_PARAM_SHA, carried over from V10.01.2000's APP_Normal_RadioAction, although V11 also writes the SHA to its own field. Moved to Jira TX-1052; no ETB pull request is in the record. | none (sensor firmware, Jira) |
| #237 | S3 | External behaviour | Kepler sensor firmware (innovateuk-sensor), BLE advertising name | Not determinable from the record: the issue says where the cut happens is not known (lack of room in the advertising packet is suspected but unchecked), and it was moved to Jira TX-1053 as a sensor firmware defect with no ETB change. | none (sensor firmware, Jira) |
| #251 | S2 | Functional | benchtools/instruments/nordic_dongle (open_link, _disconnect, DISCONNECT_EVENT_TIMEOUT); firmware/nordic_dongle/src/nus_client.c | A race: after a sensor reset the dongle reports +disc only at the 4 s supervision timeout, but the driver waited 2 s, so the late event stayed unread and the next open_link took it as its own failure; the firmware's disconnect could not cancel a pending connect (no sd_ble_gap_connect_cancel), so later connects got err 10 and the pending connect linked unseen. Analysed and confirmed on hardware in the issue comments; fixed in firmware 1.5.0 and the driver (PR #257, 623cf8c). | #257 |
| #256 | S1 | Functional | firmware/nordic_dongle (Makefile nano.specs; 64-bit printf formats) | The firmware formatted 64-bit values with %llu while the Makefile links newlib-nano (--specs=nano.specs), whose printf has no long long support; host unit tests link a full C library and the bench dongle ran an SES build, so nothing caught it. Fixed by timestamp_format_us() for all 64-bit output and a CI guard against long long conversions (PR #258, a7a62bb). | #258 |
| #259 | S3 | Functional | benchtools/instruments/jlink/probe.py (flash, reset) | flash() called reset(halt=True), and reset() sent 'monitor reset' without interrupting a running core; the GDB Server refuses monitor commands while the core runs. Fixed by halting through -exec-interrupt before any monitor command, and before load (PR #262, 7e9c9a9). | #262 |
| #271 | S2 | Functional | benchtools/instruments/nordic_dongle (send_package DFU client) | The client did not check Packet Receipt Notifications against what it had sent, found a lost 20-byte piece only at the object's checksum, and had no recovery. The loss came about 0.2 s after a data object's create, inferred (not traced in the bootloader) to be writes arriving during the flash page erase. Fixed by checking every receipt and resending the image with a pause after each data create, bounded and logged (PR #272, hotfix v0.02.0001). | #272 |
| #275 | S3 | Functional | benchtools/instruments/nordic_dongle (send_package, _open_dfu_link) | #244 (37e9939) added send_package with its own connect, _open_dfu_link, without the bounded 0x3E retry that open_link has had since #180 (d31d608). Fixed by routing it through the same retry loop (PR #276, hotfix v0.02.0002). | #276 |
| #293 | S2 | Functional | benchtools/instruments/s2lp/traffic.py (kepler_frame, _stream_batch); MockTransport | When a call returned, _stream_batch's finally stopped the board and any reports arriving with the stop were logged and dropped, so the next call started with nothing (confirmed in code, on the simulated kit and on hardware); MockTransport also discarded undelivered simulator output on the stop write. Fixed by setting those frames aside for kepler_frame(since_last=True) (PR #298, c552778); the remaining 26-27 ms deaf gap was split to #299. | #298 |
| #305 | S3 | Test | tests/test_doc_versions.py (TestMergeDriver); scripts/doc_versions.py (_conflict_style) | The underlying 'Permission denied' writing .git/objects is not determinable from the record: it is stated as unverified (a scanner holding new object files is suspected, and it was reproduced outside pytest on a plain git add). The test's own weakness is recorded: repository() ran git setup with check=False. PR #310 (67212eb) checks setup, retries refused object writes, and gives _conflict_style the merged file's folder. | #310 |
| #313 | S2 | Functional | plugins/kepler/decoder.py (LAYOUTS) | LAYOUTS held only the V11 TWF layout (type version 1, 100 bytes); a type-version-0 frame fell back to it (#287), so the 96-byte V10.00 frame was rejected as too short. Fixed by adding the V10.00 layout taken from the V10.00.0000 firmware source (PR #333, 9fe25a0). | #333 |
| #314 | S2 | Test | specs/kepler_version.yaml, kepler_battery.yaml, kepler_temperature.yaml; benchtools/simulated/kepler.py | The specification patterns were written for the V11.00 reply form ('= (\d+)mV'); V11.02 firmware puts a space before the unit (and changes reply case and writes 'Sec'), and the simulated sensor still answered in the old form, which hid it. Fixed with patterns accepting both forms and tests against both (PR #315, 77a0056). | #315 |
| #319 | S3 | Functional | benchtools/core/transport/serial_port.py (SerialTransport._split_baudrate) | _split_baudrate treated a trailing :<digits> as a line rate unless the host name had no dot, so a socket:// URL with an IP address lost its TCP port. Fixed so a pyserial URL keeps its whole text and only a bare port name carries a rate (PR #332, b2417b4). | #332 |
| #349 | S1 | Functional | benchtools/instruments/jlink/probe.py (JLinkProbe.attach, halt) | attach() set _halted=True on the assumption that the GDB Server halts the core on every attach; an attach made after an earlier client's 'monitor go' (which GDB never sees) finds the core running, and halt() then returned early. Fixed by sending 'monitor halt' and flushing GDB's register cache after -target-select (PR #351, 30ba9cb); ETB-DOCK-001 aligned in PR #354. | #351, #354 |
| #352 | S1 | Functional | benchtools/instruments/jlink (JLinkProbe.read_variable) | read_variable read whatever address GDB gave the variable without checking it; a static discarded by the linker keeps a DWARF entry at address 0, so the read returned flash address 0 (the vector table). Fixed by refusing address-0 variables in read_variable, write_variable and variable_address (PR #353, 357774d). | #353 |

---

## 10. Review & Approval

Review and approval of this document are not entered in this table. They are
given by the merge of the pull request that last changed the document, and that
merge is the record (ETB-SUP8-001 §5.7). The evidence is the pull request, its
CI result and its merge record: who merged it, when, and the merge commit. The
last row of the revision history names the issue, and the issue links the pull
request.

| Role | Name | Recorded by |
|---|---|---|
| Author | Claude | The commits in the pull request |
| Reviewer | Dermot Murphy | The merge of the pull request that last changed this document |
| Approver | Dermot Murphy | The merge of the pull request that last changed this document |
