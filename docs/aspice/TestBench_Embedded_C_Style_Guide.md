# TestBench Embedded C Style Guide

*Automotive SPICE® PAM v4.0 | SWE.3, SWE.4, SUP.1 — Embedded C for TestBench firmware*

---

## Document Identification & Control

| Field | Value | Field | Value |
|---|---|---|---|
| **Document ID** | TB-STY-001 | **Version** | 0.1 |
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

---

## Table of Contents

1. [Purpose and Scope](#1-purpose-and-scope)
2. [Terms and Definitions](#2-terms-and-definitions)
3. [Normative References](#3-normative-references)
4. [ASPICE Compliance Notes](#4-aspice-compliance-notes)
5. [Roles and Responsibilities](#5-roles-and-responsibilities)
6. [File Organisation](#6-file-organisation)
7. [File Header and Footer](#7-file-header-and-footer)
8. [Include Guards](#8-include-guards)
9. [Indentation and Tabs](#9-indentation-and-tabs)
10. [Line Length](#10-line-length)
11. [Blank Lines and Vertical Whitespace](#11-blank-lines-and-vertical-whitespace)
12. [Horizontal Whitespace](#12-horizontal-whitespace)
13. [Brace Style](#13-brace-style)
14. [Parenthesis Style](#14-parenthesis-style)
15. [Naming Conventions — Overview](#15-naming-conventions--overview)
16. [Naming — Files](#16-naming--files)
17. [Naming — Module Prefix](#17-naming--module-prefix)
18. [Naming — Variables](#18-naming--variables)
19. [Naming — Constants and Object-Like Macros](#19-naming--constants-and-object-like-macros)
20. [Naming — Function-Like Macros](#20-naming--function-like-macros)
21. [Naming — Functions](#21-naming--functions)
22. [Naming — Types (typedef)](#22-naming--types-typedef)
23. [Naming — Struct and Union Tags](#23-naming--struct-and-union-tags)
24. [Naming — Enumeration Types and Members](#24-naming--enumeration-types-and-members)
25. [Naming — Interrupt Service Routines](#25-naming--interrupt-service-routines)
26. [Naming — Prefixes Summary Table](#26-naming--prefixes-summary-table)
27. [Comment Style — Line Comments](#27-comment-style--line-comments)
28. [Comment Style — Block Comments](#28-comment-style--block-comments)
29. [Comment Style — Doxygen Headers](#29-comment-style--doxygen-headers)
30. [Comment Style — File Header](#30-comment-style--file-header)
31. [Comment Style — Section Banners](#31-comment-style--section-banners)
32. [Comment Style — Inline Comments](#32-comment-style--inline-comments)
33. [Comment Density](#33-comment-density)
34. [Integer Literals](#34-integer-literals)
35. [Floating-Point Literals](#35-floating-point-literals)
36. [String Literals](#36-string-literals)
37. [Preprocessor Directives — Layout](#37-preprocessor-directives--layout)
38. [Preprocessor Directives — Include Order](#38-preprocessor-directives--include-order)
39. [Expressions and Operators](#39-expressions-and-operators)
40. [Control Flow Statement Layout](#40-control-flow-statement-layout)
41. [Switch Statement Layout](#41-switch-statement-layout)
42. [Function Definition Layout](#42-function-definition-layout)
43. [Struct and Union Layout](#43-struct-and-union-layout)
44. [Typedef Layout](#44-typedef-layout)
45. [Enum Layout](#45-enum-layout)
46. [Variable Declaration Layout](#46-variable-declaration-layout)
47. [Pointer Declarators](#47-pointer-declarators)
48. [Cast Expressions](#48-cast-expressions)
49. [Yoda Conditions](#49-yoda-conditions)
50. [Magic Numbers](#50-magic-numbers)
51. [End-of-File](#51-end-of-file)
52. [AStyle Configuration Reference](#52-astyle-configuration-reference)
53. [cstylecheck Configuration Reference](#53-cstylecheck-configuration-reference)
54. [Automated Enforcement](#54-automated-enforcement)
55. [Style Review Checklist](#55-style-review-checklist)
56. [Deviations](#56-deviations)
57. [Document Change History](#57-document-change-history)

---

## 1. Purpose and Scope

### 1.1 Purpose

This document defines the **visual and formatting conventions** for the C source
of this project: indentation, spacing, naming, commenting and layout —
independently of what the code does, which is the companion Embedded C Coding
Standard (TB-STD-002).

Consistent style is not decoration. It lowers the cost of review, lets static
analysis be strict without being noisy, and makes a diff show what changed
rather than how it was typed.

### 1.2 Scope

This guide applies to:

- all `.c` and `.h` files owned by this project — in practice
  `firmware/nordic_dongle/src/` and its headers;
- all new C files added to this project;
- existing files undergoing a modification that touches more than 20% of their
  lines.

### 1.3 Out of Scope

As TB-STD-002 §1.3: the nRF5 SDK and SoftDevice sources, `config/sdk_config.h`,
linker scripts, startup and assembly files, build files, and the Python source
of `benchtools`.

### 1.4 Relationship to Other Documents

| Document | ID | Relationship |
|---|---|---|
| TestBench Embedded C Coding Standard | TB-STD-002 | Companion — governs behavioural rules |
| Industry C Coding Standards — Applicability | TB-STD-001 | Rationale for rule choices |
| TestBench System Requirements | TB-SYS2-001 | TB-SYS2-092 requires conformance to this guide |
| CStyleCheck `rules.yml` | (tool config) | Machine-readable enforcement of this guide |
| AStyle configuration | (tool config) | Automated reformatter, derived from this guide |

---

## 2. Terms and Definitions

| Term | Definition |
|---|---|
| **Module** | A logical grouping of functionality, consisting of one `.c` and one or more `.h` files sharing a common prefix. |
| **Module prefix** | A short lowercase identifier (e.g. `uart`, `can`, `adc`) prepended to all public identifiers in a module. |
| **File scope** | Identifiers declared at the top level of a translation unit, outside any function. |
| **Block scope** | Identifiers declared inside a function body or compound statement. |
| **Snake case** | Words separated by underscores, all lowercase: `my_variable`. |
| **Upper snake case** | Words separated by underscores, all uppercase: `MY_CONSTANT`. |
| **Pascal case** | Each word starts with a capital letter, no separator: `MyFunction`. |
| **Object-like macro** | A `#define` whose replacement list does not include a parameter list. |
| **Function-like macro** | A `#define` whose name is immediately followed by `(`. |
| **Magic number** | A numeric literal embedded directly in code without a named constant. |
| **ISR** | Interrupt Service Routine — a function invoked by hardware interrupt. |
| **Yoda condition** | A comparison where the constant appears on the left: `if (0 == x)`. |
| **Doxygen** | A documentation generator that parses structured comment tags (`@brief`, `@param`, `@return`). |
| **AStyle** | Artistic Style — an open-source source code formatter for C/C++. |
| **cstylecheck** | The project style checker (this repository) that enforces naming and miscellaneous rules. |

---

## 3. Normative References

The following documents are referenced normatively. When a conflict exists, the order of precedence is as listed.

1. **MISRA C:2012** — Guidelines for the Use of the C Language in Critical Systems, MISRA Ltd, 2012 (including Amendment 1:2016 and MISRA C:2023 corrigendum).
2. **Barr-C:2018** — Embedded C Coding Standard, Barr Group, version 2.0, 2018.
3. **ASPICE v4.0** — Automotive SPICE Process Assessment / Reference Model, VDA QMC, 2023.
4. **ISO/IEC 9899:2011 (C11)** — Programming languages — C.
5. **CERT C Coding Standard** — SEI CERT C Coding Standard, Carnegie Mellon University, 2016.
6. **NASA/JPL C Coding Standard** — Power of Ten Rules, Gerard Holzmann, JPL, 2006.
7. **ISO 26262-6:2018** — Road vehicles — Functional safety — Part 6: Product development at the software level.

---

## 4. ASPICE Compliance Notes

This document supports the following ASPICE v4 Level 2 process areas and generic practices:

| ASPICE Process Area | Relevant Practice | How This Document Contributes |
|---|---|---|
| SWE.3 Software Detailed Design and Unit Construction | BP3 — Define software unit interfaces | Naming conventions ensure consistent interface identifiers |
| SWE.3 | BP5 — Implement software units | Style rules applied during unit construction |
| SWE.4 Software Unit Verification | BP2 — Conduct static verification | Style guide rules are automatically enforced by cstylecheck |
| SUP.1 Quality Assurance | BP2 — Assure compliance of work products | Style review checklist (Section 55) |
| SUP.8 Configuration Management | BP1 — Identify configuration items | This document is under version control as a configuration item |
| GP 2.1.1 | Define the process | This document is the defined process for C style |
| GP 2.2.1 | Define responsibility and authority | Section 5 defines ownership |
| GP 2.3.1 | Identify process information items | Document ID, version, and status are tracked |

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

## 6. File Organisation

### 6.1 Source File Pairs

Each module shall consist of exactly one `.c` implementation file and one `.h` public header. A module may have additional private header files (suffix `_priv.h` or `_internal.h`).

```
uart/
    uart.c          /* implementation */
    uart.h          /* public API */
    uart_priv.h     /* internal definitions (optional) */
```

### 6.2 File Naming

- File names shall use **lowercase snake case**: `motor_control.c`, `adc_driver.h`.
- File names shall not exceed 31 characters (excluding extension).
- File names shall not duplicate any C standard library header name (e.g. `string.h`, `stdio.h` are forbidden). `[RULE: misc.reserved_header_name]`

### 6.3 Directory Structure

```
src/
    app/            /* application-layer modules */
    drivers/        /* hardware-driver modules */
    middleware/     /* platform-independent middleware */
    hal/            /* hardware abstraction layer */
    rtos/           /* RTOS integration/wrappers */
    common/         /* shared utilities, types, macros */
inc/                /* public headers exposed to host applications */
tests/              /* unit tests */
third_party/        /* vendor code — exempt from this guide */
```

### 6.4 Maximum File Length

Each source file shall not exceed **500 lines** in total (including blanks, comments, and code). `[RULE: misc.file_length]`

Files approaching this limit should be split into logical sub-modules.

---

## 7. File Header and Footer

### 7.1 File Header

Every `.c` and `.h` file shall begin with a copyright block comment, followed by exactly one blank line.

```c
/*
 * (C) Copyright 2026 <Organisation Name>
 *
 * SPDX-License-Identifier: <licence-identifier>
 *
 * File:    uart.c
 * Module:  UART Driver
 * Brief:   UART transmit/receive driver for STM32F4.
 *
 * ASPICE:  SWE.3
 * MISRA:   Compliant subset — see project deviation list
 */
```

`[RULE: misc.copyright_header]` — The copyright block must match the template in `src/copyright_header.txt`; year may differ.

### 7.2 File Footer (Optional)

When enabled, each file shall end with a single-line EOF comment followed by exactly one blank line:

```c
/* EOF: uart.c */

```

`[RULE: misc.eof_comment]`

---

## 8. Include Guards

### 8.1 Macro-Based Guards

Every `.h` file shall use an include guard whose macro name matches the pattern:

```
{FILENAME_UPPER}_{EXT_UPPER}_
```

Example for `uart_driver.h`:

```c
#ifndef UART_DRIVER_H_
#define UART_DRIVER_H_

/* ... header content ... */

#endif /* UART_DRIVER_H_ */
```

`[RULE: include_guards]`

### 8.2 `#pragma once`

`#pragma once` is permitted as an alternative to macro guards when supported by the toolchain. When used, it shall appear as the very first non-comment line of the file.

---

## 9. Indentation and Tabs

### 9.1 Indentation Character

`[RULE: misc.indentation]`

Indentation shall be by **tab characters**. One tab is **eight columns**.

Spaces shall not be used for indentation. Where a line must be aligned rather
than indented — a continuation that lines up under an opening parenthesis, a
column in a table of initialisers — the alignment is made with tabs at the
same eight-column grid, so that the file reads identically at any tab setting
that is a multiple of eight.

The CStyleCheck configuration (`misc.indentation`: tabs, width 8) and the
AStyle configuration enforce this. Where the two disagree, the AStyle
configuration is the authoritative source, because it is the one that rewrites
the file.

### 9.2 Continuation Lines

Lines broken for length shall be indented **two indent levels** beyond the
opening line:

```c
result = some_very_long_function_name(
		first_argument,
		second_argument,
		third_argument);
```

### 9.3 Preprocessor Directives

Preprocessor directives shall be left-aligned at column 0. Nested directives
indent the keyword only, never the `#`:

```c
#if defined(UART_ENABLE)
#  if defined(UART_DMA)
	/* DMA path */
#  else
	/* polling path */
#  endif
#endif
```

---

## 10. Line Length

`[RULE: misc.line_length]`

> **Placeholder:** The maximum line length will be derived from `src/rules.yml → misc.line_length.max` and the AStyle `--max-code-length` option.

Current `rules.yml` default: 180 characters. This placeholder will be updated when the AStyle config is finalised.

### 10.1 Breaking Long Lines

When a line exceeds the limit:

- Break after a comma in an argument list.
- Break before a binary operator (`&&`, `||`, `+`, etc.); the operator leads the continuation line.
- Break after `=` or `return`.
- Do not break inside a string literal unless using implicit concatenation.

---

## 11. Blank Lines and Vertical Whitespace

### 11.1 Between Top-Level Declarations

- **Two blank lines** shall separate top-level function definitions.
- **One blank line** shall separate `#include` blocks, `typedef` declarations, and non-function file-scope declarations from each other.

### 11.2 Within a Function Body

- **One blank line** shall follow the local variable declaration block before the first executable statement. `[RULE: misc.declaration_spacing]`
- **One blank line** shall precede a block comment that introduces a logical section.
- No more than **one consecutive blank line** inside a function body.

### 11.3 Whitespace Ratio

`[RULE: misc.whitespace_ratio]`

The ratio of blank lines to code lines in a file shall not fall below the configured thresholds, ensuring adequate readability spacing.

---

## 12. Horizontal Whitespace

### 12.1 Around Operators

- A single space shall appear on both sides of all binary and ternary operators: `a + b`, `x == y`, `a ? b : c`.
- No space between a unary operator and its operand: `!flag`, `~mask`, `*p_buf`, `&var`.
- No space between `sizeof` / `alignof` and `(type)` when used as a type query: `sizeof(uint32_t)`.

### 12.2 After Keywords

A single space shall follow control-flow keywords: `if (`, `for (`, `while (`, `switch (`, `do {`.

No space between a function name and its `(`: `uart_Init()`, not `uart_Init ()`.

### 12.3 After Commas

A single space shall follow each comma in argument lists, initialiser lists, and parameter declarations.

### 12.4 Inside Brackets

No space immediately inside parentheses or square brackets:

```c
/* Correct */
result = func(a, b);
val = array[idx];

/* Wrong */
result = func( a, b );
val = array[ idx ];
```

### 12.5 Pointer and Address-of Operators

The `*` (dereference / pointer declarator) and `&` (address-of) operators shall be written adjacent to the **type**, not the variable name, in declarations:

```c
uint8_t *p_buffer;   /* correct */
uint8_t* p_buffer;   /* also acceptable per AStyle config */
uint8_t * p_buffer;  /* wrong */
```

`[AStyle: --align-pointer=type | --align-pointer=middle]` — authoritative setting comes from the AStyle configuration file.

---

## 13. Brace Style

`[AStyle: --style=]`

> **Placeholder:** The brace placement style (Allman, K&R, Linux, etc.) will be derived from the project AStyle configuration file.

### 13.1 Mandatory Braces

Braces **shall** be used around the body of every `if`, `else`, `for`, `while`, and `do` statement, even when the body is a single statement. (MISRA C:2012 Rule 15.6, Barr-C 8.3.)

```c
/* Correct */
if (NULL == p_buf)
{
    return ERROR;
}

/* Wrong */
if (NULL == p_buf)
    return ERROR;
```

### 13.2 Empty Blocks

An empty block shall contain a comment explaining why it is intentionally empty:

```c
while (uart_RxBufferIsEmpty())
{
    /* intentional busy-wait — timeout handled by caller */
}
```

---

## 14. Parenthesis Style

### 14.1 Explicit Parentheses for Clarity

Use parentheses to make operator precedence explicit whenever mixing operators from different precedence groups:

```c
result = (a + b) * c;           /* explicit */
result = a + b * c;             /* relies on precedence — avoid */
```

### 14.2 Return Statements

`return` is a statement, not a function. Do not enclose its expression in superfluous parentheses unless the parentheses are needed for line-breaking:

```c
return status;          /* correct */
return (status);        /* wrong */
```

---

## 15. Naming Conventions — Overview

All identifiers shall be:

- Written in **English**.
- **Self-documenting** — the name shall convey meaning without relying on comments for basic understanding.
- Free of cryptic abbreviations not listed in the project abbreviation list (`src/aliases.txt`).
- Not shorter than **3 characters**, except for permitted single-character loop counters (`i`, `j`, `k`). `[RULE: variables.min_length]`
- Not longer than **40 characters** for variables, **60 characters** for functions and macros. `[RULE: variables.max_length, functions.max_length]`
- Free of reserved C/POSIX/C++ names (checked by `[RULE: reserved_names]`).

---

## 16. Naming — Files

- Lowercase snake case: `motor_control.c`.
- The base name (without extension) forms the **module prefix** for all identifiers within that file.
- Header file names shall match their corresponding source file: `uart.c` → `uart.h`.

---

## 17. Naming — Module Prefix

`[RULE: file_prefix]`

All identifiers at file scope (global variables, static variables, functions, object-like macros, constants) **shall** be prefixed with the module name followed by the separator `_`:

```
uart_      →  uart_TxBufferSend, uart_g_tx_count, UART_BAUD_RATE
can_       →  can_MessageReceive, can_s_rx_queue, CAN_MAX_PAYLOAD
```

- The module prefix shall be **lowercase**.
- The separator shall be `_`.
- `main.c` and `main.h` are exempt from the prefix requirement. `[RULE: file_prefix.exempt_main]`

---

## 18. Naming — Variables

`[RULE: variables]`

### 18.1 Case

All variable names shall use **lower snake case**: `tx_byte_count`, `buffer_index`.

### 18.2 Scope Prefixes

| Scope | Required prefix (local part, after module prefix) | Example |
|---|---|---|
| Global (extern linkage) | `g_` | `uart_g_tx_count` |
| File-scope static | `s_` | `uart_s_rx_queue` |
| Local variable | none | `byte_count` |
| Parameter | none (see 18.3) | `buffer_size` |

`[RULE: variables.global.g_prefix, variables.static.s_prefix]`

### 18.3 Parameter Prefix (Optional)

When `variables.parameter.p_prefix.enabled` is set to `true`, all function parameters shall begin with `p_`:

```c
void uart_BufferWrite(uint8_t *p_p_data, uint16_t p_length);
```

### 18.4 Pointer Prefix

Single-pointer variables shall have their local part begin with `p_`: `p_buffer`, `uart_s_p_rx_head`. `[RULE: variables.pointer_prefix]`

Double-pointer variables shall begin with `pp_`: `pp_device_list`. `[RULE: variables.pp_prefix]`

### 18.5 Boolean Prefix (Optional)

When enabled, `bool`/`_Bool` variables shall begin with `b_` and be phrased as a question: `b_is_full`, `b_transmit_active`. `[RULE: variables.bool_prefix]`

### 18.6 Handle Prefix

Variables holding RTOS or POSIX handles (e.g. `TaskHandle_t`, `FILE *`) shall begin with `h_`: `h_uart_task`, `h_log_file`. `[RULE: variables.handle_prefix]`

### 18.7 Numeric Suffixes in Names

`[RULE: variables.no_numeric_in_name]`

Variable names shall not embed a numeric value that is duplicated elsewhere (e.g. `buffer32` when the type is `uint32_t`). Hardware peripheral instance numbers (e.g. `uart2`, `spi1`) are exempt.

### 18.8 Prefix Ordering

When multiple prefixes apply, they shall appear in the order: `[g_] [p_|pp_] [b_|h_]`. `[RULE: variables.prefix_order]`

Example: a global pointer to a boolean: `uart_g_p_b_overflow_flag`.

---

## 19. Naming — Constants and Object-Like Macros

`[RULE: constants, macros (object-like)]`

All object-like `#define` constants and `const`-qualified file-scope variables shall use **UPPER\_SNAKE\_CASE**:

```c
#define UART_BAUD_RATE    115200U
#define MAX_PACKET_SIZE   256U

static const uint8_t uart_s_PREAMBLE[] = { 0xAAU, 0x55U };
```

- Minimum length: 2 characters. Maximum length: 60 characters.
- Module prefix applies: `UART_`, `CAN_`, etc.
- RTOS configuration macros (`configUSE_*`, `portMAX_DELAY`, etc.) are exempt. `[RULE: constants.exempt_patterns]`

---

## 20. Naming — Function-Like Macros

`[RULE: macros]`

Function-like macros shall also use **UPPER\_SNAKE\_CASE**:

```c
#define UART_SET_BAUD(baud)   (USART1->BRR = (baud))
#define MAX(a, b)             (((a) > (b)) ? (a) : (b))
```

An optional `_M` suffix may be required by the project configuration to distinguish function-like macros from constants: `UART_SET_BAUD_M(baud)`. `[RULE: macros.function_like_suffix]`

---

## 21. Naming — Functions

`[RULE: functions]`

### 21.1 Style

The project shall use **Object–Verb** style: `<Module>_<Object><Verb>`

```
uart_BufferRead       (module=uart, object=Buffer, verb=Read)
can_MessageSend       (module=can, object=Message, verb=Send)
adc_ChannelConvert    (module=adc, object=Channel, verb=Convert)
```

`[RULE: functions.style = object_verb]`

Object and verb segments shall use **PascalCase**. `[RULE: functions.object_case = pascal, functions.verb_case = pascal]`

Minimum length: 4 characters. Maximum length: 60 characters.

### 21.2 Static (Private) Functions

When `functions.static_prefix.enabled` is `true`, file-scope static functions shall be prefixed with `prv_`:

```c
static void prv_uart_FifoFlush(void);
```

### 21.3 Permitted Object Exclusions

Short verbs that act as both object and verb (`Wr`, `Rd`, `Init`, `IoCntrl`) exempt the function from the full object\_verb check. `[RULE: functions.object_exclusions]`

---

## 22. Naming — Types (typedef)

`[RULE: typedefs]`

All project-defined `typedef` names shall use **UPPER\_SNAKE\_CASE** with a `_T` suffix:

```c
typedef struct uart_config_s  UART_CONFIG_T;
typedef uint16_t              MOTOR_SPEED_T;
typedef void (*UART_CALLBACK_T)(uint8_t byte);
```

Standard fixed-width types (`uint8_t`, `int32_t`, etc.) from `<stdint.h>` are exempt.

---

## 23. Naming — Struct and Union Tags

`[RULE: structs]`

Struct and union **tags** shall use **lower snake case** with a `_s` suffix (struct) or `_u` suffix (union):

```c
struct uart_config_s
{
    uint32_t baud_rate;
    uint8_t  stop_bits;
};

union sensor_data_u
{
    float    f_value;
    uint32_t raw;
};
```

Struct **member names** shall use lower snake case, with no module prefix required.

---

## 24. Naming — Enumeration Types and Members

`[RULE: enums]`

- Enum **type names** shall use lower snake case with a `_t` suffix: `uart_status_t`.
- Enum **member names** shall use UPPER\_SNAKE\_CASE prefixed with the type name (minus the `_t` suffix, uppercased):

```c
typedef enum uart_status_t
{
    UART_STATUS_OK      = 0,
    UART_STATUS_ERROR   = 1,
    UART_STATUS_TIMEOUT = 2,
    UART_STATUS_BUSY    = 3
} uart_status_t;
```

`[RULE: enums.type_suffix = _t, enums.member_prefix_from_type = true]`

---

## 25. Naming — Interrupt Service Routines

`[RULE: functions.isr_suffix]`

ISR functions shall use the suffix `_IRQHandler` as required by the CMSIS/STM32 vector table naming convention:

```c
void USART1_IRQHandler(void);
void TIM2_IRQHandler(void);
void DMA1_Stream0_IRQHandler(void);
```

ISR functions are exempt from the module prefix requirement. `[RULE: file_prefix.exempt_patterns → ISR]`

---

## 26. Naming — Prefixes Summary Table

| Category | Case | Prefix / Suffix | Example |
|---|---|---|---|
| File name | lower\_snake | — | `uart_driver.c` |
| Module prefix | lower | `<module>_` | `uart_` |
| Global variable | lower\_snake | `<mod>_g_` | `uart_g_tx_count` |
| Static variable | lower\_snake | `<mod>_s_` | `uart_s_rx_head` |
| Local variable | lower\_snake | — | `byte_count` |
| Parameter | lower\_snake | `p_` (optional) | `p_buffer` |
| Pointer | lower\_snake | `p_` prefix on local part | `p_data` |
| Double pointer | lower\_snake | `pp_` | `pp_handle` |
| Boolean | lower\_snake | `b_` (optional) | `b_is_ready` |
| Handle | lower\_snake | `h_` | `h_uart_task` |
| Constant (`#define`) | UPPER\_SNAKE | `<MOD>_` | `UART_BAUD_RATE` |
| Function-like macro | UPPER\_SNAKE | `<MOD>_` | `UART_SET_BAUD` |
| Function | Module + PascalCase | `<mod>_<Object><Verb>` | `uart_BufferRead` |
| typedef | UPPER\_SNAKE | `_T` suffix | `UART_CONFIG_T` |
| Struct tag | lower\_snake | `_s` suffix | `uart_config_s` |
| Union tag | lower\_snake | `_u` suffix | `sensor_data_u` |
| Enum type | lower\_snake | `_t` suffix | `uart_status_t` |
| Enum member | UPPER\_SNAKE | `<TYPE_PREFIX>_` | `UART_STATUS_OK` |
| ISR | UPPER / mixed | `_IRQHandler` suffix | `USART1_IRQHandler` |

---

## 27. Comment Style — Line Comments

Line comments (`//`) shall be permitted and preferred for brief end-of-line annotations:

```c
uint32_t baud_rate;     /* baud rate in bits/second */
uint8_t  stop_bits;     /* 1 or 2 */
```

Both `//` and `/* */` are acceptable. Projects using C89/C90 compatibility shall restrict to `/* */` only.

---

## 28. Comment Style — Block Comments

Multi-line block comments shall use the following format:

```c
/*
 * This is a multi-line block comment.
 * Each continuation line begins with a space and asterisk.
 * The closing delimiter is on its own line.
 */
```

`[RULE: misc.block_comment_spacing]` — After the closing `*/`, at least one and at most two blank lines shall follow before the next non-blank line (when the rule is enabled).

---

## 29. Comment Style — Doxygen Headers

`[RULE: misc.function_doc_header]`

Every function definition shall be immediately preceded by a Doxygen block comment containing at minimum:

```c
/**
 * @brief   Reads a byte from the UART receive buffer.
 *
 * @param[out] p_byte    Pointer to storage for the received byte.
 * @param[in]  timeout   Timeout in milliseconds; 0 = non-blocking.
 *
 * @return  UART_STATUS_OK on success.
 * @return  UART_STATUS_TIMEOUT if no data arrived within timeout.
 * @return  UART_STATUS_ERROR on hardware fault.
 */
uart_status_t uart_BufferRead(uint8_t *p_byte, uint32_t timeout)
{
```

Required tags: `@brief`, `@param` (one per parameter), `@return` (for non-void functions).

---

## 30. Comment Style — File Header

See Section 7.1. The file header comment shall contain at minimum: copyright, SPDX licence, file name, module name, and a one-line brief description.

---

## 31. Comment Style — Section Banners

Logical sections within a source file may be separated by a banner comment:

```c
/* =========================================================================
 * Receive Path
 * ========================================================================= */
```

Banners shall not exceed the line-length limit.

---

## 32. Comment Style — Inline Comments

Inline comments on the same line as code shall be separated from the code by **at least two spaces**:

```c
uint32_t timeout_ms = 100U;  /* default 100 ms per UART spec §4.2 */
```

Inline comments shall not state the obvious. Comment the **why**, not the **what**.

---

## 33. Comment Density

`[RULE: misc.comment_ratio]`

The ratio of explanatory comment lines to code lines shall not fall below the configured thresholds:

- Warning threshold: 15 % (default).
- Error threshold: 5 % (default).

File header blocks and Doxygen blocks are excluded from this count (they are documentation, not explanatory comments).

---

## 34. Integer Literals

### 34.1 Unsigned Suffix

Unsigned integer constants shall carry a `U` suffix. `[RULE: misc.unsigned_suffix]`

```c
#define BUFFER_SIZE  256U
uint8_t mask = 0xFFU;
```

The literal `0` is neutral and does not require `U`.

### 34.2 Uppercase Suffixes

Integer suffixes shall use **uppercase** letters only. The lowercase `l` is visually ambiguous with `1` and is forbidden. `[RULE: misc.lowercase_l_suffix]` (MISRA C:2012 Rule 7.3)

```c
/* Correct */
int32_t val = 1000L;
uint32_t big = 1000000UL;

/* Wrong */
int32_t val = 1000l;    /* lowercase l */
```

### 34.3 Hexadecimal Digits

Hexadecimal digits `A`–`F` shall be uppercase: `0xDEADBEEFU`.

### 34.4 Octal Constants

Octal integer constants are forbidden (MISRA C:2012 Rule 7.1). `[RULE: misc.octal_constant]`

```c
/* Wrong */
uint8_t mode = 010;  /* octal 8, not decimal 10 */

/* Correct */
uint8_t mode = 8U;
```

The bare literal `0` (zero alone) is always permitted.

### 34.5 Trigraphs

Trigraphs are forbidden in all source and header files. `[RULE: misc.trigraph]` (MISRA C:2012/2023 Rule 4.2)

---

## 35. Floating-Point Literals

Floating-point literals shall always include a decimal point and at least one digit on each side:

```c
float gain = 1.0F;       /* correct */
float gain = 1.F;        /* wrong — no digit after decimal */
float gain = 1;          /* wrong — integer literal assigned to float */
```

The `F` suffix shall be used for `float` literals; no suffix for `double`.

---

## 36. String Literals

- String literals shall be declared `const` when assigned to a pointer: `const char *p_name = "uart";`.
- String literal concatenation across lines is permitted:

```c
const char *p_msg = "First part of a very long "
                    "message string.";
```

---

## 37. Preprocessor Directives — Layout

### 37.1 `#define` Alignment

When multiple related `#define` constants are grouped together, their values may be vertically aligned:

```c
#define UART_BAUD_9600    9600U
#define UART_BAUD_115200  115200U
#define UART_BAUD_921600  921600U
```

### 37.2 Macro Parameter Parentheses

Every macro parameter shall be enclosed in parentheses in the replacement text (MISRA C:2012 Rule 20.7):

```c
#define SQUARE(x)   ((x) * (x))   /* correct */
#define SQUARE(x)   (x * x)       /* wrong */
```

### 37.3 Multi-Statement Macros

Function-like macros containing two or more statements shall be wrapped in `do { ... } while (0U)`. `[RULE: macros.multistatement_wrapper]` (CERT PRE10-C)

```c
#define UART_ASSERT_AND_LOG(cond, msg)  \
    do {                                \
        if (!(cond)) {                  \
            log_Error(msg);             \
            assert(false);              \
        }                               \
    } while (0U)
```

### 37.4 Trailing Semicolon in Macros

A `#define` body shall not end with a bare semicolon. `[RULE: macros.trailing_semicolon]` (CERT PRE11-C)

---

## 38. Preprocessor Directives — Include Order

`#include` directives shall be ordered as follows, each group separated by one blank line:

1. The module's own header (for `.c` files): `#include "uart.h"`
2. Other project headers: `#include "can.h"`
3. RTOS and middleware headers: `#include "FreeRTOS.h"`
4. HAL and driver headers: `#include "stm32f4xx_hal.h"`
5. C standard library headers: `#include <stdint.h>`

All project-relative headers shall use double-quote syntax. All system/library headers shall use angle-bracket syntax.

---

## 39. Expressions and Operators

### 39.1 Explicit Precedence

Parentheses shall be used to make operator precedence explicit when combining operators from different precedence levels. Relying on non-obvious precedence is prohibited.

### 39.2 Compound Assignment

Compound assignment operators (`+=`, `-=`, etc.) are permitted. Do not expand them to verbose form unless clarity requires it.

### 39.3 Comma Operator

The comma operator shall not be used outside `for` loop initialisers/increments.

### 39.4 Sizeof

`sizeof` shall always be applied to a **variable** or **expression**, not a **type name**, in contexts where the variable type is known:

```c
memset(p_buf, 0, sizeof(*p_buf));  /* preferred */
memset(p_buf, 0, sizeof(BUF_T));   /* acceptable, not preferred */
```

---

## 40. Control Flow Statement Layout

### 40.1 `if` / `else`

```c
if (UART_STATUS_OK == status)
{
    /* ... */
}
else if (UART_STATUS_TIMEOUT == status)
{
    /* ... */
}
else
{
    /* ... */
}
```

- `else` shall be on the same line as the closing `}` or on the next line (AStyle-controlled).
- Braces are mandatory even for single-statement bodies (Section 13.1).

### 40.2 `for`

```c
for (uint8_t i = 0U; i < UART_BUFFER_SIZE; i++)
{
    /* ... */
}
```

### 40.3 `while`

```c
while (0U == uart_RxBufferIsEmpty())
{
    /* ... */
}
```

### 40.4 `do … while`

```c
do
{
    status = uart_ByteReceive(&byte);
} while (UART_STATUS_BUSY == status);
```

### 40.5 Null Statements

A null (empty) statement shall be on its own line with a comment. `[RULE: misc.null_statement_comment]` (JSF Rule 192)

```c
while (uart_TxBufferIsEmpty())
{
    ; /* intentional spin-wait */
}
```

---

## 41. Switch Statement Layout

```c
switch (uart_status)
{
    case UART_STATUS_OK:
        uart_ProcessByte(byte);
        break;

    case UART_STATUS_TIMEOUT:
        uart_HandleTimeout();
        break;

    default:
        uart_HandleError(uart_status);
        break;
}
```

Rules:
- Every `case` and `default` label shall be indented one level from the `switch`.
- The body of each `case` shall be indented one further level.
- Every `case` shall end with `break`, `return`, or `/* fall-through */` comment.
- A `default` label shall always be present (MISRA C:2012 Rule 16.4).

---

## 42. Function Definition Layout

```c
/**
 * @brief  Transmits a buffer over UART.
 * @param[in] p_data    Pointer to data buffer.
 * @param[in] length    Number of bytes to transmit.
 * @return              UART_STATUS_OK on success.
 */
uart_status_t uart_BufferTransmit(const uint8_t *p_data, uint16_t length)
{
    uart_status_t status = UART_STATUS_OK;
    uint16_t      byte_idx;

    for (byte_idx = 0U; byte_idx < length; byte_idx++)
    {
        status = uart_ByteTransmit(p_data[byte_idx]);
        if (UART_STATUS_OK != status)
        {
            break;
        }
    }

    return status;
}
```

- The return type and function name shall be on the **same line**.
- The opening brace shall be placed as configured by AStyle.
- Local variable declarations shall appear at the **top** of the function body, before the first executable statement.
- The function shall have a **single return point** (MISRA C:2012 Rule 15.5, advisory).

### 42.1 Function Length

Each function body shall not exceed **60 lines**. `[RULE: misc.function_length]` (NASA Power of Ten Rule 4)

---

## 43. Struct and Union Layout

```c
typedef struct uart_config_s
{
    uint32_t  baud_rate;      /* baud rate in bits/s */
    uint8_t   data_bits;      /* 7 or 8 */
    uint8_t   stop_bits;      /* 1 or 2 */
    uint8_t   parity;         /* UART_PARITY_NONE / ODD / EVEN */
    uint8_t   pad[3];         /* explicit padding — MISRA C:2012 Rule 6.1 */
} UART_CONFIG_T;
```

- Member names shall use lower snake case.
- Explicit padding members shall be named `pad[n]` with a comment.
- `typedef` and `struct` declaration shall be combined where the tag is also needed.

---

## 44. Typedef Layout

```c
/* Scalar typedef */
typedef uint16_t MOTOR_SPEED_T;

/* Struct typedef — combined form */
typedef struct sensor_sample_s
{
    uint32_t timestamp_ms;
    int16_t  temperature_raw;
} SENSOR_SAMPLE_T;

/* Function-pointer typedef */
typedef void (*UART_RX_CALLBACK_T)(uint8_t byte, void *p_context);
```

---

## 45. Enum Layout

```c
typedef enum motor_state_t
{
    MOTOR_STATE_IDLE    = 0,
    MOTOR_STATE_RUNNING = 1,
    MOTOR_STATE_FAULT   = 2,
    MOTOR_STATE_COUNT       /* sentinel — not a valid state */
} motor_state_t;
```

- Members shall be vertically aligned at the `=` where practical.
- A sentinel member (`_COUNT`, `_MAX`, `_LAST`) is recommended for array sizing.
- The first member shall be explicitly initialised to `0`.

---

## 46. Variable Declaration Layout

### 46.1 One Declaration Per Line

Each variable shall be declared on its own line:

```c
/* Correct */
uint8_t  byte_count;
uint32_t timeout_ms;

/* Wrong */
uint8_t byte_count, timeout_ms;
```

### 46.2 Initialisation

All variables shall be initialised at the point of declaration or immediately following:

```c
uint8_t  status      = 0U;
uint16_t packet_size = 0U;
```

### 46.3 Scope Minimisation

Variables shall be declared at the narrowest applicable scope.

---

## 47. Pointer Declarators

The `*` in a pointer declaration shall be placed as configured by the AStyle `--align-pointer` option. Within a single declaration group, placement shall be consistent.

```c
uint8_t  *p_buffer;          /* pointer-to-type style */
uint8_t  *p_src, *p_dst;     /* only if both are pointers */
```

Multiple pointer and non-pointer variables shall not share a single declaration line.

---

## 48. Cast Expressions

- Casts shall be used sparingly and only when a conversion is explicitly required.
- Every cast shall be accompanied by a comment explaining why it is safe.
- C-style casts are the only form available in C; they shall be written with no space between the type and the cast expression:

```c
uint8_t byte = (uint8_t)raw_value;  /* truncation intentional: only lower 8 bits needed */
```

---

## 49. Yoda Conditions

`[RULE: misc.yoda_conditions]`

In equality comparisons (`==`, `!=`), the **constant or rvalue** shall appear on the **left**:

```c
if (NULL == p_buffer)       { /* correct */ }
if (UART_STATUS_OK == ret)  { /* correct */ }

if (p_buffer == NULL)       { /* wrong */ }
```

This prevents accidental assignment in place of comparison.

---

## 50. Magic Numbers

`[RULE: misc.magic_numbers]`

Numeric literals other than `0`, `1`, `-1`, and a project-defined exempt list shall not appear directly in code. Use named constants:

```c
/* Correct */
#define UART_RX_TIMEOUT_MS   100U
if (elapsed_ms > UART_RX_TIMEOUT_MS)

/* Wrong */
if (elapsed_ms > 100U)
```

---

## 51. End-of-File

Every source file shall end with exactly **one newline character** after the last non-blank content. Most editors and git tools enforce this automatically. Files that do not end with a newline produce compiler warnings on some toolchains.

---

## 52. AStyle Configuration Reference

> **Placeholder:** This section will be populated with the complete project AStyle (`.astylerc`) configuration when the file is finalised. Key options to document include:
>
> - `--style=` (brace placement)
> - `--indent=` (tab/space and width)
> - `--max-code-length=` (line length)
> - `--align-pointer=` (pointer declarator alignment)
> - `--pad-oper` / `--pad-paren` (operator spacing)
> - `--break-blocks` (blank lines between blocks)
> - `--add-brackets` (mandatory braces on single-line bodies)

The AStyle configuration file shall be version-controlled at `.astylerc` in the project root. Any deviation from AStyle-reformatted output is a style violation.

---

## 53. cstylecheck Configuration Reference

> **Placeholder:** This section will document which rules in `src/rules.yml` enforce each section of this style guide. A cross-reference table mapping rule IDs to style guide sections will be inserted here after the rule population phase.

The cstylecheck tool enforces naming conventions, prefix rules, magic numbers, line length, indentation, comment density, and other rules defined in `src/rules.yml`. All rules shall be run in CI on every pull request.

---

## 54. Automated Enforcement

### 54.1 CI Pipeline

Style checks shall run automatically as part of the CI pipeline:

1. **AStyle** — reformats code to canonical style (or fails if output differs from committed code).
2. **cstylecheck** — enforces naming conventions and miscellaneous rules from `src/rules.yml`.
3. **pre-commit hook** — runs both tools locally before each commit.

### 54.2 Zero-Violation Policy

No new style violations shall be introduced in a pull request. The baseline violation count shall not increase. `[RULE: misc.baseline]`

### 54.3 Suppression

Per-line suppression: `/* cstylecheck: disable <rule.id> */`

Per-file suppression: add an entry to `src/exclusions.yml`.

Suppressions require a justification comment and shall be reviewed during code review.

---

## 55. Style Review Checklist

Use this checklist during code review to verify style compliance. Automated tools cover most items; this list targets items requiring human judgement.

- [ ] File header is present and correct (Section 7).
- [ ] Include guard matches the pattern (Section 8).
- [ ] Indentation is consistent throughout (Section 9).
- [ ] No line exceeds the configured maximum (Section 10).
- [ ] All identifiers follow naming conventions (Sections 15–26).
- [ ] All function parameters and return values are documented (Section 29).
- [ ] Braces are present on all control flow bodies (Section 13.1).
- [ ] All magic numbers have named constants (Section 50).
- [ ] Yoda conditions used for `==` and `!=` (Section 49).
- [ ] No octal literals present (Section 34.4).
- [ ] All integer constants have uppercase suffixes (Section 34.2).
- [ ] No trigraphs present (Section 34.5).
- [ ] Comments explain "why", not "what" (Section 32).
- [ ] No commented-out code (dead code shall be deleted, not commented out).
- [ ] Function length does not exceed the limit (Section 42.1).
- [ ] File length does not exceed the limit (Section 6.4).

---

## 56. Deviations

### 56.1 Deviation Request Process

When strict compliance with a rule in this guide is impractical, a deviation shall be requested using the project Deviation Request form. The request shall include:

- Rule reference (section number and `[RULE:]` tag).
- Reason compliance is impractical.
- Alternative measures taken to mitigate the risk.
- Approval from the Software Engineering Lead.

### 56.2 Deviation Register

All approved deviations shall be recorded in the project Deviation Register (`docs/aspice/deviations/`) with a unique deviation ID, approval date, and expiry condition.

---

## 57. Document Change History

| Version | Date | Author | Change Description |
|---|---|---|---|
| 0.1 | 2026-09-19 | Claude | Initial |

---

## 58. Review & Approval

| Role | Name | Signature / Electronic Approval | Date |
|---|---|---|---|
| Author | Claude | Approved | 2026-09-19 |
| Reviewer | Dermot Murphy | — | *pending* |
| Approver | Dermot Murphy | — | *pending* |

---

*End of TB-STY-001 Embedded C Style Guide v0.1*
