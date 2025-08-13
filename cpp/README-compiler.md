# E Minor — Self-Hosted Compiler (v1.0)

This is a **self-hosted compiler** for E Minor written entirely in E Minor source.
It implements: Lexer, Parser, AST builder, Star-Code validator, IR Emitter, Optimizer,
Disassembler, and a Multi-Segment Linker (TEXT/DATA/RODATA).

## Layout
- `src/compiler/` — core compiler modules
- `src/tools/` — disassembler, railroad-diagram generator
- `src/runtime/` — minimal runtime shims (render/input/output)
- `docs/` — generated artifacts (railroads, specs)

## Quick Start (conceptual)
```eminor
@main {
  #init $C
  #load $C, "src/tests/hello.eminor"
  #call $compile, $C
  #exit
}
```

## Bootstrapping
Stage 0: use a seed (your earlier Python emitter) to emit IR for `src/compiler/*.eminor`.
Stage 1: run the produced E Minor compiler on this source to self-host.
