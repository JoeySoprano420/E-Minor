# E-Minor
E Minor
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
