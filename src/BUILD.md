# Build & Bootstrap

1) **Stage-0 seed**: Emit IR for `src/compiler/*.eminor` with your minimal seed.
2) **Stage-1 self-host**: Use the resulting compiler to rebuild itself from source.
3) **Artifacts**: `.text.hex`, `.data.hex`, `.rodata.hex`, `symbols.json`, `a.out.ir.bin`.

## Tools
- Disassembler: `src/tools/disasm.eminor` ($disassemble)
- Railroad generator: `src/tools/railroad.eminor` ($grammar_to_railroad)
