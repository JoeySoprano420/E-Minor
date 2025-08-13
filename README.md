# E-Minor

# 🧬 Overview

E Minor is a capsule-driven, machine-native language designed for symbolic clarity, introspective debugging, and high-performance execution. It blends expressive syntax with low-level control, making it ideal for systems architects, educators, and creative technologists.

Whether you're building capsule agents, simulating environments, or teaching symbolic reasoning, E Minor offers a modular, inspectable, and extensible platform.

---

# ✨ Core Concepts

- **Capsule Encoding**  
  `$A0 → 0xA0`. Non-hex capsule names hash to stable `cap8`.

- **Const Pool (`kidx16`)**  
  Deduplicated entries for `INT`, `HEX`, `DURATION(ns)`, `STRING`, `BOOL`. See `*.sym.json`.

- **Control Flow**  
  Expressions lower to a stack machine (`PUSH*`, `BINOP`, `UNOP`). Branches use `JZ`/`JMP` with patching.

- **Symbol Resolution**  
  Functions assigned stable indices. Labels patched with relative 16-bit jumps.

---

# 🛡️ Star-Code Validator

E Minor includes a built-in validator enforcing pragmatic, extensible rules:

| Code       | Description                                                                 |
|------------|------------------------------------------------------------------------------|
| SC001–003  | Capsules/channels/packets must be `#init`’d or `let`-declared before use (warn) |
| SC010–012  | No double lease; warn on sublease/release of non-leased capsules             |
| SC020–021  | `#sleep`/`#expire` duration must be non-negative integer ns                  |
| SC030      | Warn on non-boolean literal used as `#if` condition                          |
| SC040      | `goto :label` must target a defined label (error)                            |

Validator output is precise and JSON-structured:

* .json

{
  "issues": [
    {
      "severity": "ERROR",
      "code": "SC040",
      "line": …,
      "column": …,
      "message": "…"
    }
  ]
}



## 🧪 Demo Snippet

* .eminor

@main {
  #init $A0
  #load $A0, 0xFF
  #call $render, $A0
  #if (1 < 2 && true) {
    #render $A0
  } #else {
    #exit
  } #endif
}



## E Minor
Capsule encoding: $A0 → 0xA0. Non-hex capsule names hash to a stable cap8.

Const pool (kidx16): deduped entries: INT, HEX, DURATION(ns), STRING, BOOL. See *.sym.json.

Control flow: expressions lower to stack machine (PUSH*, BINOP/UNOP), branches use JZ/JMP with patching.

Symbols: functions assigned stable indices; labels patched with relative 16-bit jumps.

Star-Code checks baked in
The validator enforces pragmatic, predictable rules (extensible):

SC001–003: Capsule/channel/packet must be #init’d or let-declared before use (warn).

SC010–012: No double lease; warn on sublease/release of non-leased.

SC020–021: #sleep/#expire duration must be non-negative integer ns.

SC030: Warn on non-boolean literal used as #if condition.

SC040: goto :label must target a defined label (error).

Output is precise, JSON-structured: {"issues":[{"severity":"ERROR", "code":"SC040", "line":…, "column":…, "message":"…"}]}.

What’s already generated (demo)
text
Copy
Edit
@main {
  #init $A0
  #load $A0, 0xFF
  #call $render, $A0
  #if (1 < 2 && true) { #render $A0 } #else { #exit } #endif
}
