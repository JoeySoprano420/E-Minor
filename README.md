# E-Minor

## # E Minor v1.0 — Complete Language Overview

> You want native speed *and* mechanical sympathy, without giving up safety or clarity. E Minor is that pact: a dual-syntax language whose source maps deterministically to a hex-IR that is one breath from machine code—no ambiguity, no mysterious runtime.

---

## 1) Design Tenets

* **Raw speed:** Source → hex-IR → native dispatch. No translation layers beyond the direct mapping. Optimizations are AOT (and optionally JIT) but always visible and predictable.
* **Optimized safety:** Memory is explicit and bounded through **capsules** and **leasing**; concurrency is explicit with **channels** and **workers**; errors are **capsules** with rich diagnostics.
* **Zero ambiguity:** The grammar is also the lexer+parser+AST schema. Shortcode and long-form are equivalent; both collapse to the same IR.
* **Portability & footprint:** Condensed boilerplate, short opcodes, small constant pools.
* **Observability:** **Star-Code** validations at compile time; verbose error codes/flags/warnings at runtime.

---

## 2) Two Native Source Forms (Equal in Power)

**Shortcode**: terse, machine-friendly; great for systems code and generators.
**Long-form**: self-explanatory; great for teaching, reviews, and clarity.

```eminor
# Shortcode
@main {
  #init $A0
  #load $A0, 0xFF
  #call $render, $A0
  #exit
}
```

```eminor
# Long-form (equivalent)
@entry_point {
  initialize capsule $A0
  assign value 0xFF to capsule $A0
  invoke function $render with capsule $A0
  terminate execution
}
```

Both compile to the **same** deterministic hex sequence.

---

## 3) Core Model

### Capsules (predictable packets)

* **\$A0, \$B7, …** are named capsule registers/handles (8-bit id); they hold typed data or act as references to packet data.
* **Leasing/Subleasing:** Acquire exclusive or shared rights to a capsule’s payload for bounded scopes.
* **Release:** Return rights; Star-Code ensures no double-lease/dangling releases.

### Channels & Packets

* **#send / #recv** move capsules across **channels**—separate lanes for parallelism.
* Packets are structured contents; channels coordinate ownership boundaries, not just bytes.

### Workers

* Lightweight units of parallel execution (`function`/`worker`), invoked via `#spawn` and synchronized via `#join`.

### Stamps & Durations

* **stamp** values (logical timestamps/versions) and **duration** (time in ns).
* `#stamp` and `#expire` provide lifecycle/validity boundaries.

### Errors as Capsules

* `#error $A0, <code>, "message"`—produces a rich, structured error capsule; no cryptic codes.

---

## 4) Type System

**Primitives:** `u8 u16 u32 u64`, `i8 i16 i32 i64`, `f32 f64`, `bool`, `stamp`, `duration`, `byte[N]`.
**Parameterized:** `capsule<T>`, `packet<T>` (logical content carried or referenced by capsules).
**Durations:** literal units `ns`, `ms`, `s`, `m`, `h` compile to **integer nanoseconds**.

---

## 5) Control Flow

* **Selection:** `#if (expr) { … } #else { … } #endif` (long-form keywords map equivalently).
* **Iteration:** `#loop (expr) { … }` (condition-checked at block entry).
* **Labels/Goto:** `:label` and `goto :label` exist for systems-level code; Star-Code guarantees defined targets.

**Expression precedence:**
`unary(! ~ -)` < `* / %` < `+ -` < `< > <= >=` < `== !=` < `&&` < `||`.

---

## 6) Modules, Imports, Packaging

* `@module "path"` declares a compilation unit identity.
* `@import "path" [as $alias]` and `@export $symbol` use a **netting/subnetting** protocol for linking.
* Packaging can be written **in user code**—no external manifest is required by design.

---

## 7) I/O & Rendering

* I/O is a **direct pipeline** from syntax → hex → device/OS interface.
* **Rendering** is user-driven (`#render $A0`), making the language suitable for tiny runtimes and embedded UIs.

---

## 8) Error Handling & Diagnostics

* **Capsule-based**: errors, warnings, and flags are first-class data; they’re verbose and actionable.
* **Star-Code** (AOT validation) enforces:

  * Use-before-init/let (warn)
  * Leasing discipline (double-lease -> error; sublease/release mismatches -> warn)
  * Duration sanity (non-negative ns)
  * Control-flow hygiene (undefined labels -> error)
  * Boolean conditions (non-bool literal in `#if` -> warn)

---

## 9) Concurrency & Parallelism

* **Channels** decouple throughput from latency; **workers** are spawned (`#spawn`) with capsule/constant arguments.
* `#join $T0` synchronizes; Star-Code can assert that the joined thread handle was actually spawned.

---

## 10) Optimizations (Native & Transparent)

* **Peephole**: collapses common instruction pairs to minimal sequences.
* **Inlining**: of small, pure functions; **capsule-aware** to avoid allocations.
* **Constant Folding** & **Loop Unrolling**: guided by **profile data** (PGO) gathered in dev builds.
* **Flow Flattening**: pipelines/chains become linearized opcode streams.
* **Semantic Folding**: long-form intent resolves to canonical short opcodes with trace overlays.

The **IR is the hex itself**, so optimizations preserve a 1:1 reading of “what will run.”

---

## 11) Toolchain (Reference)

* **Lexer** (megalithic): streaming, NDJSON/JSON, duration→ns, capsule tokens, directives.
* **Parser**: recursive-descent; AST as dataclasses → JSON.
* **Star-Code**: AOT validator with precise line/column diagnostics (JSON).
* **IR Emitter**: AST → **hex**/**bin** + symbol/const pools (JSON).
* **Railroad Diagrams**: Generated HTML for the full grammar (visual).
* **(Optional)** Disassembler: hex → readable mnemonics (pairs with the emitter).

---

## 12) IR Snapshot (v1.0)

Single-byte opcodes, tiny immediates. Examples:

* `INIT cap8` (0x01) — initialize capsule
* `LOAD cap8, kidx16` (0x02) — load constant into capsule
* `CALL func16` / `CALLA func16, cap8` (0x03/0x04)
* `RENDER/INPUT/OUTPUT cap8` (0x20..0x22)
* `SEND/RECV chan8, pkt8` (0x30/0x31)
* `STAMP cap8, kidx16` / `EXPIRE cap8, kidx16` (0x50/0x51)
* Expr stack: `PUSHK kidx16` (0x80), `PUSHCAP cap8` (0x82), `UNOP id` (0x90), `BINOP id` (0x91)
* Branch: `JZ rel16` (0xA0), `JMP rel16` (0xA2)
* `END` (0xFF)

**Const pool kinds:** `INT`, `HEX`, `DURATION(ns)`, `STRING`, `BOOL`.

---

## 13) Extensibility

* **Macros**: deterministic expansions into either long-form or shortcode; no runtime cost.
* **Plugins**: AOT-checked; emit well-formed opcodes or expand to E Minor source.
* **Prompt-based autocomplete**: aids authoring, but expansions always validate via Star-Code.

---

## 14) Safety & Determinism

* No undefined behavior in the core semantics.
* Memory access happens through capsules; leasing makes mutability explicit.
* Concurrency hazards are reduced via channel handoff and explicit joins.
* All control transfers (including `goto`) are validated.

---

## 15) Worked Examples

### A. Render a value

```eminor
@main {
  #init  $A0
  #load  $A0, 0x2A
  #call  $render, $A0
  #exit
}
```

### B. Timed cache with stamps/expire

```eminor
@main {
  #init $K0
  #load $K0, "session-key"
  #stamp $K0, true
  #expire $K0, 5m
  #exit
}
```

### C. Parallel render with worker

```eminor
@main {
  #spawn $render_worker, $A0
  #join  $A0
  #exit
}

function $render_worker($A0: capsule<u8>) {
  {
    #render $A0
  }
}
```

---

## 16) Pipeline in One Glance

1. **Source (short/long)**
2. **Star-Code validation** (AOT checks; can switch AOT/JIT based on environment)
3. **Capsule & symbol mapping** (zero-cost lookups)
4. **Hex IR generation** (this *is* the IR)
5. **Optimizations** (peephole, inlining, folding, unrolling, PGO)
6. **Dispatch** (native execution; channels/workers; I/O pipelines)
7. **Diagnostics** (rich errors; trace overlays)

---

## 17) Glossary

* **Capsule:** Typed, bounded memory handle; the unit of ownership/transfer.
* **Lease/Sublease/Release:** Rights discipline for capsule mutation/sharing.
* **Stamp:** Logical tag/validity bit (or version) attached to data.
* **Duration:** Time literal resolved to nanoseconds.
* **Channel:** Concurrency lane for send/receive of capsules.
* **Worker:** Concurrent function; spawned and joined explicitly.
* **Star-Code:** AOT rule system for correctness & safety.
* **Hex IR:** The executable opcode stream emitted by the compiler.

---

## 18) Why it feels fast

* Compact tokens → compact AST → *tiny* IR.
* No allocation surprises: capsules and leases make ownership explicit.
* Operators, control flow, and calls compile to tight, single-byte opcodes.
* The toolchain is “straight-through”: what you write is what runs.

---

