# pretty-print AST (optional)
python3 eminor_parser.py your.eminor --pretty > ast.json

# run Star-Code + emit IR (hex + bin + sym)
python3 eminor_ir_emitter.py your.eminor \
  --out-prefix build/your

# outputs:
#   build/your.ir.hex   (space-separated opcodes)
#   build/your.ir.bin   (raw bytes)
#   build/your.sym.json (const pool, func index, labels, opcode tables)
#   build/your.star.json (Star-Code issues)
