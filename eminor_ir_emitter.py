#!/usr/bin/env python3
# E Minor v1.0 — IR Emitter -> Hex Opcode Stream
# Consumes E Minor source, runs parser and Star-Code checks, and emits:
#   - .ir.hex (space-separated hex bytes)
#   - .ir.bin (raw bytes)
#   - .sym.json (symbols + constants + listing map)
# Usage:
#   python eminor_ir_emitter.py program.eminor
#   echo "@main { #exit }" | python eminor_ir_emitter.py -

import sys, json, struct, os, binascii
from typing import Dict, Any, List, Tuple

# Import parser and starcheck
try:
    import eminor_parser as parser_mod
except Exception:
    print(json.dumps({"error":"eminor_parser.py not found on sys.path"}), file=sys.stderr)
    sys.exit(1)

try:
    import eminor_starcheck as starcheck
except Exception:
    from pathlib import Path
    here = Path(__file__).parent
    sys.path.append(str(here))
    import eminor_starcheck as starcheck

# ---------------- IR Spec (opcodes) ----------------
OP = {
    "NOP":0x00,
    "INIT":0x01,
    "LOAD":0x02,         # LOAD cap, const_index(u16)
    "CALL":0x03,         # CALL func_index (u16)
    "CALLA":0x04,        # CALLA func_index (u16), cap
    "EXIT":0x05,

    "LEASE":0x10, "SUBLEASE":0x11, "RELEASE":0x12, "CHECKEXP":0x13,
    "RENDER":0x20, "INPUT":0x21, "OUTPUT":0x22,
    "SEND":0x30, "RECV":0x31,
    "SPAWN":0x40,        # SPAWN func_index(u16), argc(u8), [arg kind+payload]
    "JOIN":0x41,         # JOIN thread cap
    "STAMP":0x50, "EXPIRE":0x51, "SLEEP":0x52, "YIELD":0x53,
    "ERROR":0x60,        # ERROR cap, code_kidx(u16), msg_kidx(u16)

    "PUSHK":0x80,        # PUSH const_index(u16)
    "PUSHCAP":0x82,      # PUSH capsule value (by id byte)
    "UNOP":0x90,         # UNOP op_id(u8)
    "BINOP":0x91,        # BINOP op_id(u8)

    "JZ":0xA0, "JNZ":0xA1, "JMP":0xA2,

    "END":0xFF,
}
# Binary op ids
OPID = {
    "||":1, "&&":2,
    "==":3, "!=":4,
    "<":5, ">":6, "<=":7, ">=":8,
    "+":9, "-":10, "*":11, "/":12, "%":13,
}
UNID = {"!":1, "~":2, "u-":3}

# Encoding helpers
def u8(x): return x & 0xFF
def u16(x): return (x>>8)&0xFF, x&0xFF

def encode_capsule_id(name: str) -> int:
    # Expect hex-like names (A0, B7, FF). If not hex-like, fall back to simple hash (stable).
    try:
        if len(name)==2 and all(c in "0123456789abcdefABCDEF" for c in name):
            return int(name, 16) & 0xFF
    except Exception:
        pass
    # Stable DJB2-style hash truncated
    h=5381
    for c in name: h=((h<<5)+h)+ord(c)
    return h & 0xFF

class ConstPool:
    # kinds: INT, HEX, DURATION, STRING, BOOL
    def __init__(self):
        self.items: List[Tuple[str, Any]] = []
        self.index: Dict[Tuple[str, Any], int] = {}
    def idx(self, kind:str, value:Any) -> int:
        key=(kind, value)
        if key in self.index: return self.index[key]
        i=len(self.items)
        self.items.append(key)
        self.index[key]=i
        return i
    def json(self):
        return [{"kind":k,"value":v} for (k,v) in self.items]

class Symtab:
    # functions, labels, strings, etc.
    def __init__(self):
        self.func_index: Dict[str,int]={}
        self.labels: Dict[str,int]={}
        self.strings: Dict[str,int]={}
    def func_idx(self, name:str)->int:
        if name in self.func_index: return self.func_index[name]
        i=len(self.func_index)
        self.func_index[name]=i
        return i

class Emitter:
    def __init__(self, ast: Dict[str,Any]):
        self.ast=ast
        self.consts=ConstPool()
        self.syms=Symtab()
        self.code: List[int]=[]
        self.fixups: List[Tuple[int,str,str]]=[]  # (offset, kind, target)
        self.label_stack: List[Tuple[str,int,int]]=[]  # (break_label, continue_label, depth)

    def emit(self, b):
        if isinstance(b, int): self.code.append(b&0xFF)
        else: self.code.extend([x&0xFF for x in b])

    def here(self)->int: return len(self.code)

    def patch_rel16(self, at:int, target:int):
        rel = target - (at+2)  # branch from end of imm16
        self.code[at]   = (rel>>8)&0xFF
        self.code[at+1] = rel&0xFF

    def compile(self):
        # entry block
        entry = self.ast["entry"]
        self.compile_block(entry["block"])
        self.emit(OP["END"])
        # resolve labels/calls
        for (pos, kind, target) in self.fixups:
            if kind=="label":
                if target not in self.syms.labels: raise RuntimeError(f"Undefined label :{target}")
                self.patch_rel16(pos, self.syms.labels[target])
            elif kind=="func":
                # function indices are already immediate; nothing to patch here (we used indices not addresses)
                pass
        return bytes(self.code)

    # --- Blocks & items ---
    def compile_block(self, blk):
        for item in blk["items"]:
            t=item["_type"]
            if t.endswith("Decl"):
                self.compile_decl(item)
            else:
                self.compile_stmt(item)

    def compile_decl(self, decl):
        t=decl["_type"]
        if t=="FunctionDecl":
            name = decl["name"]["name"]
            idx = self.syms.func_idx(name)
            # for v1, we inline function bodies after END? Keep simple: treat as stub; callable index only (no body)
            # Future: store body offsets in sym.json for AOT link.
            pass
        elif t=="WorkerDecl":
            name = decl["name"]["name"]
            self.syms.func_idx(name)
        elif t=="LabelStmt":
            nm=decl["name"]
            self.syms.labels[nm] = self.here()
        else:
            # let/module/export/import — no direct code emission
            pass

    # --- Statements ---
    def compile_stmt(self, s):
        t=s["_type"]
        if t=="LabelStmt":
            self.syms.labels[s["name"]] = self.here(); return
        if t=="InitStmt":
            cap = encode_capsule_id(s["target"]["name"])
            self.emit([OP["INIT"], cap]); return
        if t=="LoadStmt":
            cap = encode_capsule_id(s["target"]["name"])
            kidx = self.compile_value(s["value"])
            self.emit([OP["LOAD"], cap] + list(u16(kidx))); return
        if t=="CallStmt":
            fidx = self.syms.func_idx(s["func"]["name"])
            if s.get("arg"):
                cap = encode_capsule_id(s["arg"]["name"])
                self.emit([OP["CALLA"]] + list(u16(fidx)) + [cap])
            else:
                self.emit([OP["CALL"]] + list(u16(fidx)))
            return
        if t=="ExitStmt": self.emit(OP["EXIT"]); return
        if t=="LeaseStmt": self.emit([OP["LEASE"], encode_capsule_id(s["target"]["name"])]); return
        if t=="SubleaseStmt": self.emit([OP["SUBLEASE"], encode_capsule_id(s["target"]["name"])]); return
        if t=="ReleaseStmt": self.emit([OP["RELEASE"], encode_capsule_id(s["target"]["name"])]); return
        if t=="CheckExpStmt": self.emit([OP["CHECKEXP"], encode_capsule_id(s["target"]["name"])]); return
        if t=="RenderStmt": self.emit([OP["RENDER"], encode_capsule_id(s["target"]["name"])]); return
        if t=="InputStmt":  self.emit([OP["INPUT"],  encode_capsule_id(s["target"]["name"])]); return
        if t=="OutputStmt": self.emit([OP["OUTPUT"], encode_capsule_id(s["target"]["name"])]); return
        if t=="SendStmt":
            a=encode_capsule_id(s["chan"]["name"]); b=encode_capsule_id(s["pkt"]["name"])
            self.emit([OP["SEND"], a, b]); return
        if t=="RecvStmt":
            a=encode_capsule_id(s["chan"]["name"]); b=encode_capsule_id(s["pkt"]["name"])
            self.emit([OP["RECV"], a, b]); return
        if t=="SpawnStmt":
            fidx = self.syms.func_idx(s["func"]["name"])
            args = s["args"] or []
            self.emit([OP["SPAWN"]] + list(u16(fidx)) + [len(args)&0xFF])
            for a in args:
                if a["_type"]=="Literal":
                    kidx = self.compile_value(a)
                    self.emit([0x01] + list(u16(kidx)))  # kind tag 0x01 = const index
                elif a["_type"]=="Identifier" and a.get("is_dollar"):
                    self.emit([0x02, encode_capsule_id(a["name"])])     # kind tag 0x02 = capsule
                else:
                    # expression: emit evaluated value to const pool? For now not supported in spawn args
                    kidx = self.compile_value(a) if a["_type"]=="Literal" else self.consts.idx("STRING","<expr>")
                    self.emit([0x01] + list(u16(kidx)))
            return
        if t=="JoinStmt":
            self.emit([OP["JOIN"], encode_capsule_id(s["thread"]["name"])]); return
        if t=="StampStmt":
            cap=encode_capsule_id(s["target"]["name"]); kidx=self.compile_value(s["value"])
            self.emit([OP["STAMP"], cap] + list(u16(kidx))); return
        if t=="ExpireStmt":
            cap=encode_capsule_id(s["target"]["name"]); kidx=self.consts.idx("DURATION", s["duration"]["value"])
            self.emit([OP["EXPIRE"], cap] + list(u16(kidx))); return
        if t=="SleepStmt":
            kidx=self.consts.idx("DURATION", s["duration"]["value"])
            self.emit([OP["SLEEP"]] + list(u16(kidx))); return
        if t=="YieldStmt": self.emit(OP["YIELD"]); return
        if t=="ErrorStmt":
            cap=encode_capsule_id(s["target"]["name"])
            cidx=self.compile_value(s["code"])
            midx=self.consts.idx("STRING", s["message"]["value"])
            self.emit([OP["ERROR"], cap] + list(u16(cidx)) + list(u16(midx))); return
        if t=="IfStmt":
            self.compile_expr(s["cond"])
            self.emit(OP["JZ"])
            jz_at = self.here()
            self.emit([0x00,0x00])  # rel16 placeholder
            self.compile_block(s["then_block"])
            self.emit(OP["JMP"])
            jmp_at = self.here()
            self.emit([0x00,0x00])
            else_target = self.here()
            self.patch_rel16(jz_at, else_target)
            if s.get("else_block"):
                self.compile_block(s["else_block"])
            end_target = self.here()
            self.patch_rel16(jmp_at, end_target)
            return
        if t=="LoopStmt":
            start = self.here()
            self.compile_expr(s["cond"])
            self.emit(OP["JZ"]); jz_at = self.here(); self.emit([0x00,0x00])
            self.compile_block(s["body"])
            self.emit(OP["JMP"]); back_at=self.here(); self.emit([0x00,0x00])
            self.patch_rel16(back_at, start)
            end = self.here()
            self.patch_rel16(jz_at, end)
            return
        if t=="GotoStmt":
            self.emit(OP["JMP"])
            at=self.here(); self.emit([0x00,0x00])
            self.fixups.append((at, "label", s["label"]))
            return

        raise RuntimeError(f"Unhandled stmt type {t}")

    # --- Expressions ---
    def compile_expr(self, e):
        t=e["_type"]
        if t=="Literal":
            kidx=self.consts.idx(e["kind"], e["value"])
            self.emit([OP["PUSHK"]] + list(u16(kidx)))
            return
        if t=="Identifier":
            if e.get("is_dollar"):
                self.emit([OP["PUSHCAP"], encode_capsule_id(e["name"])])
            else:
                # plain ident -> treat as string const
                kidx=self.consts.idx("STRING", e["name"])
                self.emit([OP["PUSHK"]] + list(u16(kidx)))
            return
        if t=="UnaryOp":
            self.compile_expr(e["rhs"])
            self.emit([OP["UNOP"], UNID[e["op"]]])
            return
        if t=="BinaryOp":
            self.compile_expr(e["lhs"]); self.compile_expr(e["rhs"])
            self.emit([OP["BINOP"], OPID[e["op"]]])
            return
        raise RuntimeError(f"Unhandled expr node {t}")

    def compile_value(self, v)->int:
        if v["_type"]=="Literal":
            return self.consts.idx(v["kind"], v["value"])
        # attempt to fold simple identifiers as strings
        if v["_type"]=="Identifier":
            if v.get("is_dollar"):  # cannot constant-fold capsules
                return self.consts.idx("STRING", f"${v['name']}")
            else:
                return self.consts.idx("STRING", v["name"])
        # Fallback: serialize expression to string for const pool (debug aid)
        return self.consts.idx("STRING","<expr>")

def ast_from_source(src: str) -> Dict[str,Any]:
    ast_json = parser_mod.parse_source_to_ast_json(src)
    return ast_json

def encode_hex(bs: bytes) -> str:
    return " ".join(f"{b:02X}" for b in bs)

def main():
    import argparse, pathlib
    ap = argparse.ArgumentParser(description="E Minor v1.0 IR Emitter")
    ap.add_argument("file", help="source file path or '-' for stdin")
    ap.add_argument("--no-starcheck", action="store_true")
    ap.add_argument("--out-prefix", default=None, help="prefix for outputs (default: input basename)")
    args = ap.parse_args()

    if args.file == "-":
        src = sys.stdin.read()
        prefix = args.out_prefix or "stdin"
    else:
        with open(args.file, "r", encoding="utf-8") as f: src=f.read()
        base = os.path.basename(args.file)
        prefix = args.out_prefix or os.path.splitext(base)[0]

    ast = ast_from_source(src)

    if not args.no_starcheck:
        issues = starcheck.validate(ast)
        has_err = any(i["severity"]=="ERROR" for i in issues)
        with open(prefix+".star.json","w",encoding="utf-8") as f:
            json.dump({"issues":issues}, f, indent=2)
        if has_err:
            print(json.dumps({"error":"Star-Code validation failed","issues":issues}, indent=2), file=sys.stderr)
            sys.exit(2)

    emitter = Emitter(ast)
    code = emitter.compile()
    hexs = encode_hex(code)

    with open(prefix+".ir.hex","w",encoding="utf-8") as f: f.write(hexs+"\n")
    with open(prefix+".ir.bin","wb") as f: f.write(code)
    with open(prefix+".sym.json","w",encoding="utf-8") as f:
        json.dump({
            "const_pool": emitter.consts.json(),
            "func_index": emitter.syms.func_index,
            "labels": emitter.syms.labels,
            "opcodes": OP,
            "binops": OPID,
            "unops": UNID,
        }, f, indent=2)

    print(json.dumps({
        "ok": True,
        "bytes": len(code),
        "hex_path": prefix+".ir.hex",
        "bin_path": prefix+".ir.bin",
        "sym_path": prefix+".sym.json",
        "star_path": None if args.no_starcheck else prefix+".star.json"
    }, indent=2))

if __name__ == "__main__":
    main()
