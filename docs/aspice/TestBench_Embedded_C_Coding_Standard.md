# TestBench Embedded C Coding Standard

*Automotive SPICE® PAM v4.0 | SWE.3, SWE.4, SUP.1 — Embedded C for TestBench firmware*

---

## Document Identification & Control

| Field | Value | Field | Value |
|---|---|---|---|
| **Document ID** | TB-STD-002 | **Version** | 0.2 |
| **Project** | TestBench | **Date** | 2026-09-19 |
| **Status** | Draft | **Classification** | Internal |
| **Author** | Claude | **Reviewer** | Dermot Murphy |
| **Approver** | Dermot Murphy | **Related Process** | SWE.3, SWE.4, SUP.1 |

> Reviewer and Approver are the same person; see TB-DEV-002.

> This document keeps its own numbered structure, which the identification
> block above precedes rather than renumbers. Sections marked `[RULE: TBD]`
> are structural placeholders carried over deliberately: the rule they will
> carry is not yet decided, and inventing one would be worse than saying so.

## Revision History

| Version | Date | Author | Description of Change |
|---|---|---|---|
| 0.1 | 2026-09-19 | Claude | Initial |
| 0.2 | 2026-09-30 | Claude | §1.2: scope names the dongle firmware's host unit tests, `firmware/nordic_dongle/test/`; §1.3: the tests' stand-ins for nRF5 SDK headers are vendor API; §7.4: CStyleCheck runs on the tests in their own step, clean and without a baseline (#111). |

---

## Table of Contents

1. [Purpose and Scope](#1-purpose-and-scope)
2. [Terms and Definitions](#2-terms-and-definitions)
3. [Normative References](#3-normative-references)
4. [ASPICE Compliance Notes](#4-aspice-compliance-notes)
5. [Roles and Responsibilities](#5-roles-and-responsibilities)
6. [Rule Classification System](#6-rule-classification-system)
7. [Compiler and Toolchain Requirements](#7-compiler-and-toolchain-requirements)
8. [Language Subset — Permitted C Features](#8-language-subset--permitted-c-features)
9. [Language Subset — Prohibited C Features](#9-language-subset--prohibited-c-features)
10. [Data Types and Type Safety](#10-data-types-and-type-safety)
11. [Integer Types — Selection and Use](#11-integer-types--selection-and-use)
12. [Integer Arithmetic and Overflow](#12-integer-arithmetic-and-overflow)
13. [Implicit and Explicit Type Conversions](#13-implicit-and-explicit-type-conversions)
14. [Pointer Types and Pointer Safety](#14-pointer-types-and-pointer-safety)
15. [Arrays and Buffer Safety](#15-arrays-and-buffer-safety)
16. [String Handling](#16-string-handling)
17. [Boolean Expressions](#17-boolean-expressions)
18. [Bitwise Operations](#18-bitwise-operations)
19. [Memory Management — Static Allocation](#19-memory-management--static-allocation)
20. [Memory Management — Dynamic Allocation](#20-memory-management--dynamic-allocation)
21. [Memory Management — Stack Usage](#21-memory-management--stack-usage)
22. [Memory Management — Volatile and Shared Data](#22-memory-management--volatile-and-shared-data)
23. [Control Flow — General](#23-control-flow--general)
24. [Control Flow — `goto`](#24-control-flow--goto)
25. [Control Flow — Recursion](#25-control-flow--recursion)
26. [Control Flow — Infinite Loops](#26-control-flow--infinite-loops)
27. [Control Flow — `break` and `continue`](#27-control-flow--break-and-continue)
28. [Control Flow — `switch` Statements](#28-control-flow--switch-statements)
29. [Functions — Design Rules](#29-functions--design-rules)
30. [Functions — Parameters and Return Values](#30-functions--parameters-and-return-values)
31. [Functions — Prototypes and Declarations](#31-functions--prototypes-and-declarations)
32. [Functions — Inline Functions](#32-functions--inline-functions)
33. [Functions — Recursion](#33-functions--recursion)
34. [Functions — Assertions](#34-functions--assertions)
35. [Preprocessor — Conditional Compilation](#35-preprocessor--conditional-compilation)
36. [Preprocessor — Header Inclusion](#36-preprocessor--header-inclusion)
37. [Preprocessor — Macros vs. Functions](#37-preprocessor--macros-vs-functions)
38. [Preprocessor — Token Pasting and Stringification](#38-preprocessor--token-pasting-and-stringification)
39. [Global Variables](#39-global-variables)
40. [File-Scope Static Variables](#40-file-scope-static-variables)
41. [Constants — `const` vs. `#define`](#41-constants--const-vs-define)
42. [Initialisation](#42-initialisation)
43. [Scope and Lifetime](#43-scope-and-lifetime)
44. [Linkage](#44-linkage)
45. [Structures and Unions](#45-structures-and-unions)
46. [Bit Fields](#46-bit-fields)
47. [Enumerations](#47-enumerations)
48. [Standard Library Usage](#48-standard-library-usage)
49. [Restricted Standard Library Functions](#49-restricted-standard-library-functions)
50. [Concurrency — Interrupt Safety](#50-concurrency--interrupt-safety)
51. [Concurrency — RTOS Task Safety](#51-concurrency--rtos-task-safety)
52. [Concurrency — Atomic Access](#52-concurrency--atomic-access)
53. [Error Handling — Strategy](#53-error-handling--strategy)
54. [Error Handling — Return Codes](#54-error-handling--return-codes)
55. [Error Handling — Assertions](#55-error-handling--assertions)
56. [Error Handling — Safe State and Fail-Safe Behaviour](#56-error-handling--safe-state-and-fail-safe-behaviour)
57. [Hardware Abstraction](#57-hardware-abstraction)
58. [Register Access](#58-register-access)
59. [Interrupt Service Routines](#59-interrupt-service-routines)
60. [Watchdog](#60-watchdog)
61. [Timing and Delays](#61-timing-and-delays)
62. [Floating-Point Arithmetic](#62-floating-point-arithmetic)
63. [Portability](#63-portability)
64. [Undefined, Unspecified, and Implementation-Defined Behaviour](#64-undefined-unspecified-and-implementation-defined-behaviour)
65. [MISRA C:2012 Compliance Mapping](#65-misra-c2012-compliance-mapping)
66. [CERT C Compliance Mapping](#66-cert-c-compliance-mapping)
67. [Sign Compatibility](#67-sign-compatibility)
68. [Declared-But-Not-Defined Identifiers](#68-declared-but-not-defined-identifiers)
69. [Static Analysis Tools](#69-static-analysis-tools)
70. [Code Review for Standards Compliance](#70-code-review-for-standards-compliance)
71. [Unit Verification Criteria](#71-unit-verification-criteria)
72. [Deviation Procedure](#72-deviation-procedure)
73. [Document Change History](#73-document-change-history)

---

## 1. Purpose and Scope

### 1.1 Purpose

This document defines the **behavioural coding rules** that govern what the C
code in this project does and how it is constructed: type safety, memory
management, control flow, concurrency, error handling and hardware interaction.

Style and formatting rules — what the code looks like — are the companion
Embedded C Style Guide (TB-STY-001).

This standard exists to:

- prevent defects caused by undefined, unspecified or implementation-defined C
  behaviour;
- keep the firmware portable across target MCU architectures, so that a second
  bench dongle or a second target part does not mean a rewrite;
- satisfy the coding-related requirements of ASPICE v4 Level 2 (SWE.3, SWE.4)
  and TB-SYS2-092;
- align with the MISRA C:2012/2023 rules applicable to embedded software;
- be enforceable by machine, through the CStyleCheck action pinned in
  `.github/workflows/style.yml`.

### 1.2 Scope

This standard applies to:

- all `.c` and `.h` files owned by this project — in practice
  `firmware/nordic_dongle/src/` and its headers, and the firmware's host unit
  tests in `firmware/nordic_dongle/test/`;
- all new C files added to this project;
- existing files undergoing a modification that touches more than 20% of their
  lines.

### 1.3 Out of Scope

| Excluded | Why |
|---|---|
| Stand-ins for nRF5 SDK headers and functions in `firmware/nordic_dongle/test/support/` (`include/*.h`, and the SDK functions in `fake_sdk.c`) | They must reproduce the SDK's own names to stand in for it; the project's own `fake_*` controls in the same files remain in scope |
| Nordic nRF5 SDK sources and the S140 SoftDevice | Vendor-supplied; not modified by this project, and its licence governs it (TB-ACQ4-001 §4) |
| `config/sdk_config.h` | A vendor configuration artefact whose keys and layout are the SDK's, not this project's |
| Linker scripts, startup code and assembly (`.s`, `.S`) | Vendor-supplied or toolchain-generated |
| Build files (`Makefile`, `*.emProject`) | Not C |
| Python source | `benchtools` is governed by TB-SWE2-001 and the project's Python conventions, not by this standard |

An excluded file is excluded because someone else owns it, not because the rules
are inconvenient. A project file that would be easier to write by breaking a
rule is a deviation (§72), recorded as one.

### 1.4 Relationship to Other Documents

| Document | ID | Relationship |
|---|---|---|
| TestBench Embedded C Style Guide | TB-STY-001 | Companion — governs formatting |
| Industry C Coding Standards — Applicability | TB-STD-001 | Which external standards this one draws on, and why |
| TestBench System Requirements | TB-SYS2-001 | TB-SYS2-092 requires conformance to this standard |
| TestBench Quality Assurance Plan | TB-SUP1-001 | TB-QA-006 — the check that enforces it |
| CStyleCheck `rules.yml` | (tool config) | Machine-readable enforcement subset |
| MISRA C:2012 | (external) | Primary normative standard |

---

## 2. Terms and Definitions

| Term | Definition |
|---|---|
| **Undefined behaviour (UB)** | C11 §3.4.3 — Behaviour upon use of a non-portable or erroneous construct for which the standard imposes no requirements. The compiler may do anything. |
| **Unspecified behaviour** | C11 §3.4.4 — Two or more behaviours are possible; the standard does not specify which. |
| **Implementation-defined behaviour** | C11 §3.4.1 — Behaviour that is documented by the compiler vendor and consistent, but varies between implementations. |
| **Constraint violation** | Failure to satisfy a syntax or semantic rule for which the standard requires a diagnostic. |
| **Essential type** | The conceptual type of an expression under the MISRA C:2012 Essential Type Model, used to categorise operands for type safety checks. |
| **Atomic operation** | An operation that completes without interruption and cannot be interleaved with other operations on the same data. |
| **Critical section** | A code region protected against concurrent access by disabling interrupts or holding a mutex. |
| **Safe state** | A system state in which no harm can occur while the system waits for recovery or shutdown. |
| **ASIL** | Automotive Safety Integrity Level (ISO 26262), A through D, D being most stringent. |
| **SIL** | Safety Integrity Level (IEC 61508), 1 through 4, 4 being most stringent. |
| **RTOS** | Real-Time Operating System. |
| **ISR** | Interrupt Service Routine — a function invoked directly by hardware interrupt. |
| **HAL** | Hardware Abstraction Layer. |
| **MCU** | Microcontroller Unit. |
| **cstylecheck** | The project style and naming compliance checker. |

---

## 3. Normative References

1. **MISRA C:2012** — Guidelines for the Use of the C Language in Critical Systems, MISRA Ltd, 2012 (including Amendment 1:2016 and MISRA C:2023).
2. **CERT C Coding Standard** — SEI CERT C Coding Standard, Carnegie Mellon SEI, 2nd edition, 2016.
3. **Barr-C:2018** — Embedded C Coding Standard, Barr Group, v2.0, 2018.
4. **ASPICE v4.0** — Automotive SPICE Process Assessment/Reference Model, VDA QMC, 2023.
5. **ISO/IEC 9899:2011 (C11)** — Programming languages — C.
6. **ISO 26262-6:2018** — Functional safety — Software level.
7. **IEC 61508-3:2010** — Functional safety — Software requirements.
8. **NASA Power of Ten** — Power of Ten: Rules for Developing Safety-Critical Code, G. Holzmann, JPL, 2006.
9. **JSF AV C++ Coding Standards** — Joint Strike Fighter Air Vehicle, Rev. C, 2005.

---

## 4. ASPICE Compliance Notes

| ASPICE v4 Process Area | Base Practice | How This Document Contributes |
|---|---|---|
| SWE.3 Software Detailed Design and Unit Construction | BP5 — Implement software units | Rules in this standard govern unit construction |
| SWE.3 | BP6 — Apply coding guidelines | This document IS the coding guidelines for SWE.3 BP6 |
| SWE.4 Software Unit Verification | BP1 — Develop unit verification specification | Rules map to verifiable criteria (Section 71) |
| SWE.4 | BP2 — Conduct static verification | cstylecheck and static analysis enforce a subset of rules |
| SWE.5 Software Integration and Integration Test | BP3 — Agree interface | Interface/linkage rules (Sections 31, 44) |
| SUP.1 Quality Assurance | BP3 — Assure compliance | Deviation procedure (Section 72), review checklist (Section 70) |
| SUP.8 Configuration Management | BP1 — Identify CIs | This document is version-controlled |
| SUP.9 Problem Resolution | BP1 — Record problems | Violation reports feed into problem resolution |
| GP 2.1.1 | Define the process | This document defines the coding process |
| GP 2.1.3 | Monitor and control | CI enforcement via cstylecheck and static analysis |
| GP 2.2.1 | Define responsibility | Section 5 |
| GP 2.3.1 | Identify information items | Document ID, version, status tracked in CM |

---

## 5. Roles and Responsibilities

| Role | Holder | Responsibility |
|---|---|---|
| Project lead | Dermot Murphy | Owns this document; approves changes and deviations |
| Author / implementer | Claude | Writes C conforming to it; raises a deviation request where a rule cannot be met |
| Reviewer | Dermot Murphy | Checks conformance at review, using the checklist in TB-TMPL-001 §6.5 |
| Quality assurance | Dermot Murphy | TB-SUP1-001 — watches that the CI check stays enforcing and that the deviation register is maintained |
| Configuration management | Dermot Murphy | TB-SUP8-001 — version history and baselines |

TestBench has one human team member holding every one of these roles, and an
author that is a model. Both facts are recorded as deviations rather than
implied away: TB-DEV-001 and TB-DEV-002.

---

## 6. Rule Classification System

Rules in this standard are classified using the MISRA C model:

| Class | Description |
|---|---|
| **Mandatory** | Shall be complied with in all cases. No deviation is possible. |
| **Required** | Shall be complied with. Deviations are permitted only with formal approval (Section 72). |
| **Advisory** | Should be complied with. Project may choose not to follow with documented rationale. |

Each rule is also tagged with its source standard:
- `[MISRA n.n]` — MISRA C:2012 rule number
- `[CERT Xxx]` — CERT C rule identifier
- `[BARR n.n]` — Barr-C:2018 section reference
- `[JPL n]` — NASA Power of Ten rule number
- `[JSF nnn]` — JSF AV C++ Coding Standard rule number

---

## 7. Compiler and Toolchain Requirements

### 7.1 C Language Standard

Source shall be compiled as **C11** or a GNU dialect of it. `[MISRA 1.1]`

> **Current state.** `firmware/nordic_dongle/Makefile` sets no `-std` flag, so
> the toolchain default applies. This is recorded rather than papered over: the
> flag should be set explicitly so that a toolchain upgrade cannot silently
> change the language the firmware is compiled as.

### 7.2 Warning Level

Compilation shall treat warnings as errors. The firmware build sets
`-Wall -Werror`; `-Wextra` is not yet enabled, and enabling it is the natural
next step for this rule. `[MISRA 1.1]`

### 7.3 Toolchain

| Item | Value |
|---|---|
| Compiler | GNU Arm Embedded, version pinned in `.github/workflows/firmware.yml` |
| Target | Cortex-M4F — `-mcpu=cortex-m4 -mthumb -mabi=aapcs -mfloat-abi=hard -mfpu=fpv4-sp-d16` |
| Platform | nRF5 SDK 17.1.0, S140 SoftDevice 7.2.0, board PCA10059 |
| Packaging | `nrfutil` 6.1.7 (TB-ACQ4-001 §4.3) |

Flash and RAM usage are recorded by every CI firmware build (TB-SYS2-091). A
change that moves them is visible in the build log rather than discovered when
an image stops fitting.

### 7.4 Static Analysis

CStyleCheck runs on every push against `firmware/nordic_dongle`, against
`.cstylecheck-baseline.json`, and against the firmware's host unit tests in a
separate step with no baseline that fails on any finding
(`.github/workflows/style.yml`). The test step's module aliases
(`.cstylecheck-dongle-tests-aliases.txt`) and its narrow, justified exclusions
(`.cstylecheck-dongle-tests-exclusions.yml`) apply to that step only. It enforces the mechanically checkable subset
of this standard and of TB-STY-001; the rest is enforced at review
(TB-TMPL-001 §6.5).

Additional analysers — clang-tidy with CERT/MISRA checks, PC-lint Plus,
Polyspace, LDRA — may be run, and their findings are treated as findings
against this standard.

### 7.5 Compiler Qualification

**Not applicable.** ISO 26262-8 tool qualification applies to a compiler
building safety-related delivered software. TestBench is a test tool, carries
no ASIL classification and ships in no product (TB-SYS2-102). The compiler
version is nonetheless pinned and recorded (TB-SVD-001), because a measurement
must be reproducible even when a safety argument is not required.

### 7.6 Compiler Diagnostic Pragmas

Suppression of a compiler warning by pragma or attribute shall be:

- limited to the smallest scope that works;
- accompanied by a comment saying why;
- reviewed at code review, and recorded as a deviation under §72 where it
  suppresses a rule of this standard.

---

## 8. Language Subset — Permitted C Features

The following C features are explicitly permitted:

- Fixed-width integer types from `<stdint.h>` and `<stdbool.h>`.
- Standard control flow: `if`, `else`, `for`, `while`, `do`–`while`, `switch`.
- Structs, unions, enums, and typedefs.
- File-scope and block-scope variables with explicit storage class.
- `const`-qualified objects.
- `volatile`-qualified objects (with the restrictions of Section 22).
- `static` functions and variables.
- `extern` declarations.
- Function pointers (with the restrictions of Section 29.6).
- Designated initialisers (C99+).
- Compound literals (C99+) — with restrictions noted in Section 42.
- `_Bool` / `bool` (C99+ via `<stdbool.h>`).
- `restrict` keyword for pointer parameters (C99+) — use with care.

---

## 9. Language Subset — Prohibited C Features

The following C features are prohibited in production code. `[MISRA 1.1, MISRA 1.2, BARR 1.1]`

| Feature | Reason | Rule Reference |
|---|---|---|
| `goto` | Unstructured control flow; see Section 24 for the single permitted exception | MISRA 15.1 |
| `setjmp` / `longjmp` | Bypasses destructors and stack unwinding | MISRA 21.4 |
| Recursion | Stack depth unpredictable; see Section 25 | MISRA 17.2, JPL 1 |
| Dynamic memory allocation (`malloc`, `calloc`, `realloc`, `free`) | Heap fragmentation and non-determinism; see Section 20 | MISRA 21.3, JPL 3 |
| Variable-length arrays (VLAs) | Stack overflow risk; size not deterministic at compile time | MISRA 18.8 |
| `union` overlapping members for type punning | Undefined behaviour; use `memcpy` instead | MISRA 19.2 |
| Flexible array members (C99 `struct s { int a[]; }`) | Allocation complexity | — |
| Trigraphs | Silent character substitution | MISRA 4.2 |
| Octal literals (e.g. `010`) | Misread as decimal | MISRA 7.1 |
| `register` storage class | Ignored by modern compilers; misleading | Advisory |
| `_Complex`, `_Imaginary` | No embedded use; UB risk | — |
| Thread-local storage (`_Thread_local`) | Use RTOS task-local storage instead | — |
| `asm` / `__asm` inline assembly in C functions | Use separate `.s` files or compiler intrinsics | Advisory |
| `#pragma` without justification comment | Undocumented side effects | — |
| `//` comments in C89/C90 mode | Language standard restriction | MISRA 3.1 |

---

## 10. Data Types and Type Safety

### 10.1 Fixed-Width Integer Types

All integer variables shall use fixed-width types from `<stdint.h>` in preference to basic types:

| Preferred | Instead of |
|---|---|
| `int8_t`, `uint8_t` | `char`, `unsigned char` |
| `int16_t`, `uint16_t` | `short`, `unsigned short` |
| `int32_t`, `uint32_t` | `int`, `unsigned int`, `long` |
| `int64_t`, `uint64_t` | `long long` |

`[MISRA 4.6, BARR 2.1]`

Exceptions:
- `bool` (from `<stdbool.h>`) for boolean values.
- `size_t` for sizes and counts returned by `sizeof` and string functions.
- `ptrdiff_t` for pointer differences.
- `char` when handling character data passed to standard library string functions.

### 10.2 Plain `char` Signedness

The signedness of plain `char` is implementation-defined. `[MISRA 10.4]`

- When `char` is used (for string data), do not assume it is signed or unsigned.
- For numeric data, always use `int8_t` or `uint8_t` explicitly.

`[RULE: sign_compatibility.plain_char_is_signed]`

### 10.3 Signedness Selection

Use **unsigned** types for: bit masks, register values, buffer indices, sizes, and quantities that cannot be negative.

Use **signed** types for: differences, offsets, error codes that may be negative, and values from external interfaces using signed representation.

### 10.4 The Essential Type Model

When mixing types in expressions, follow the MISRA C:2012 Essential Type Model: `[MISRA 10.x]`

- Do not mix signed and unsigned types in binary expressions without an explicit cast.
- Do not compare signed and unsigned values.
- Do not assign a wider type to a narrower type without an explicit cast and range check.

---

## 11. Integer Types — Selection and Use

### 11.1 Unsigned Literals for Unsigned Contexts

Unsigned integer constants shall carry a `U` suffix when assigned to unsigned types or used in unsigned arithmetic. `[MISRA 7.2, BARR 7.3]` `[RULE: misc.unsigned_suffix]`

### 11.2 Integer Suffix Uppercase

Integer literal suffixes shall use uppercase letters. The lowercase `l` is forbidden because it is visually indistinguishable from `1`. `[MISRA 7.3]` `[RULE: misc.lowercase_l_suffix]`

### 11.3 No Octal Literals

Octal integer literals are forbidden. `[MISRA 7.1]` `[RULE: misc.octal_constant]`

### 11.4 Hexadecimal Digits

Hexadecimal digits `A`–`F` shall be uppercase: `0xDEADBEEFU`.

### 11.5 Type Size Assumptions

Code shall not assume a specific size for `int`, `long`, or pointer types. Use fixed-width types or `sizeof()` for size-dependent logic. `[MISRA 4.6]`

---

## 12. Integer Arithmetic and Overflow

### 12.1 Signed Integer Overflow

Signed integer overflow is **undefined behaviour** in C. Code shall not depend on wraparound of signed integers. `[CERT INT32-C]`

Protect against overflow before arithmetic operations:

```c
/* Check before adding */
if (a <= (INT32_MAX - b))
{
    result = a + b;
}
else
{
    /* handle overflow */
}
```

### 12.2 Unsigned Integer Wraparound

Unsigned integer wraparound is well-defined (modular arithmetic) but often unintentional. Validate inputs to prevent unintended wrap:

```c
/* Guard underflow before unsigned subtraction */
if (b <= a)
{
    diff = a - b;
}
```

### 12.3 Division and Modulo

Check for division by zero before all `/` and `%` operations. `[CERT INT33-C]`

### 12.4 Shift Operations

- Left-shift on signed integers is undefined behaviour for values that overflow. Use unsigned types for shift operations. `[MISRA 12.2]`
- Shift amounts shall not be negative or greater than or equal to the bit width of the type. `[MISRA 12.2, CERT INT34-C]`

### 12.5 Mixed-Sign Arithmetic

Do not mix signed and unsigned operands in arithmetic or comparison expressions without explicit cast and documented justification. `[MISRA 10.4]`

---

## 13. Implicit and Explicit Type Conversions

### 13.1 No Implicit Narrowing

Do not rely on implicit narrowing conversions. An explicit cast shall be used when converting from a wider to a narrower type:

```c
uint32_t val32 = 0x0000FFFFU;
uint16_t val16 = (uint16_t)val32;  /* explicit — truncation intentional */
```

### 13.2 No Implicit Signed/Unsigned Conversion

Implicit conversions between signed and unsigned shall be avoided. Use explicit casts. `[MISRA 10.3]`

### 13.3 Boolean Context

In boolean contexts (`if`, `while`, `for`), operands shall evaluate explicitly to a boolean:

```c
/* Correct */
if (0U != byte_count)

/* Wrong */
if (byte_count)      /* implicit conversion from integer to boolean */
```

`[MISRA 14.4]`

### 13.4 Pointer–Integer Conversions

Conversion between pointer and integer types shall only be used for memory-mapped register access and shall be explicitly documented:

```c
volatile uint32_t *p_reg = (volatile uint32_t *)0x40020000U;  /* GPIOA base */
```

`[MISRA 11.1, MISRA 11.4, CERT INT36-C]`

---

## 14. Pointer Types and Pointer Safety

### 14.1 Pointer Initialisation

All pointers shall be initialised before use — either to a valid address, or to `NULL`:

```c
uint8_t *p_buffer = NULL;
```

### 14.2 NULL Pointer Checks

Pointer parameters that may be `NULL` shall be checked before dereferencing:

```c
if (NULL == p_data)
{
    return UART_STATUS_ERROR;
}
byte = *p_data;
```

`[BARR 2.4, CERT EXP34-C]`

### 14.3 No Pointer Arithmetic on Void Pointers

Arithmetic on `void *` is undefined behaviour. Cast to a typed pointer before arithmetic. `[MISRA 18.2, MISRA 18.3]`

### 14.4 No Function Pointer Casting

Function pointers shall not be cast to or from `void *` or data pointers. `[MISRA 11.1]`

### 14.5 Pointer Aliasing

Do not alias two pointers of incompatible types (strict aliasing rule). Use `memcpy` for type-punning. `[CERT EXP39-C]`

### 14.6 `const` Correctness

Pointers to data that a function does not modify shall be declared `const`:

```c
uart_status_t uart_BufferTransmit(const uint8_t *p_data, uint16_t length);
```

`[BARR 2.3, MISRA 8.13]`

### 14.7 Pointer Prefix

Pointer variable names shall use the `p_` prefix for single indirection and `pp_` for double indirection. `[RULE: variables.pointer_prefix]`

---

## 15. Arrays and Buffer Safety

### 15.1 Bounds Checking

Array accesses shall be bounds-checked before use:

```c
if (idx < ARRAY_SIZE)
{
    val = array[idx];
}
```

`[CERT ARR30-C]`

### 15.2 No Variable-Length Arrays

Variable-length arrays (VLAs) are prohibited. Use fixed-size arrays or dynamic allocation (when permitted). `[MISRA 18.8]`

### 15.3 Buffer Overflow Prevention

Functions that write to buffers shall always accept and respect a length parameter. Functions that read from null-terminated strings shall always specify a maximum length. `[CERT STR31-C, STR32-C]`

### 15.4 Array Size via `sizeof`

The number of elements in an array shall be computed with:

```c
#define ARRAY_SIZE(a)   (sizeof(a) / sizeof((a)[0]))
```

Do not hardcode array sizes in loop bounds. `[BARR 2.5]`

---

## 16. String Handling

### 16.1 Null Termination

All strings passed to standard library functions shall be null-terminated. `[CERT STR32-C]`

### 16.2 Safe String Functions

The following unsafe functions are prohibited: `strcpy`, `strcat`, `sprintf`, `gets`. Use length-limited alternatives:

| Prohibited | Use instead |
|---|---|
| `strcpy(d, s)` | `strncpy(d, s, n)` + explicit termination |
| `strcat(d, s)` | `strncat(d, s, n)` |
| `sprintf(b, ...)` | `snprintf(b, size, ...)` |
| `gets(b)` | `fgets(b, size, stdin)` |

`[CERT STR31-C, BARR 2.6]`

### 16.3 String Length

String length shall never be assumed. Always use `strlen()` or explicit length tracking.

---

## 17. Boolean Expressions

### 17.1 Use `bool`

Boolean variables shall be of type `bool` (from `<stdbool.h>`):

```c
#include <stdbool.h>
bool b_is_ready = false;
```

`[MISRA 14.4, BARR 2.8]`

### 17.2 Boolean Comparisons

Do not compare `bool` values against `true` or `false` with `==`. Test them directly:

```c
if (b_is_ready)          { /* correct */ }
if (true == b_is_ready)  { /* wrong */ }
```

`[MISRA 14.4]`

### 17.3 Bitwise vs. Logical Operators

Logical operators (`&&`, `||`, `!`) shall be used for boolean conditions.
Bitwise operators (`&`, `|`, `~`, `^`) shall be used only for bitwise manipulation, not for boolean logic.

---

## 18. Bitwise Operations

### 18.1 Unsigned Types for Bit Manipulation

Bitwise operations shall only be applied to **unsigned** types. `[MISRA 12.1, MISRA 10.1]`

### 18.2 Mask and Shift Clarity

Bit masks and shift values shall be named constants:

```c
#define UART_CR1_UE_POS   (0U)
#define UART_CR1_UE_MASK  (1U << UART_CR1_UE_POS)

p_uart->CR1 |= UART_CR1_UE_MASK;
```

### 18.3 Shift Amount

Shift amounts shall be non-negative, less than the bit width of the type, and the shifted expression shall be of unsigned type. `[MISRA 12.2]`

---

## 19. Memory Management — Static Allocation

### 19.1 Static Allocation Preferred

Static and automatic (stack) allocation is strongly preferred over dynamic heap allocation for all embedded firmware. `[JPL 3, BARR 6.1]`

### 19.2 Pre-allocated Pools

Where variable-size data is needed at runtime, use pre-allocated memory pools of fixed-size blocks. Document the maximum pool size and element count.

### 19.3 Compile-Time Sizing

Buffer sizes shall be determined at compile time wherever possible. Use `#define` constants for all buffer dimensions.

---

## 20. Memory Management — Dynamic Allocation

### 20.1 General Policy

Dynamic memory allocation using `malloc`, `calloc`, `realloc`, and `free` is **prohibited** in interrupt context and in any code path on the ASIL/SIL-rated safety path. `[MISRA 21.3, JPL 3]`

### 20.2 Permitted Use

Dynamic allocation is permitted in non-safety-related code (e.g. development tools, logging, host-side utilities) subject to:

- All allocations checked for `NULL` return.
- Every `malloc`/`calloc` has an exactly paired `free`.
- No allocation after system initialisation in RTOS tasks (allocate once at startup).

### 20.3 RTOS Memory

For RTOS heap usage, the project shall configure a fixed total heap size and use RTOS memory allocation APIs (e.g. `pvPortMalloc`/`vPortFree` in FreeRTOS) rather than direct `malloc`. RTOS heap usage shall be verified against maximum by stack and heap analysis.

### 20.4 Memory Leak Prevention

Every allocation shall have exactly one matching deallocation. Use RTOS memory pool objects where deterministic lifecycle is required.

---

## 21. Memory Management — Stack Usage

### 21.1 Stack Size Analysis

The maximum stack depth of every task and ISR shall be estimated at design time and confirmed by worst-case call-graph analysis.

### 21.2 Large Local Variables

Local variables larger than 64 bytes shall be declared at file scope (static) or in a statically allocated block. Avoid large stack-allocated arrays. `[BARR 6.2]`

### 21.3 Stack Monitoring

Production firmware shall include RTOS stack high-water-mark monitoring (e.g. `uxTaskGetStackHighWaterMark`) with an assertion or fault when remaining stack falls below a safety margin.

---

## 22. Memory Management — Volatile and Shared Data

### 22.1 `volatile` for Hardware Registers

All memory-mapped hardware registers shall be accessed through `volatile`-qualified pointers. `[MISRA 11.4, BARR 9.1]`

```c
volatile uint32_t * const p_GPIOA_IDR = (volatile uint32_t *)0x40020010U;
```

### 22.2 `volatile` for ISR-Shared Variables

Variables shared between an ISR and non-ISR code shall be declared `volatile`. `[BARR 9.1, CERT DCL22-C]`

```c
volatile uint32_t uart_g_rx_count = 0U;
```

### 22.3 `volatile` Is Not Atomicity

`volatile` alone does not guarantee atomicity on multi-byte variables or multi-core systems. Use atomic operations or critical sections (Section 52) for shared multi-byte data.

### 22.4 No `volatile` Without Purpose

`volatile` shall not be applied to variables that are not hardware registers, ISR-shared, or used in busy-wait loops. Gratuitous `volatile` inhibits optimisation without benefit.

---

## 23. Control Flow — General

### 23.1 Single Entry, Single Exit (SESE)

Each function shall have a single return point at the end of the function body. `[MISRA 15.5 — Advisory]`

Where multiple return paths would otherwise improve clarity, the return value shall be written to a result variable and returned at the end:

```c
status = uart_CheckParam(p_data, length);
if (UART_STATUS_OK == status)
{
    status = uart_DoTransmit(p_data, length);
}
return status;
```

### 23.2 Nesting Depth

Control flow nesting depth shall not exceed **5 levels**. Functions exceeding this limit shall be decomposed. `[BARR 8.2, JSF 118]`

### 23.3 Unreachable Code

Code that is unreachable under all conditions is forbidden. `[MISRA 2.1]`

Unreachable code introduced by conditional compilation shall be documented with a comment.

### 23.4 Dead Code

Dead code (code that is syntactically present but never executed) shall be removed, not commented out.

---

## 24. Control Flow — `goto`

`goto` is prohibited with one permitted exception: forward `goto` to a single cleanup/error-exit label within the same function. `[MISRA 15.1]`

```c
uart_status_t uart_ComplexOperation(void)
{
    uart_status_t status = UART_STATUS_OK;

    status = uart_StepA();
    if (UART_STATUS_OK != status) { goto cleanup; }

    status = uart_StepB();
    if (UART_STATUS_OK != status) { goto cleanup; }

cleanup:
    uart_ReleaseResources();
    return status;
}
```

Rules for this exception:
- The label name shall be `cleanup` or `error_exit`.
- `goto` shall only jump **forward** (never backward).
- There shall be at most one such label per function.

---

## 25. Control Flow — Recursion

Direct and indirect recursion is **prohibited**. `[MISRA 17.2, JPL 1]`

Stack depth resulting from recursion cannot be statically bounded, making stack overflow analysis impossible.

Where tree or graph traversal would naturally use recursion, implement an iterative algorithm with an explicit, statically allocated stack.

---

## 26. Control Flow — Infinite Loops

Deliberate infinite loops (e.g. the RTOS task main loop or the bare-metal superloop) shall be written with `while (true)` and a comment indicating intent:

```c
while (true)
{
    /* main superloop — intentional infinite loop */
    uart_ProcessEvents();
    can_ProcessMessages();
}
```

A `for (;;)` form is also acceptable. `while (1)` is acceptable but `while (true)` is preferred for clarity.

---

## 27. Control Flow — `break` and `continue`

- `break` is permitted inside `switch` statements and as the sole means of exiting a loop on an error condition.
- `continue` is discouraged; use it only when it materially improves readability and with a comment.
- More than one `break` per loop body requires justification in a comment.

`[MISRA 15.4 — Advisory]`

---

## 28. Control Flow — `switch` Statements

- Every `switch` shall have a `default` clause. `[MISRA 16.4 — Required]`
- Every `case` shall terminate with `break`, `return`, or a `/* fall-through */` comment. Unintentional fall-through is prohibited. `[MISRA 16.3 — Required]`
- `case` values shall be of the same essential type as the `switch` expression. `[MISRA 16.7]`
- An enum `switch` should cover all enumeration values (compiler warning `-Wswitch` will catch omissions).

---

## 29. Functions — Design Rules

### 29.1 Single Responsibility

Each function shall perform one clearly defined task. Functions that perform multiple unrelated tasks shall be decomposed.

### 29.2 Function Length

Each function body shall not exceed **60 lines** (including blank lines and comments within the body). `[JPL 4]` `[RULE: misc.function_length]`

Functions that cannot meet this limit due to a finite state machine or protocol handler require documented justification and a raised limit per the deviation procedure.

### 29.3 Complexity

The cyclomatic complexity of a function shall not exceed **10**. Verify with a static analysis tool.

### 29.4 Side Effects in Expressions

A function called as part of a complex expression shall not produce side effects that affect other sub-expressions. `[MISRA 13.2]`

### 29.5 One Purpose Per Call

Functions shall either perform an action OR return a value — not both. A function that both modifies state and returns a value shall document this dual nature explicitly.

### 29.6 Function Pointers

Function pointers are permitted but shall:
- Point only to functions with compatible prototypes (no void cast).
- Be checked for `NULL` before being called.
- Be named according to the function naming convention.

`[MISRA 11.1]`

---

## 30. Functions — Parameters and Return Values

### 30.1 Parameter Count

Functions shall have no more than **5 parameters**. `[BARR 9.3, JSF 120]` Functions requiring more context should pass a configuration struct.

### 30.2 Output Parameters

When a function needs to return multiple values, output parameters (passed by pointer) shall be used. Output parameters shall be named with a suffix or clearly documented in the Doxygen header.

### 30.3 Return Value Checking

The return value of every function that can return an error status shall be checked by the caller:

```c
status = uart_BufferTransmit(p_data, length);
if (UART_STATUS_OK != status)
{
    /* handle error */
}
```

Ignoring a return value shall be explicit:

```c
(void)uart_FlushBuffer();  /* intentional discard */
```

`[MISRA 17.7, CERT ERR33-C]`

### 30.4 No Pointer Parameters Without NULL Check

Any function receiving a pointer parameter shall check for `NULL` at entry unless the parameter is documented as always non-NULL (with the caller's obligation to guarantee this).

---

## 31. Functions — Prototypes and Declarations

### 31.1 Explicit Prototypes

All functions shall be declared with a full prototype before they are called. `[MISRA 8.2]`

```c
/* Header file */
uart_status_t uart_BufferTransmit(const uint8_t *p_data, uint16_t length);
```

### 31.2 Matching Declaration and Definition

A function's declaration (in the header) and definition (in the `.c` file) shall have identical parameter types and return types. `[MISRA 8.3]`

### 31.3 No Implicit Function Declarations

Calling an undeclared function is prohibited. `[MISRA 17.3]`

`[RULE: misc.declared_not_defined]`

### 31.4 `void` Parameter List

A function that takes no parameters shall be explicitly declared with `void`:

```c
void uart_Init(void);    /* correct */
void uart_Init();         /* wrong — pre-C11 meaning is implementation-defined */
```

`[MISRA 8.2]`

---

## 32. Functions — Inline Functions

- `inline` functions shall only be used for very short functions (3 lines or fewer) where call overhead is measurable.
- `inline` functions shall be defined in header files.
- Inline functions are preferred over function-like macros for type safety. `[BARR 7.5]`

---

## 33. Functions — Recursion

Recursion is prohibited (see Section 25). All functions shall have a statically deterministic call depth.

---

## 34. Functions — Assertions

### 34.1 Assert Density

`[RULE: misc.assert_density]`

Non-trivial functions (≥ 10 lines) shall contain at least one `assert()` call or equivalent defensive check to validate preconditions or invariants. `[JPL 5]`

### 34.2 Project Assert Macro

The project shall define a `PROJ_ASSERT(cond)` macro that:
- In debug builds: calls standard `assert()` or invokes a custom fault handler.
- In release builds: either remains as a null expression or calls a safe-state handler (project decision, documented in the Deviation Register).

```c
#define PROJ_ASSERT(cond)   \
    do {                    \
        if (!(cond))        \
        {                   \
            fault_Handler(); \
        }                   \
    } while (0U)
```

---

## 35. Preprocessor — Conditional Compilation

### 35.1 Feature Flags

Conditional compilation shall be used for:
- Platform/target differences.
- Debug vs. release builds.
- Optional hardware features.

Do not use conditional compilation to maintain multiple incompatible logic paths in the same file. Prefer separate source files.

### 35.2 `#ifdef` vs. `#if defined()`

`#if defined(SYMBOL)` is preferred over `#ifdef SYMBOL` for clarity and consistency with multi-condition tests:

```c
#if defined(UART_DMA_ENABLE) && defined(DMA1_SUPPORTED)
```

### 35.3 Nesting Depth

Conditional compilation nesting shall not exceed 3 levels.

### 35.4 `#else` and `#endif` Comments

Every `#else` and `#endif` shall include a comment referencing the corresponding condition:

```c
#if defined(UART_DMA_ENABLE)
    /* DMA path */
#else
    /* polled path */
#endif /* UART_DMA_ENABLE */
```

---

## 36. Preprocessor — Header Inclusion

### 36.1 Include All Required Headers

Each source file shall include every header that defines types, macros, or functions it uses. Do not rely on transitive inclusion. `[CERT PRE04-C]`

### 36.2 No Cyclic Includes

Header files shall not include each other in a cycle. Break cycles using forward declarations.

### 36.3 System Header Names

Project source files shall not share their base name with any standard C or POSIX header. `[CERT PRE04-C]` `[RULE: misc.reserved_header_name]`

---

## 37. Preprocessor — Macros vs. Functions

### 37.1 Prefer Inline Functions

Where a macro is used purely for performance (to avoid a function call), an `inline` function shall be used instead if the compiler supports inlining. Inline functions provide type safety; macros do not.

### 37.2 Macro Side Effects

Macro arguments shall not have side effects (e.g. `++`, function calls) because they may be evaluated more than once:

```c
#define MAX(a, b)   (((a) > (b)) ? (a) : (b))

int result = MAX(x++, y);  /* WRONG — x incremented twice if x > y initially */
```

### 37.3 Object-Like Macro Constants

Prefer `static const` typed variables over object-like `#define` for typed constants when the value is not needed in a preprocessor expression:

```c
static const uint32_t UART_TIMEOUT_MS = 100U;   /* preferred in C99+ */
#define UART_TIMEOUT_MS   100U                    /* acceptable — both in scope */
```

---

## 38. Preprocessor — Token Pasting and Stringification

`##` (token pasting) and `#` (stringification) shall only be used when necessary for code generation and shall be accompanied by a comment explaining the pattern. `[MISRA 20.10, MISRA 20.11]`

---

## 39. Global Variables

### 39.1 Minimise Global State

Global variables (external linkage) shall be minimised. Prefer passing state through function parameters or using a module-private singleton pattern (file-scope static). `[JPL 6, BARR 8.4]`

### 39.2 Global Variable Declaration

All global variables shall be declared `extern` in the module's public header and defined exactly once in the module's `.c` file.

### 39.3 Global Variable Naming

Global variables shall use the `g_` prefix (after the module prefix): `uart_g_tx_count`. `[RULE: variables.global.g_prefix]`

### 39.4 Const-Qualified Globals

Read-only global data shall be declared `const` to prevent accidental modification and allow placement in read-only flash:

```c
const uint8_t uart_g_PREAMBLE[] = { 0xAAU, 0x55U };
```

---

## 40. File-Scope Static Variables

### 40.1 Prefer Static over Global

Module state that is not needed externally shall use **file-scope static** variables rather than globals:

```c
static uart_state_t uart_s_state = UART_STATE_IDLE;
```

### 40.2 Static Variable Naming

File-scope static variables shall use the `s_` prefix: `uart_s_rx_count`. `[RULE: variables.static.s_prefix]`

### 40.3 Initialisation of Statics

File-scope static variables shall be explicitly initialised. Relying on zero-initialisation by the C runtime is acceptable but should be documented:

```c
static uint32_t uart_s_byte_count = 0U;  /* explicit zero init */
```

---

## 41. Constants — `const` vs. `#define`

| Use case | Preferred form |
|---|---|
| Typed constant within a module | `static const TYPE NAME = value;` |
| Typed constant exported in a header | `extern const TYPE NAME;` (defined in `.c`) |
| Preprocessor-visible constant (e.g. array size in a struct) | `#define NAME valueU` |
| Enum-related constant | `enum` member |

`[BARR 7.2]`

---

## 42. Initialisation

### 42.1 All Variables Initialised Before Use

Every variable shall be initialised before its value is read. `[CERT EXP33-C, MISRA 9.1]`

```c
uart_status_t status = UART_STATUS_OK;
uint8_t byte = 0U;
```

### 42.2 Struct Initialisation

Structs shall be initialised using designated initialisers to avoid silent padding-byte issues and to improve readability:

```c
UART_CONFIG_T config =
{
    .baud_rate = 115200U,
    .data_bits = 8U,
    .stop_bits = 1U,
    .parity    = UART_PARITY_NONE
};
```

### 42.3 No Partial Initialisation

Do not leave structure or array members un-initialised. If a member is intentionally unused, assign it a zero or default value with a comment.

---

## 43. Scope and Lifetime

### 43.1 Minimise Scope

Variables shall be declared at the narrowest applicable scope. Declare inside `for` loop initialisers when the variable is only needed in the loop:

```c
for (uint8_t i = 0U; i < count; i++) { ... }
```

### 43.2 Block Scope Declarations

In C99+, block-scope declarations may appear anywhere before first use within the block. However, for readability in embedded code, declarations shall appear at the top of the function body unless there is a strong reason to declare at point of use.

---

## 44. Linkage

### 44.1 Internal Linkage

Functions and variables not referenced outside their translation unit shall be declared `static`:

```c
static void prv_uart_FifoFlush(void);
static uint32_t uart_s_error_count = 0U;
```

`[MISRA 8.7, BARR 9.2]`

### 44.2 No Implicit Linkage

Do not rely on default (external) linkage for identifiers that should be private. Explicitly `static` all file-scope identifiers that are not part of the public API.

### 44.3 One Definition Rule

Every non-inline function and every non-`static` object shall have exactly one definition across all translation units. `[MISRA 8.6]`

---

## 45. Structures and Unions

### 45.1 Struct Padding

Be aware that the compiler may insert padding bytes between struct members for alignment. For safety-critical serialisation or memory-mapped registers:
- Use explicit padding members.
- Verify struct sizes with `_Static_assert`.
- Use compiler-specific packing attributes only when necessary, with a comment.

### 45.2 Union Restrictions

Unions shall not be used to reinterpret the bytes of one type as another (type punning), as this is undefined behaviour in C. `[MISRA 19.2]`

Use `memcpy` for type-safe byte reinterpretation.

### 45.3 `_Static_assert` for Struct Sizes

For all structs that are serialised, memory-mapped, or exchanged over a communication protocol, a `_Static_assert` shall verify the expected size:

```c
_Static_assert(sizeof(CAN_FRAME_T) == 13U, "CAN_FRAME_T size mismatch");
```

---

## 46. Bit Fields

Bit fields shall only be used with `unsigned int` or `_Bool` base types. `[MISRA 6.1]`

The layout of bit fields in memory is implementation-defined. Do not use bit fields for memory-mapped hardware registers; use masks and shifts instead. `[MISRA 6.1, BARR 2.10]`

---

## 47. Enumerations

### 47.1 Enums for Related Constants

Use `enum` (not `#define`) for groups of related integer constants. `[BARR 7.2]`

### 47.2 Enum Values

The first member shall be explicitly assigned `0`. All members should be explicitly assigned. `[BARR 2.9]`

### 47.3 Enum as Return Type

Prefer returning an enum type rather than a raw integer for status/error codes:

```c
uart_status_t uart_ByteTransmit(uint8_t byte);
```

### 47.4 Enum Size

Do not assume the size of an enum type. Use `_Static_assert` or a fixed-width integer cast when size matters.

---

## 48. Standard Library Usage

### 48.1 Permitted Headers

The following standard library headers are generally permitted in embedded projects:

| Header | Use |
|---|---|
| `<stdint.h>` | Fixed-width integer types |
| `<stdbool.h>` | Boolean type |
| `<stddef.h>` | `NULL`, `size_t`, `offsetof` |
| `<stdarg.h>` | Variable argument lists (logging only) |
| `<string.h>` | `memcpy`, `memset`, `memcmp` (see Section 49 for unsafe functions) |
| `<assert.h>` | `assert()` (debug builds only in strict SIL environments) |
| `<limits.h>` | Integer limits |
| `<math.h>` | Floating-point (see Section 62) |

### 48.2 Restricted Headers

The following headers require documented justification:

| Header | Risk | Condition for Use |
|---|---|---|
| `<stdio.h>` | File I/O; `printf` can block | Allowed in debug/logging only |
| `<stdlib.h>` | `malloc`/`free`/`exit`/`abort` | Only `abs`, `div`, `strtol` permitted; no heap functions |
| `<time.h>` | Portability; timer resolution varies | Allowed with documented HAL wrapper |
| `<errno.h>` | Thread-safety of `errno` varies | Allowed; check toolchain thread-safety |
| `<setjmp.h>` | Bypasses stack unwinding | **Prohibited** |

---

## 49. Restricted Standard Library Functions

The following functions are prohibited or restricted:

| Function | Status | Alternative |
|---|---|---|
| `malloc`, `calloc`, `realloc`, `free` | Prohibited on safety path | Static allocation; RTOS pools |
| `gets` | Prohibited | `fgets` |
| `strcpy` | Prohibited | `strncpy` + explicit termination |
| `strcat` | Prohibited | `strncat` |
| `sprintf` | Prohibited | `snprintf` |
| `scanf` | Prohibited | Explicit parsing |
| `atoi`, `atof`, `atol` | Prohibited (no error detection) | `strtol`, `strtof`, `strtod` |
| `strtok` | Prohibited (not reentrant) | `strtok_r` (POSIX) or custom |
| `rand`, `srand` | Restricted | Use a qualified PRNG for safety use |
| `exit`, `abort` | Restricted | Only in fault handler; never in normal flow |
| `assert()` | Restricted | Use `PROJ_ASSERT()` macro |
| `setjmp`, `longjmp` | Prohibited | — |

`[MISRA 21.x, CERT STR31-C, CERT ERR04-C]`

---

## 50. Concurrency — Interrupt Safety

### 50.1 Critical Section Protection

Shared data accessed from both interrupt and non-interrupt context shall be protected by a critical section (disable/enable interrupts):

```c
taskENTER_CRITICAL();
uart_g_rx_count++;
taskEXIT_CRITICAL();
```

### 50.2 Critical Section Length

Critical sections shall be as short as possible — only the minimum code necessary to access shared data. Long critical sections degrade interrupt latency.

### 50.3 No Blocking in ISR

ISR functions shall never block, call RTOS APIs that may block, or call `malloc`/`free`.

### 50.4 No `printf` in ISR

`printf` and all standard I/O functions are prohibited inside ISRs due to their non-reentrant nature and potential to block.

---

## 51. Concurrency — RTOS Task Safety

### 51.1 Mutex Protection for Shared Resources

Resources shared between RTOS tasks shall be protected by a mutex or semaphore:

```c
osMutexAcquire(h_uart_mutex, osWaitForever);
uart_BufferTransmit(p_data, length);
osMutexRelease(h_uart_mutex);
```

### 51.2 Deadlock Prevention

Mutex acquisition order shall be documented and consistent across all tasks to prevent deadlock. A task shall not hold more than one mutex at a time (except where a documented hierarchical locking order is established).

### 51.3 Priority Inversion

Use priority-inheritance mutexes or priority-ceiling mutexes where priority inversion could cause timing violations.

---

## 52. Concurrency — Atomic Access

### 52.1 Atomic Types

For single-variable flags shared between tasks or between task and ISR, use `volatile` with appropriate critical-section protection (Section 50), or `_Atomic` (C11) where the toolchain supports it.

### 52.2 Multi-Byte Atomicity

Reading or writing a multi-byte variable (e.g. `uint32_t` on an 8-bit MCU) may require multiple bus cycles and is not inherently atomic. Protect with critical sections.

---

## 53. Error Handling — Strategy

### 53.1 No Silent Failure

Functions shall not silently ignore errors. Every detectable error condition shall:
1. Return an error status code to the caller, OR
2. Invoke a registered error callback, OR
3. Transition the system to a defined safe state.

`[BARR 8.5, CERT ERR00-C]`

### 53.2 Error Propagation

Errors shall propagate up the call stack until a layer that can meaningfully handle them. Intermediate layers shall pass error codes upward, not mask them.

---

## 54. Error Handling — Return Codes

### 54.1 Module-Specific Status Enum

Each module shall define its own status enumeration:

```c
typedef enum uart_status_t
{
    UART_STATUS_OK      = 0,
    UART_STATUS_ERROR   = 1,
    UART_STATUS_TIMEOUT = 2,
    UART_STATUS_BUSY    = 3
} uart_status_t;
```

### 54.2 Return Code Checking

All return values that encode error status shall be checked. Explicit discard via `(void)` cast is required when a return value is intentionally ignored. `[MISRA 17.7]`

---

## 55. Error Handling — Assertions

`assert()`-style checks validate programmer assumptions and preconditions — they are not user-input validation.

In safety-critical software, the response to a failed assertion shall be a controlled shutdown or safe-state entry, not merely an abort. See Section 34.2 for the `PROJ_ASSERT` macro.

---

## 56. Error Handling — Safe State and Fail-Safe Behaviour

### 56.1 Defined Safe States

For each module with actuator or safety-relevant output, a safe state shall be defined and documented. The safe state shall be achievable from any error condition.

### 56.2 Hardware Watchdog

All production firmware shall configure and periodically service the hardware watchdog. The watchdog shall NOT be serviced from within an ISR. `[ISO 26262-6]`

### 56.3 Fault Handler

An unrecoverable fault (failed assertion, stack overflow detected, hardware fault) shall invoke a dedicated `fault_Handler()` that:
1. Disables all actuator outputs.
2. Enters the safe state.
3. Logs a fault record if non-volatile storage is available.
4. Either resets the system or halts (project policy decision, documented).

---

## 57. Hardware Abstraction

### 57.1 HAL Layer

All direct hardware register access shall be confined to a Hardware Abstraction Layer (HAL). Code above the HAL layer shall not access hardware registers directly.

### 57.2 Port Abstraction

Hardware-specific definitions (pin numbers, register base addresses, IRQ numbers) shall be isolated in a single port-configuration header (`<project>_port.h` or equivalent).

### 57.3 HAL Interface Contracts

HAL functions shall have clearly documented preconditions, postconditions, and side effects.

---

## 58. Register Access

Memory-mapped hardware registers shall only be accessed through:
- `volatile`-qualified pointers, OR
- Compiler-specific intrinsics for atomic register read-modify-write.

Never access hardware registers through un-qualified pointers; the compiler may optimise the access away.

```c
#define GPIOA_ODR   (*((volatile uint32_t *)0x40020014U))

GPIOA_ODR |= (1U << 5U);  /* set pin 5 */
```

---

## 59. Interrupt Service Routines

### 59.1 ISR Design

ISRs shall:
- Be as short as possible.
- Post data to a queue/buffer and signal a task for processing.
- Not call blocking RTOS APIs.
- Not perform complex computation.
- Not use `printf` or any buffered I/O.

### 59.2 ISR Naming

ISRs shall use the `_IRQHandler` suffix per CMSIS convention. `[RULE: functions.isr_suffix]`

### 59.3 ISR Re-entrancy

ISRs are not re-entrant by default on ARM Cortex-M. If nested interrupts are enabled, ISR shared data access shall be protected accordingly.

### 59.4 ISR Latency Budget

The maximum execution time of each ISR shall be documented and verified against the interrupt latency budget.

---

## 60. Watchdog

The hardware watchdog shall be:
- Configured with a documented timeout period.
- Serviced from the main task or a dedicated watchdog task.
- Not serviced if any task heartbeat is missed (allow reset on deadlock).

The watchdog timeout shall be documented in the System Safety Architecture.

---

## 61. Timing and Delays

### 61.1 No Blocking Busy-Waits

Blocking busy-waits (`while (x != y) {}`) are prohibited in task context except where the wait duration is strictly bounded and documented with its maximum bound.

### 61.2 RTOS Delays

Task delays shall use RTOS-provided delay functions (`osDelay`, `vTaskDelay`) rather than spin-wait loops.

### 61.3 Timeout on All Blocking Operations

Every RTOS blocking call (queue receive, mutex take, semaphore take) shall have a finite timeout. `osWaitForever` is permitted only where deadlock is provably impossible and documented.

### 61.4 Timestamp Types

Timestamps shall use `uint32_t` tick counts or a project-defined `TICK_T` typedef. Timestamp overflow and rollover shall be handled explicitly using subtraction (not comparison):

```c
uint32_t elapsed = current_tick - start_tick;  /* correct — wraps safely */
if (current_tick > (start_tick + timeout))     /* WRONG — overflows */
```

---

## 62. Floating-Point Arithmetic

### 62.1 Floating-Point Use

Floating-point arithmetic shall only be used where no fixed-point alternative exists. On MCUs without a hardware FPU, floating-point operations are slow and shall be minimised.

### 62.2 NaN and Infinity Handling

Code using floating-point shall check for and handle `NaN` and `Inf` conditions. Do not compare floating-point values for exact equality:

```c
/* Wrong */
if (temperature == 0.0F)

/* Correct */
if (fabsf(temperature) < 1.0E-6F)
```

### 62.3 Floating-Point Type Selection

Use `float` (single precision) unless `double` precision is explicitly required. On most embedded MCUs, `double` is emulated and significantly slower.

---

## 63. Portability

### 63.1 Architecture Assumptions

Code shall not assume:
- Specific size of `int`, `long`, or pointer.
- Specific byte order (endianness) unless explicitly isolated in a HAL function.
- Specific alignment requirements without `_Static_assert` verification.

`[MISRA 4.6, CERT INT13-C]`

### 63.2 Endianness

Code that serialises or deserialises multi-byte values shall explicitly handle byte order using documented conversion macros:

```c
#define UINT32_TO_BE(x)   \
    ((((x) & 0xFF000000U) >> 24U) | \
     (((x) & 0x00FF0000U) >>  8U) | \
     (((x) & 0x0000FF00U) <<  8U) | \
     (((x) & 0x000000FFU) << 24U))
```

### 63.3 Compiler Extensions

Compiler-specific extensions (`__attribute__`, `#pragma`, intrinsics) shall be:
- Isolated in a HAL or utility header.
- Guarded by a `#if defined(__GNUC__)` or equivalent check.
- Accompanied by a fallback definition for portable builds.

---

## 64. Undefined, Unspecified, and Implementation-Defined Behaviour

Code shall not exhibit undefined behaviour (UB). `[MISRA Underpinning Principle]`

Common sources of UB to avoid:

| Source | Rule | Mitigation |
|---|---|---|
| Signed integer overflow | CERT INT32-C | Range-check before arithmetic |
| Shift by negative or ≥ width | MISRA 12.2 | Assert shift amount |
| NULL pointer dereference | CERT EXP34-C | NULL check before dereference |
| Out-of-bounds array access | CERT ARR30-C | Bounds check |
| Use of uninitialised variable | CERT EXP33-C, MISRA 9.1 | Always initialise |
| Modifying `const` data via pointer | MISRA 11.3 | `const`-correct code |
| Strict aliasing violation | CERT EXP39-C | Use `memcpy` for type punning |
| Sequence point violations | MISRA 13.2 | One side effect per expression |
| Modifying `volatile` without memory barrier | — | Use appropriate memory barriers |

---

## 65. MISRA C:2012 Compliance Mapping

> **Placeholder:** A complete cross-reference table mapping each MISRA C:2012 Required and Advisory rule to the corresponding section of this standard, and its enforcement status (automated / manual / deviation) will be inserted here during the rule population phase.

Key MISRA rules directly addressed by this standard:

| MISRA Rule | Category | Section |
|---|---|---|
| 1.1 | Required | 7, 8, 9 |
| 2.1 | Required | 23.3 |
| 4.2 | Required (2023) | 9 |
| 5.x | Required | 15–26 (Style Guide) |
| 7.1 | Required | 11.3 |
| 7.2 | Required | 11.1 |
| 7.3 | Required | 11.2 |
| 8.2 | Required | 31.1 |
| 8.3 | Required | 31.2 |
| 8.6 | Required | 44.3 |
| 8.7 | Advisory | 44.1 |
| 8.13 | Advisory | 14.6 |
| 9.1 | Mandatory | 42.1 |
| 10.1–10.8 | Required | 10.4, 12.5, 13.1–13.4 |
| 11.1 | Required | 14.4, 29.6 |
| 11.3 | Required | 64 |
| 11.4 | Advisory | 13.4, 22.1 |
| 12.1 | Advisory | 18.1 |
| 12.2 | Required | 12.4, 18.3 |
| 13.2 | Required | 29.4 |
| 14.4 | Required | 17.1, 17.2, 13.3 |
| 15.1 | Advisory | 24 |
| 15.2 | Required | 24 |
| 15.4 | Advisory | 27 |
| 15.5 | Advisory | 23.1 |
| 16.3 | Required | 28 |
| 16.4 | Required | 28 |
| 17.2 | Required | 25, 33 |
| 17.3 | Mandatory | 31.3 |
| 17.7 | Required | 30.3, 54.2 |
| 18.2 | Required | 14.3 |
| 18.3 | Required | 14.3 |
| 18.8 | Required | 15.2 |
| 19.2 | Advisory | 45.2 |
| 20.7 | Required | Style Guide §37.2 |
| 20.10 | Advisory | 38 |
| 20.11 | Advisory | 38 |
| 21.3 | Required | 20.1 |
| 21.4 | Required | 9 |

---

## 66. CERT C Compliance Mapping

> **Placeholder:** A complete cross-reference table mapping CERT C rules to sections of this standard will be inserted during the rule population phase.

Key CERT C rules addressed:

| CERT Rule | Title | Section |
|---|---|---|
| DCL22-C | Use volatile for data accessible in multiple contexts | 22.2 |
| EXP33-C | Do not read uninitialized memory | 42.1 |
| EXP34-C | Do not dereference null pointers | 14.2, 30.4 |
| EXP39-C | Do not access a variable through a pointer of incompatible type | 14.5 |
| INT32-C | Ensure signed integer operations do not overflow | 12.1 |
| INT33-C | Ensure division and modulo do not divide by zero | 12.3 |
| INT34-C | Do not shift an expression by a negative amount or by ≥ width | 12.4 |
| INT36-C | Converting a pointer to integer or integer to pointer | 13.4 |
| ARR30-C | Do not form or use out-of-bounds pointers | 15.1 |
| STR31-C | Guarantee that storage for strings has sufficient space | 15.3 |
| STR32-C | Do not pass a non-null-terminated character sequence | 16.1 |
| ERR00-C | Adopt and implement a consistent and comprehensive error-handling policy | 53 |
| ERR33-C | Detect and handle standard library errors | 30.3 |
| PRE10-C | Wrap multistatement macros in a do-while loop | Style Guide §37.3 |
| PRE11-C | Do not conclude a single statement object-like macro definition with a semicolon | Style Guide §37.4 |

---

## 67. Sign Compatibility

`[RULE: sign_compatibility]`

The cstylecheck sign-compatibility checker validates that unsigned literals are not passed to signed parameters and vice versa, based on function prototypes found in header files.

The project setting `plain_char_is_signed = true` is the default. Change this if the toolchain defaults to unsigned `char`.

---

## 68. Declared-But-Not-Defined Identifiers

`[RULE: misc.declared_not_defined]`

Functions and variables declared `extern` but never defined in any scanned translation unit are flagged. This catches missing BSP stubs and forward-declaration mismatches.

Symbols intentionally left undefined (e.g. HAL stubs to be linked from a library) may be suppressed with:

```c
extern void HAL_UART_Init(void);  /* cstylecheck: disable misc.declared_not_defined */
```

---

## 69. Static Analysis Tools

### 69.1 cstylecheck

The cstylecheck tool (this repository) enforces naming conventions, macro rules, literal formatting, line metrics, and a growing set of MISRA/CERT rules. It shall be run in CI on every pull request with zero new violations allowed.

Configuration: `src/rules.yml`

### 69.2 Complementary Tools

For full MISRA compliance, complement cstylecheck with one of:
- **PC-lint Plus** (MISRA C:2012 / CERT C profiles)
- **Polyspace Code Prover** (formal verification + MISRA)
- **LDRA TBvision** (MISRA, DO-178C)
- **Parasoft C/C++test** (MISRA, CERT, AUTOSAR)
- **Clang-tidy** (cert-* checks, bugprone-*, concurrency-*)

### 69.3 Static Analysis in CI

Static analysis shall run on every PR branch. The maximum permitted violation count is defined in the project Quality Plan. A ratcheting policy (violations may not increase) shall be enforced.

---

## 70. Code Review for Standards Compliance

The following checklist shall be used during code review to verify coding standard compliance for items not covered by automated tools.

**Design and Architecture:**
- [ ] Function performs a single, well-defined task (Section 29.1).
- [ ] No global state where file-scope static suffices (Section 39.1).
- [ ] Error return codes checked at all call sites (Section 30.3).
- [ ] No silent error swallowing (Section 53.1).

**Type Safety:**
- [ ] Fixed-width types used throughout (Section 10.1).
- [ ] No mixed signed/unsigned arithmetic without explicit cast (Section 12.5).
- [ ] All pointer parameters NULL-checked (Section 14.2, 30.4).
- [ ] `const` applied to pointers not modified (Section 14.6).

**Memory:**
- [ ] No VLAs (Section 15.2).
- [ ] No dynamic allocation on safety path (Section 20.1).
- [ ] All variables initialised before use (Section 42.1).
- [ ] ISR-shared variables declared `volatile` (Section 22.2).

**Concurrency:**
- [ ] Shared data protected by critical section or mutex (Sections 50, 51).
- [ ] No blocking calls in ISRs (Section 50.3).
- [ ] All blocking RTOS calls have finite timeout (Section 61.3).

**Control Flow:**
- [ ] No recursion (Section 25).
- [ ] No `goto` except forward-to-cleanup (Section 24).
- [ ] All `switch` statements have `default` (Section 28).
- [ ] All fall-throughs commented (Section 28).

**Hardware:**
- [ ] Hardware registers accessed only through `volatile` pointers (Section 58).
- [ ] Watchdog serviced correctly (Section 60).

---

## 71. Unit Verification Criteria

For ASPICE SWE.4 (Software Unit Verification), each unit shall satisfy:

| Criterion | Verification Method | Pass Condition |
|---|---|---|
| Zero cstylecheck errors | CI automated | No `error`-severity violations |
| Zero cstylecheck warnings | CI automated | No new `warning`-severity violations (ratchet policy) |
| MISRA compliance | Static analysis tool | No unapproved deviations |
| No uninitialised variable warnings | Compiler (`-Wall -Wextra`) | Zero warnings with warnings-as-errors |
| Cyclomatic complexity ≤ 10 | Static analysis | All functions pass |
| Function length ≤ 60 lines | cstylecheck | Zero violations |
| Code review checklist complete | Peer review | Reviewer approval |
| Unit tests pass with ≥ 80 % branch coverage | Unit test suite | Coverage report |

---

## 72. Deviation Procedure

### 72.1 When a Deviation Is Needed

A deviation is required when:
- A Required or Mandatory rule cannot be complied with for technical reasons.
- Third-party code violates this standard and cannot be modified.
- A specific tool or framework pattern conflicts with a rule.

### 72.2 Deviation Request Form

A Deviation Request shall document:
1. Rule reference (section and tag, e.g. `[MISRA 15.1]`).
2. Location in source code (file, function, line range).
3. Reason compliance is impractical.
4. Alternative safety measures applied.
5. Risk assessment.
6. Approval by Software Engineering Lead and Quality Assurance.

### 72.3 Deviation Register

All approved deviations shall be recorded in the deviation register (`docs/aspice/deviations/`) with:
- Unique deviation ID.
- Approval date and approver.
- Expiry condition (e.g. "until third-party library is updated to v3.x").

### 72.4 In-Code Suppression

Where a cstylecheck rule must be suppressed, use the inline suppression comment:

```c
uint8_t legacy_API(int x);  /* cstylecheck: disable sign_compatibility */
```

Every suppression shall reference a deviation ID:

```c
/* Deviation DEV-0042: MISRA 15.1 — goto to cleanup label — see deviation register */
goto cleanup;
```

---

## 73. Document Change History

| Version | Date | Author | Change Description |
|---|---|---|---|
| 0.1 | 2026-09-19 | Claude | Initial |

---

## 74. Review & Approval

| Role | Name | Signature / Electronic Approval | Date |
|---|---|---|---|
| Author | Claude | Approved | 2026-09-19 |
| Reviewer | Dermot Murphy | — | *pending* |
| Approver | Dermot Murphy | — | *pending* |

---

*End of TB-STD-002 Embedded C Coding Standard v0.1*
