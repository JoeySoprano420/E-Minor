# E Minor v1.0 — Formal Semantics

## 1) Execution Model

**Program root.** Exactly one entry block: `@main {…}` (alias: `@entry_point`). Program execution begins at the first instruction in that block.

**Phases (conceptual):**

1. **Intake** → build fused parse/AST (long-form + shortcode mixed).
2. **Star Code** validation (AOT). If any section depends on runtime inputs (e.g., environment, profile), the compiler **may** JIT-compile those blocks on first execution.
3. **IR emission** → **hex-opcode stream** (final, executable form).
4. **Optimizations** → semantically preserving only (see §14).
5. **Dispatch** → sequential execution on the main channel unless redirected by control flow/concurrency ops.

**Determinism.** A single thread/channel executes instructions in **program order**. Concurrency introduces controlled nondeterminism; sequencing edges are defined by channel ops and joins (§9).

**Time base.** Durations are measured in **nanoseconds** (signed 64-bit). Implementation **must** map `ms`, `s`, `m`, `h` to integers in ns with overflow detection (error capsule, §11).

---

## 2) Types & Values

**Primitives.**

* Integers: `u8/u16/u32/u64`, `i8/i16/i32/i64` (two’s-complement).
* Floats: `f32/f64` (IEEE-754).
* `bool` ∈ { `false` (=0), `true` (=1) }.
* `stamp`: opaque 64-bit identity/label (no arithmetic; comparable for equality).
* `duration`: signed 64-bit ns.
* `byte[N]`: fixed-size buffer (N > 0), contiguous.

**Capsule<T>.** A **handle** to storage containing a T (or buffer/payload). A capsule has **identity**, **lifetime**, **ownership state**, and optional **expiration** & **stamps** (§6–§8, §12).

**Packets.** `packet<T>` is a move-only message container used by channels; send/recv transfers ownership (§9).

**Conversions.**

* Integer → larger integer: zero/sign extend by source signedness.
* Integer ↔ float: IEEE-754; out-of-range is **implementation-defined** (ID).
* Boolean context: zero = false, nonzero = true.
* No implicit narrowing. Narrowing requires explicit cast (future reserved).

---

## 3) Expression Semantics

**Evaluation order.** **Left-to-right** with full sequencing between operands.
**Short-circuit:** `&&`, `||` short-circuit left-to-right.
**Comparisons:** yield `bool`. Unsigned vs signed follows operand types; mixed signedness is **ill-formed** (Star Code error) unless types are explicitly matched.
**Overflow:**

* Unsigned overflow wraps (mod 2^width).
* Signed overflow is **undefined behavior (UB)**. Compilers may assume no signed overflow for optimization.
  **Division by zero:** UB for integers; `f32/f64` follow IEEE (Inf/NaN).

---

## 4) Statement Semantics (Core)

* `#init $C` → allocate/map storage for `$C`; `$C` enters **uninitialized** state unless immediately loaded; reading uninitialized is UB.
* `#load $C, V` → write literal/constant `V` into `$C` (initializes).
* `#call $F, $Arg?` → call site semantics (§7).
* `#exit` → terminate the entire program with status 0 unless an active error capsule is set (then non-zero; §11).

**Long-form** lines are **exact synonyms** for their shortcode counterparts; they emit the **same opcodes**.

---

## 5) Control Flow

**If.**

```
#if (E) { A } #else { B } #endif
```

Evaluate E; if true execute A else B. No implicit fallthrough. Blocks create **sequence points** before first and after last instruction.

**Loop.**

```
#loop (E) { Body }
```

Evaluate E; if true execute Body; on Body completion, re-evaluate E. `#break` exits loop; `#continue` re-evaluates E.

**Goto/labels.** Jumps are restricted to the **current block** and its nested sub-blocks; jumping **into** a block with uninitialized capsules is a Star Code error.

---

## 6) Capsule Semantics (Ownership & Lifetime)

**States:** `uninit` → `init` → (leased/subleased) → `released`.

* `#init $C` transitions to `init`.
* `#lease $C` grants **exclusive mutable** access; while leased, `$C` cannot be subleased or re-leased until released.
* `#sublease $C` grants **shared read-only** views; any active sublease forbids exclusive lease.
* `#release $C` ends ownership; subsequent use is UB unless re-`#init`ed.

**Aliasing rules (soundness):**

* At most one **exclusive** lease **or** any number of **shared** subleases at a time.
* Writes require exclusive lease.
* Reads allowed under exclusive or shared.

**Mapping.** Implementations should prefer registers for small primitives; buffers may map to stack or heap (ID). Mapping must preserve aliasing guarantees.

---

## 7) Function & Worker Calls

**Declaration:** `function $f(a: capsule<T>, b: u32) : R { … }`
**Call binding:**

* Primitive parameters: **by value**.
* `capsule<T>` parameters: **by handle** with qualifiers:

  * default: **borrowed-shared** (read-only inside callee).
  * `owned` qualifier on param implies **move** of ownership into callee; caller loses access until returned or released.
  * `const` enforces read-only regardless of lease state. (Violations are Star Code errors.)

**Return.** Single return value (or `void`). Returned capsules are **owned** by caller unless marked `borrowed`.

**Reentrancy.** Functions are reentrant unless they mutate global singletons or devices (ID). Workers are concurrent entities (§9).

---

## 8) Expiration, Stamps, Time

* `#stamp $C, S` attaches/overwrites a 64-bit `stamp` on `$C`. Stamps are metadata; they do not affect the payload.
* `#expire $C, D` sets an **absolute expiry** at `(now + D)` in ns; negative `D` is immediate expiry (Star Code warns; allowed).
* `#check_exp $C` sets a machine flag visible to conditionals: true iff current time ≥ expiry.
* Expiry does **not** deallocate. Using expired capsules is legal but typically guarded by logic.

---

## 9) Concurrency & Channels

**Spawning.** `#spawn $worker, args…` starts a worker on a new channel; returns a **thread stamp** (a `stamp`). Implementation defines mapping to OS threads vs fibers (ID) but must obey happens-before rules below.

**Join.** `#join $thr` blocks until the worker with stamp `$thr` completes. Completion **synchronizes-with** the joiner.

**Channels (send/recv).**

* `#send $chan, $pkt`: **moves** the packet’s ownership to the channel; the sender **must not** read or write `$pkt` afterwards (UB).
* `#recv $chan, $pkt`: receives the next packet, **moving** ownership into `$pkt`.
* **Happens-before:** Each successful `send` **synchronizes-with** the matching `recv`. This establishes visibility of writes that happened before `send`.

**Data race definition.** Two conflicting accesses to the same capsule (at least one write) without a happens-before relationship constitute a **data race** → **UB**. Ownership rules + send/recv + join are the portable synchronization primitives.

**Yield & Sleep.**

* `#yield` gives up the processor; no memory ordering guarantees beyond those already in place.
* `#sleep D` blocks current channel for at least D ns; no extra ordering.

---

## 10) I/O & Rendering

* `#input $C`: fills `$C` from implementation-defined input source bound to the capsule/device (ID). Completes before next instruction (program order).
* `#output $C`: writes `$C` to its bound sink (flush completes before next instruction unless buffered—buffering is ID but must be coherent on `#exit`).
* `#render $C`: presents content to the rendering target; visible effects occur **after** the instruction completes. Multi-frame presentation order is program order per channel.

Side effects from I/O **are observable** and cannot be reordered across control-dependence boundaries; across independent channels, only synchronization defines visibility.

---

## 11) Errors & Diagnostics

**Error Capsule.**

```
#error $E, code:int, "message"
```

* Sets `$E` payload to `code`, attaches message as a stamp (impl may keep side buffer).
* Once set, `$E != 0` tests true.
* `#exit` returns status **0 if all error capsules observed by main are 0;** otherwise non-zero (ID precise value; recommended: max code seen).

**Propagation.** Functions **do not** implicitly propagate errors. Convention: pass `$E` down or return an error code (library choice).

**Star Code integration.** Compile-time failures (ill-formed) stop compilation with verbose diagnostics. Warnings (e.g., negative duration) do not alter runtime semantics.

---

## 12) Imports/Exports (Netting/Subnetting)

* `@import "net:<domain>/<subnet>:$symbol" as $alias` binds `$alias` to an externally provided symbol.
* The import is resolved **at link/load time**; failure is a **link error** (not UB).
* Imported symbols must declare a signature compatible with use sites; mismatches are **ill-formed** (Star Code).

**Execution semantics.** A successfully imported function/worker behaves identically to an in-module definition at the call site.

---

## 13) IR & Opcode Semantics

**Encoding.** Each instruction is:
`[OPCODE (1B)] [OPERANDS (little-endian, canonical widths)]`

**Canonical operand widths:**

* Capsule/func IDs → 1B symbolic index (A0→0xA0 is **spec example**; real encoders map IDs to compact indices).
* Literals: minimal width sufficient to hold the constant, rounded to 1/2/4/8 bytes, tagged by the opcode form.
* Durations: 8B ns. Stamps: 8B.

**Endianness.** Little-endian for multi-byte operands.

**Undefined opcodes.** Executing an unknown opcode is **trap** → program terminates with non-zero status (implementation-specific code).

---

## 14) Star Code & AOT/JIT Switching

**Star Code (compile-time).**

* Performs grammar conformance, ownership/alias checks, reachability, definite initialization, narrowing checks, and control-flow well-formedness (no jump into uninitialized region).
* Emits **hash signatures** for validated blocks.

**AOT/JIT policy.**

* Default **AOT** for all blocks.
* **JIT** is permitted for blocks whose specialization depends on runtime profile or environment. JIT’ed code **must** preserve the validated Star Code invariants and semantic equivalence.
* AOT ↔ JIT switching points are **sequence points**.

---

## 15) Optimization Correctness (Must-Hold Invariants)

Optimizations **must not** change:

* **Observable I/O order** on a channel (except where not sequenced by program order or synchronization).
* **Error semantics** (§11).
* **Happens-before edges** from send/recv/join.
* **Ownership/aliasing** constraints.
* **Expiry, stamp** attachment/observability.

Permitted examples:

* Peephole (e.g., fold `#init`+`#load` to combined form).
* Constant folding/propagation, dead-code elimination of unreachable blocks.
* Loop unrolling where iteration count is provably bounded and side effects preserved.
* Inlining that preserves call-visible effects and error behaviors.

---

## 16) Undefined Behavior (UB) vs Implementation-Defined (ID)

**UB (non-exhaustive):**

* Read of **uninitialized** capsule payload.
* **Signed** integer overflow; division by zero (integers).
* Violating lease/sublease rules (write without exclusive lease; use after `#release`).
* Data race (conflicting accesses without happens-before).
* Using a packet after `#send`; double-receive into same packet without overwrite.
* Jumping into a block that assumes initialized state not met.

**ID (must be documented by implementation):**

* Exact mapping of capsules to registers/stack/heap.
* Float‐to‐int out-of-range conversion results.
* Threading model (OS threads vs fibers) and scheduling fairness.
* `#output` buffering policy & exit-flush behavior.
* Exit status code computation when multiple error capsules are set.
* Import resolution timing (link vs load), symbol visibility scope.

---

## 17) Security & Safety Guarantees

* **No implicit aliasing** beyond lease rules.
* **Send/recv** are ownership-transfer; receivers cannot observe sender after transfer except via further messages.
* **Star Code** proves definite initialization on all reachable paths; ill-formed binaries **must not** be produced.
* **Expired** capsules are ordinary values with a flag; using them is safe (semantics up to user logic).

---

## 18) Semantic Traces (Worked Mini-Examples)

**A. Straight-line**

```
#init $A0           // $A0: uninit → init
#load $A0, 0xFF     // write 0xFF
#call $render, $A0  // read $A0, render
#exit               // exit(0)
```

Observable effects (program order): `$A0:=0xFF` → render(0xFF) → exit 0.

**B. If/Else (short-circuit)**

```
#load $f, 0         // false
#if ($f && expensive()) { … } #else { #output $log } #endif
```

`expensive()` **not** called; `$log` output happens.

**C. Channel H-B edge**

```
#send $ch, $pkt     // move pkt → ch
#recv $ch, $pkt2    // in another worker
```

All writes to `$pkt` **before** `#send` are visible **after** the matching `#recv`.

**D. Lease violation (UB)**

```
#lease $B
#sublease $B        // Star Code error (reject): cannot sublease while exclusive
```

**E. Expiry**

```
#expire $tok, 2s
#sleep 3s
#check_exp $tok     // true
```

---

## 19) Compatibility & Future-Proofing

* Opcodes `0x80–0x8F` reserved for GPU/HexStream; `0x90–0x9F` for net/subnet transports. Implementations must treat unknown reserved opcodes as trap.
* Keywords `switch/for/match/defer` reserved for v1.x extensions.
* Binary format includes a **version byte**; loaders must reject mismatches.

---

## 20) Compliance Checklist (for implementers)

* [ ] Enforce L→R expression evaluation + short-circuit.
* [ ] UB/ID behaviors implemented per spec.
* [ ] Star Code: init-def, ownership, narrowing, CFG checks.
* [ ] Channel send/recv and join create happens-before edges.
* [ ] I/O ordering per channel; flush policy documented.
* [ ] AOT/JIT switching preserves sequence points + invariants.
* [ ] Optimizations proven semantics-preserving (tests included).

---

