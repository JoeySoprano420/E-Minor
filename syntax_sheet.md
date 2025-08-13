# E Minor v1.0 – Complete Syntax Sheet

## 0) File & Program Skeleton

```eminor
@main {                         // or: @entry_point
  #init $A0
  #load $A0, 0xFF
  #call $render, $A0
  #exit
}
```

* Exactly one **entry block** per program: `@main { … }` (alias: `@entry_point { … }`).
* Additional blocks allowed (e.g., library functions, channel workers).

---

## 1) Lexical Structure

### 1.1 Character Set & Encoding

* Source is UTF-8; identifiers use ASCII letters, digits, `_` (no spaces).

### 1.2 Whitespace & Newlines

* Insignificant except as token separators. Newlines can end statements *only* when unambiguous.

### 1.3 Comments

```eminor
// single-line comment
/* block
   comment */
```

### 1.4 Identifiers

```
identifier := [A-Za-z] [A-Za-z0-9_]*
capsule_id := "$" identifier       // e.g., $A0, $buffer, $tmp1
func_id    := "$" identifier       // e.g., $render, $hash
label_id   := ":" identifier       // for branch targets (optional)
```

### 1.5 Literals

```
hex  := 0x[0-9A-Fa-f]+             // e.g., 0x00, 0xFF, 0xDEADBEEF
int  := [0-9]+                     // e.g., 0, 42, 65535
str  := " ... "                    // backslash escapes: \n \t \" \\ \xHH
bool := true | false
dur  := <int><unit>                // 10ms, 3s, 5m, 2h  (duration literal)
```

---

## 2) Keywords & Built-ins

### 2.1 Entry & Structure

```
@main            @entry_point
```

### 2.2 Long-Form Superlatives (readable)

```
initialize capsule
assign value <v> to capsule <c>
invoke function <f> with capsule <c>
terminate execution
```

### 2.3 Shortcode (machine-close)

```
#init   #load     #call    #exit
#lease  #sublease #release #check_exp
#render #input    #output
#send   #recv     #spawn   #join
#stamp  #expire   #sleep   #yield
#if     #else     #endif   #loop   #break   #continue
```

> Notes
> • `#if/#else/#endif` are statement-form conditionals (not preprocessor).
> • Long-form and shortcode may mix in one file.

---

## 3) Types & Qualifiers

### 3.1 Primitives

```
u8 u16 u32 u64     i8 i16 i32 i64
f32 f64            bool
stamp              duration
byte[N]            // fixed-size buffer
capsule<T>         // typed capsule
packet<T>          // stream unit
```

### 3.2 Qualifiers (modifiers)

```
const   // read-only view
owned   // exclusive ownership
shared  // multi-reader
volatile// device/port mapped
```

### 3.3 Annotations (optional metadata)

```
@align(16)  @packed   @hot   @cold  @inline  @noinline
```

---

## 4) Operators & Precedence

### 4.1 Precedence (high → low)

```
1)  ()  []  .                      // call, index, member
2)  !  ~  - (unary)                // logical not, bit not, neg
3)  *  /  %                        // arithmetic
4)  +  -                           // arithmetic
5)  << >>                          // shifts
6)  &                              // bitwise and
7)  ^                              // bitwise xor
8)  |                              // bitwise or
9)  == != < > <= >=                // comparisons
10) &&                             // logical and
11) ||                             // logical or
```

### 4.2 Examples

```eminor
#load $A0, (4 + 2) * 8
#if ($flag && ($x < 0x10)) { ... } #endif
```

---

## 5) Declarations

### 5.1 Function

```eminor
function $render($in: capsule<u8>) : void {
  #render $in
}
```

* Return type `void` implied if omitted.
* Parameters are typed capsules or primitives.

### 5.2 Capsule & Packet

```eminor
let $buf: capsule<byte[256]>;
let $p  : packet<u8>;
```

### 5.3 Channel Worker (concurrency)

```eminor
worker $pump($in: capsule<byte[256]>, $out: capsule<byte[256]>) {
  #loop ($in != null) {
    #recv $in, $p
    #send $out, $p
  }
}
```

---

## 6) Statements

### 6.1 Initialization & Load

```eminor
#init  $A0                      // allocate/map capsule
#load  $A0, 0xFF               // load literal into capsule
#lease $A0                      // exclusive lease
#sublease $A0                   // shared non-exclusive lease
#release $A0                    // release ownership
#check_exp $A0                  // check expiration flag
```

**Long-form equivalents**

```
initialize capsule $A0
assign value 0xFF to capsule $A0
```

### 6.2 Calls & Exit

```eminor
#call $render, $A0
#exit
```

**Long-form**

```
invoke function $render with capsule $A0
terminate execution
```

### 6.3 Control Flow

```eminor
#if   (<expr>) { ... } #else { ... } #endif
#loop (<expr>) { ... }               // while-style loop
#break
#continue
```

* `<expr>` is any boolean-yielding expression (comparison or bool).

### 6.4 Branch Labels (optional)

```eminor
:retry
#call $try_io, $A0
#if (!$ok) { goto :retry } #endif
```

* `goto :label` allowed within the same block scope.

### 6.5 Concurrency & Channels

```eminor
#spawn $worker_fn, $arg0, $arg1    // returns thread stamp
#join  $thread_stamp

#send $chan, $packet
#recv $chan, $packet

#yield                             // cooperative yield
#sleep 5ms                         // duration literal
```

### 6.6 Time & Stamps

```eminor
#stamp  $A0, 0xDEAD                // attach stamp
#expire $A0, 500ms                 // set expiration
```

### 6.7 I/O & Rendering

```eminor
#input  $A0                        // read into capsule
#output $A0                        // write from capsule
#render $A0                        // draw/present capsule
```

---

## 7) Modules, Imports/Exports (Netting/Subnetting)

### 7.1 Module Header (optional)

```eminor
@module "graphics.render"
@export $render
@export function $blend
```

### 7.2 Import

```eminor
@import "net:graphics/render:$blend" as $blend
@import "net:io/pipeline:$pump"
```

* **Scheme**: `net:<domain>/<subnet>:$symbol`
* Can import functions, workers, or constants.

---

## 8) Errors & Diagnostics (Capsules)

### 8.1 Error Capsule

```eminor
let $E: capsule<u32>;
#error $E, 0x01, "invalid state"   // sets code + attaches message stamp
#if ($E != 0) { #exit } #endif
```

* Error opcodes produce verbose flags and attach a message stamp.

---

## 9) Long-Form ↔ Shortcode ↔ Hex (Core)

| Superlative                              | Shortcode                              | Hex       |
| ---------------------------------------- | -------------------------------------- | --------- |
| initialize capsule `<c>`                 | `#init <c>`                            | 0x01      |
| assign value `<v>` to capsule `<c>`      | `#load <c>, <v>`                       | 0x02      |
| invoke function `<f>` with capsule `<c>` | `#call <f>, <c>`                       | 0x03      |
| terminate execution                      | `#exit`                                | 0xFF      |
| loop `<cond>` …                          | `#loop (<cond>) { … }`                 | 0x20      |
| if `<cond>` … else …                     | `#if (<cond>){…}#else{…}`              | 0x21/0x22 |
| compare equal                            | `==`                                   | 0x30      |
| compare not equal                        | `!=`                                   | 0x31      |
| compare <, >, <=, >=                     | `<  >  <=  >=`                         | 0x32–0x35 |
| lease/sublease/release/check\_exp        | `#lease/#sublease/#release/#check_exp` | 0x40–0x43 |
| render / input / output                  | `#render/#input/#output`               | 0x50–0x52 |
| send / recv / spawn / join               | `#send/#recv/#spawn/#join`             | 0x60–0x63 |
| stamp / expire / sleep / yield           | `#stamp/#expire/#sleep/#yield`         | 0x70–0x73 |
| error                                    | `#error <cap>, code, "msg"`            | 0x7F      |

> Hex opcodes accept trailing operands in canonical order: instruction byte(s) → operand bytes (e.g., `0x02 A0 FF` for `#load $A0, 0xFF`).

---

## 10) Grammar Snippets (EBNF-style)

### 10.1 Top Level

```
program      := entry_block , { decl | statement } ;
entry_block  := "@" ( "main" | "entry_point" ) block ;
block        := "{" { decl | statement } "}" ;
decl         := func_decl | worker_decl | let_decl | module_decl | export_decl | import_decl ;
```

### 10.2 Declarations

```
func_decl    := "function" func_id "(" [ param_list ] ")" [ ":" type ] block ;
worker_decl  := "worker" func_id "(" [ param_list ] ")" block ;
let_decl     := "let" capsule_id ":" type ";" ;
param_list   := param { "," param } ;
param        := capsule_id ":" type ;
type         := prim_type | "capsule" "<" type ">" | "packet" "<" type ">" | "byte" "[" int "]" ;
prim_type    := "u8"|"u16"|"u32"|"u64"|"i8"|"i16"|"i32"|"i64"|"f32"|"f64"|"bool"|"stamp"|"duration" ;
module_decl  := "@module" str ;
export_decl  := "@export" ( func_id | "function" func_id ) ;
import_decl  := "@import" str [ "as" func_id ] ;
```

### 10.3 Statements

```
statement    := init | load | call | exit | lease | sublease | release | checkexp
              | render | input | output | send | recv | spawn | join
              | stamp | expire | sleep | yield | error_stmt
              | if_stmt | loop_stmt | break_stmt | continue_stmt | goto_stmt
              | label ;
label        := ":" identifier ;
goto_stmt    := "goto" ":" identifier ;
init         := "#init"  capsule_id ;
load         := "#load"  capsule_id "," value ;
call         := "#call"  func_id [ "," capsule_id ] ;
exit         := "#exit" ;
lease        := "#lease" capsule_id ;
sublease     := "#sublease" capsule_id ;
release      := "#release" capsule_id ;
checkexp     := "#check_exp" capsule_id ;
render       := "#render" capsule_id ;
input        := "#input"  capsule_id ;
output       := "#output" capsule_id ;
send         := "#send"   capsule_id "," capsule_id ;   // chan, packet
recv         := "#recv"   capsule_id "," capsule_id ;   // chan, packet
spawn        := "#spawn"  func_id [ "," arg_list ] ;
join         := "#join"   capsule_id ;                  // thread stamp
stamp        := "#stamp"  capsule_id "," value ;
expire       := "#expire" capsule_id "," duration ;
sleep        := "#sleep"  duration ;
yield        := "#yield" ;
error_stmt   := "#error"  capsule_id "," value "," str ;
if_stmt      := "#if" "(" expr ")" block [ "#else" block ] "#endif" ;
loop_stmt    := "#loop" "(" expr ")" block ;
break_stmt   := "#break" ;
continue_stmt:= "#continue" ;
```

### 10.4 Expressions

```
expr         := primary { op primary } ;
primary      := value | capsule_id | "(" expr ")" ;
value        := hex | int | str | bool ;
op           := "||" | "&&" | "==" | "!=" | "<" | ">" | "<=" | ">=" | "|" | "^" | "&" | "<<" | ">>" | "+" | "-" | "*" | "/" | "%" ;
```

---

## 11) Optimization Directives (semantic, not syntax)

* **Peephole**: fold `#init; #load` into combined emission where legal.
* **Constant Folding**: evaluate literal arithmetic/logic at AOT.
* **Loop Unrolling**: unroll small, static trip counts (≤16).
* **Inlining**: inline leaf functions marked `@inline` or PGO-hot.
* **Capsule-aware**: prefer register-mapping for `capsule<u8/u16/u32/u64>`; avoid heap.
* **Flow Flattening**: remove redundant branches after folding.
* **Profile-Guided (PGO)**: reorder blocks ≈ hot paths; specialize call sites.

---

## 12) Worked Mini-Examples

### 12.1 Long-form ↔ Shortcode

```eminor
@entry_point {
  initialize capsule $A0
  assign value 0xFF to capsule $A0
  invoke function $render with capsule $A0
  terminate execution
}
```

```eminor
@main {
  #init $A0
  #load $A0, 0xFF
  #call $render, $A0
  #exit
}
```

### 12.2 Channel Worker

```eminor
worker $echo($in: capsule<byte[64]>, $out: capsule<byte[64]>) {
  #loop (true) {
    #recv  $in,  $p
    #send  $out, $p
    #yield
  }
}
```

### 12.3 Timed Expiration

```eminor
#init $token
#stamp $token, 0xC0DE
#expire $token, 2s
#check_exp $token
```

---

## 13) Reserved & Future

* Reserved keywords: `switch`, `case`, `for`, `match`, `defer` (not active in v1.0).
* All opcodes `0x80–0x8F` reserved for GPU/HexStream bridges; `0x90–0x9F` for net-subnet transports.

---

### Quick Reference (one-liner)

* **Entry**: `@main { … }`
* **Capsule**: `#init $C`; `#load $C, <lit>`; `#lease/#sublease/#release`
* **Call**: `#call $fn, $arg`; **Exit**: `#exit`
* **Flow**: `#if (e){..}#else{..}#endif`, `#loop (e){..}`, `#break/#continue`
* **I/O**: `#input/#output/#render $C`
* **Chan**: `#spawn/#join`, `#send/#recv`, `#yield/#sleep`
* **Time/ID**: `#stamp/#expire/#check_exp`
* **Error**: `#error $E, code, "msg"`

---

Want this turned into a **printable tri-fold cheat sheet** or a **poster-style PDF** (with tables and code samples on one page)? I can generate that immediately.
