#!/usr/bin/env python3
# E Minor v1.0 — Full-Language Parser (recursive descent)
# Consumes tokens from eminor_lexer[._megalithic] and emits AST JSON.
# Usage:
#   python eminor_parser.py <file> [--pretty]
#   echo "@main { #exit }" | python eminor_parser.py - --pretty

import sys, json
from dataclasses import dataclass, field
from typing import List, Optional, Union, Any

# Import the lexer (expect eminor_lexer.py in same directory)
try:
    import eminor_lexer as lex
except Exception:
    import eminor_lexer_megalithic as lex

# --------------- AST Nodes ---------------

@dataclass
class Node:
    line: int
    column: int
    def to_json(self) -> dict:
        d = {"_type": self.__class__.__name__}
        for k, v in self.__dict__.items():
            if k in ("line","column"): d[k]=v
            else: d[k]=_to_json(v)
        return d

def _to_json(v: Any) -> Any:
    if isinstance(v, Node):
        return v.to_json()
    if isinstance(v, list):
        return [_to_json(x) for x in v]
    if isinstance(v, dict):
        return {k: _to_json(val) for k, val in v.items()}
    return v

# Expr
@dataclass
class Expr(Node): pass

@dataclass
class Literal(Expr):
    kind: str
    value: Any

@dataclass
class Identifier(Expr):
    name: str
    is_dollar: bool = False

@dataclass
class UnaryOp(Expr):
    op: str
    rhs: Expr

@dataclass
class BinaryOp(Expr):
    op: str
    lhs: Expr
    rhs: Expr

# Program / Blocks
@dataclass
class Program(Node):
    entry: "EntryBlock"
    items: List[Union["Decl","Stmt"]] = field(default_factory=list)

@dataclass
class EntryBlock(Node):
    kind: str
    block: "Block"

@dataclass
class Block(Node):
    items: List[Union["Decl","Stmt"]]

# Declarations
@dataclass
class Decl(Node): pass

@dataclass
class FunctionDecl(Decl):
    name: Identifier
    params: List["Param"]
    return_type: Optional["TypeRef"]
    body: Block

@dataclass
class WorkerDecl(Decl):
    name: Identifier
    params: List["Param"]
    body: Block

@dataclass
class LetDecl(Decl):
    name: Identifier
    type_ref: "TypeRef"

@dataclass
class ModuleDecl(Decl):
    path: str

@dataclass
class ExportDecl(Decl):
    symbol: Identifier

@dataclass
class ImportDecl(Decl):
    path: str
    alias: Optional[Identifier]

@dataclass
class Param(Node):
    name: Identifier
    type_ref: "TypeRef"

@dataclass
class TypeRef(Node):
    kind: str
    name: Optional[str] = None
    inner: Optional["TypeRef"] = None
    size: Optional[int] = None

# Statements
@dataclass
class Stmt(Node): pass

@dataclass
class InitStmt(Stmt):      target: Identifier
@dataclass
class LoadStmt(Stmt):      target: Identifier; value: Expr
@dataclass
class CallStmt(Stmt):      func: Identifier; arg: Optional[Identifier]
@dataclass
class ExitStmt(Stmt):      pass
@dataclass
class LeaseStmt(Stmt):     target: Identifier
@dataclass
class SubleaseStmt(Stmt):  target: Identifier
@dataclass
class ReleaseStmt(Stmt):   target: Identifier
@dataclass
class CheckExpStmt(Stmt):  target: Identifier
@dataclass
class RenderStmt(Stmt):    target: Identifier
@dataclass
class InputStmt(Stmt):     target: Identifier
@dataclass
class OutputStmt(Stmt):    target: Identifier
@dataclass
class SendStmt(Stmt):      chan: Identifier; pkt: Identifier
@dataclass
class RecvStmt(Stmt):      chan: Identifier; pkt: Identifier
@dataclass
class SpawnStmt(Stmt):     func: Identifier; args: List[Union[Expr, Identifier]]
@dataclass
class JoinStmt(Stmt):      thread: Identifier
@dataclass
class StampStmt(Stmt):     target: Identifier; value: Expr
@dataclass
class ExpireStmt(Stmt):    target: Identifier; duration: Literal
@dataclass
class SleepStmt(Stmt):     duration: Literal
@dataclass
class YieldStmt(Stmt):     pass
@dataclass
class ErrorStmt(Stmt):     target: Identifier; code: Expr; message: Literal
@dataclass
class IfStmt(Stmt):        cond: Expr; then_block: Block; else_block: Optional[Block]
@dataclass
class LoopStmt(Stmt):      cond: Expr; body: Block
@dataclass
class BreakStmt(Stmt):     pass
@dataclass
class ContinueStmt(Stmt):  pass
@dataclass
class GotoStmt(Stmt):      label: str
@dataclass
class LabelStmt(Stmt):     name: str

# --------------- Parser ---------------

class ParserError(Exception): pass

class Parser:
    def __init__(self, tokens: List[lex.Token]):
        self.toks = tokens
        self.i = 0

    def _eof(self) -> bool:
        return self.i >= len(self.toks)
    def _peek(self, k=0):
        j = self.i + k
        return self.toks[j] if j < len(self.toks) else None
    def _advance(self):
        t = self._peek()
        if t is None: raise ParserError("Unexpected end of input")
        self.i += 1
        return t
    def _match_kind(self, *kinds):
        t = self._peek()
        if t and t.kind in kinds:
            return self._advance()
        return None
    def _expect(self, *kinds):
        t = self._peek()
        if not t or t.kind not in kinds:
            exp = " or ".join(kinds)
            got = (t.kind if t else "EOF")
            loc = f" at {t.line}:{t.column}" if t else ""
            raise ParserError(f"Expected {exp} but got {got}{loc}")
        return self._advance()

    # program
    def parse_program(self) -> Program:
        entry = self.parse_entry_block()
        items = []
        while not self._eof():
            t = self._peek()
            if t.kind in ("KW_FUNCTION","KW_WORKER","KW_LET","AT_MODULE","AT_EXPORT","AT_IMPORT"):
                items.append(self.parse_decl())
            else:
                items.append(self.parse_statement())
        return Program(line=entry.line, column=entry.column, entry=entry, items=items)

    def parse_entry_block(self) -> EntryBlock:
        t = self._expect("AT_MAIN","AT_ENTRY_POINT")
        blk = self.parse_block()
        return EntryBlock(line=t.line, column=t.column, kind=t.kind, block=blk)

    def parse_block(self) -> Block:
        lb = self._expect("LBRACE")
        items = []
        while True:
            t = self._peek()
            if not t: raise ParserError(f"Unterminated block starting at {lb.line}:{lb.column}")
            if t.kind == "RBRACE":
                self._advance(); break
            if t.kind in ("KW_FUNCTION","KW_WORKER","KW_LET","AT_MODULE","AT_EXPORT","AT_IMPORT"):
                items.append(self.parse_decl())
            else:
                items.append(self.parse_statement())
        return Block(line=lb.line, column=lb.column, items=items)

    # decls
    def parse_decl(self) -> Decl:
        t = self._peek()
        if t.kind == "KW_FUNCTION": return self.parse_function_decl()
        if t.kind == "KW_WORKER":   return self.parse_worker_decl()
        if t.kind == "KW_LET":      return self.parse_let_decl()
        if t.kind == "AT_MODULE":
            at=self._advance(); s=self._expect("STRING")
            return ModuleDecl(line=at.line, column=at.column, path=s.value)
        if t.kind == "AT_EXPORT":
            at=self._advance()
            if self._match_kind("KW_FUNCTION"):
                pass
            sym = self.parse_func_id()
            return ExportDecl(line=at.line, column=at.column, symbol=sym)
        if t.kind == "AT_IMPORT":
            at=self._advance(); s=self._expect("STRING")
            alias=None
            if self._peek() and self._peek().kind=="IDENT" and self._peek().lexeme=="as":
                self._advance()
                alias=self.parse_func_id()
            return ImportDecl(line=at.line, column=at.column, path=s.value, alias=alias)
        raise ParserError(f"Unknown declaration start: {t.kind} at {t.line}:{t.column}")

    def parse_function_decl(self) -> FunctionDecl:
        kw=self._expect("KW_FUNCTION")
        name=self.parse_func_id()
        self._expect("LPAREN")
        params=[]
        if not self._match_kind("RPAREN"):
            params.append(self.parse_param())
            while self._match_kind("COMMA"):
                params.append(self.parse_param())
            self._expect("RPAREN")
        ret_type=None
        if self._match_kind("COLON"):
            ret_type=self.parse_type()
        body=self.parse_block()
        return FunctionDecl(line=kw.line, column=kw.column, name=name, params=params, return_type=ret_type, body=body)

    def parse_worker_decl(self) -> WorkerDecl:
        kw=self._expect("KW_WORKER")
        name=self.parse_func_id()
        self._expect("LPAREN")
        params=[]
        if not self._match_kind("RPAREN"):
            params.append(self.parse_param())
            while self._match_kind("COMMA"):
                params.append(self.parse_param())
            self._expect("RPAREN")
        body=self.parse_block()
        return WorkerDecl(line=kw.line, column=kw.column, name=name, params=params, body=body)

    def parse_let_decl(self) -> LetDecl:
        kw=self._expect("KW_LET")
        name=self.parse_capsule_id()
        self._expect("COLON")
        typ=self.parse_type()
        self._expect("SEMICOLON")
        return LetDecl(line=kw.line, column=kw.column, name=name, type_ref=typ)

    def parse_param(self) -> Param:
        name=self.parse_capsule_id()
        self._expect("COLON")
        typ=self.parse_type()
        return Param(line=name.line, column=name.column, name=name, type_ref=typ)

    def parse_type(self) -> TypeRef:
        t=self._peek()
        if t.kind == "KW_BYTE":
            b=self._advance()
            self._expect("LBRACKET")
            sz=self._expect("INT")
            self._expect("RBRACKET")
            return TypeRef(line=b.line, column=b.column, kind="byte_array", size=sz.value)
        # capsule<...> or packet<...>
        if t.kind in ("KW_CAPSULE","KW_PACKET") or (t.kind=="IDENT" and t.lexeme=="packet"):
            head=self._advance()
            self._expect("LT")
            inner=self.parse_type()
            self._expect("GT")
            return TypeRef(line=head.line, column=head.column, kind=head.lexeme, inner=inner)
        # primitives
        if t.kind in ("KW_U8","KW_U16","KW_U32","KW_U64","KW_I8","KW_I16","KW_I32","KW_I64","KW_F32","KW_F64","KW_BOOL","KW_STAMP","KW_DURATION"):
            tok=self._advance()
            return TypeRef(line=tok.line, column=tok.column, kind="prim", name=tok.lexeme)
        raise ParserError(f"Expected type but got {t.kind} at {t.line}:{t.column}")

    def parse_capsule_id(self) -> Identifier:
        t=self._expect("DOLLAR_IDENT")
        return Identifier(line=t.line, column=t.column, name=t.value, is_dollar=True)
    def parse_func_id(self) -> Identifier:
        t=self._expect("DOLLAR_IDENT")
        return Identifier(line=t.line, column=t.column, name=t.value, is_dollar=True)

    # statements
    def parse_statement(self) -> Stmt:
        t=self._peek()
        k=t.kind
        if k=="COLON":
            c=self._advance(); ident=self._expect("IDENT")
            return LabelStmt(line=c.line, column=c.column, name=ident.lexeme)

        # Shortcode
        if k=="HASH_INIT":      return self._stmt_unary(InitStmt)
        if k=="HASH_LOAD":      return self._stmt_load()
        if k=="HASH_CALL":      return self._stmt_call()
        if k=="HASH_EXIT":      return self._mk(ExitStmt, t)
        if k=="HASH_LEASE":     return self._stmt_unary(LeaseStmt)
        if k=="HASH_SUBLEASE":  return self._stmt_unary(SubleaseStmt)
        if k=="HASH_RELEASE":   return self._stmt_unary(ReleaseStmt)
        if k=="HASH_CHECK_EXP": return self._stmt_unary(CheckExpStmt)
        if k=="HASH_RENDER":    return self._stmt_unary(RenderStmt)
        if k=="HASH_INPUT":     return self._stmt_unary(InputStmt)
        if k=="HASH_OUTPUT":    return self._stmt_unary(OutputStmt)
        if k=="HASH_SEND":      return self._stmt_chan(SendStmt)
        if k=="HASH_RECV":      return self._stmt_chan(RecvStmt)
        if k=="HASH_SPAWN":     return self._stmt_spawn()
        if k=="HASH_JOIN":      return self._stmt_unary2(JoinStmt, "thread")
        if k=="HASH_STAMP":     return self._stmt_value(StampStmt)
        if k=="HASH_EXPIRE":    return self._stmt_duration(ExpireStmt)
        if k=="HASH_SLEEP":     return self._stmt_sleep()
        if k=="HASH_YIELD":     return self._mk(YieldStmt, t)
        if k=="HASH_ERROR":     return self._stmt_error()
        if k=="HASH_IF":        return self._stmt_if()
        if k=="HASH_LOOP":      return self._stmt_loop()
        if k=="HASH_BREAK":     return self._mk(BreakStmt, t)
        if k=="HASH_CONTINUE":  return self._mk(ContinueStmt, t)

        # Long-form
        if k=="KW_INITIALIZE":
            init_kw=self._advance(); self._expect("KW_CAPSULE")
            target=self.parse_capsule_id()
            return InitStmt(line=init_kw.line, column=init_kw.column, target=target)
        if k=="KW_ASSIGN":
            a=self._advance(); self._expect("KW_VALUE")
            val=self.parse_value_expr()
            self._expect("KW_TO"); self._expect("KW_CAPSULE")
            target=self.parse_capsule_id()
            return LoadStmt(line=a.line, column=a.column, target=target, value=val)
        if k=="KW_INVOKE":
            inv=self._advance(); self._expect("KW_FUNCTION")
            fn=self.parse_func_id(); arg=None
            if self._match_kind("KW_WITH"):
                self._expect("KW_CAPSULE")
                arg=self.parse_capsule_id()
            return CallStmt(line=inv.line, column=inv.column, func=fn, arg=arg)
        if k=="KW_TERMINATE":
            tr=self._advance(); self._expect("KW_EXECUTION")
            return ExitStmt(line=tr.line, column=tr.column)

        if k=="KW_GOTO":
            g=self._advance(); self._expect("COLON")
            ident=self._expect("IDENT")
            return GotoStmt(line=g.line, column=g.column, label=ident.lexeme)

        raise ParserError(f"Unknown statement start {k} at {t.line}:{t.column}")

    def _mk(self, cls, tok): self._advance(); return cls(line=tok.line, column=tok.column)
    def _stmt_unary(self, cls):
        t=self._advance(); cap=self.parse_capsule_id(); return cls(line=t.line, column=t.column, target=cap)
    def _stmt_unary2(self, cls, field):
        t=self._advance(); cap=self.parse_capsule_id(); return cls(line=t.line, column=t.column, **{field: cap})
    def _stmt_load(self) -> LoadStmt:
        t=self._expect("HASH_LOAD"); cap=self.parse_capsule_id(); self._expect("COMMA"); val=self.parse_value_expr()
        return LoadStmt(line=t.line, column=t.column, target=cap, value=val)
    def _stmt_call(self) -> CallStmt:
        t=self._expect("HASH_CALL"); fn=self.parse_func_id(); arg=None
        if self._match_kind("COMMA"): arg=self.parse_capsule_id()
        return CallStmt(line=t.line, column=t.column, func=fn, arg=arg)
    def _stmt_chan(self, cls):
        t=self._advance(); a=self.parse_capsule_id(); self._expect("COMMA"); b=self.parse_capsule_id()
        if cls is SendStmt: return SendStmt(line=t.line, column=t.column, chan=a, pkt=b)
        return RecvStmt(line=t.line, column=t.column, chan=a, pkt=b)
    def _stmt_spawn(self) -> SpawnStmt:
        t=self._expect("HASH_SPAWN"); fn=self.parse_func_id(); args=[]
        if self._match_kind("COMMA"):
            args.append(self.parse_arg())
            while self._match_kind("COMMA"):
                args.append(self.parse_arg())
        return SpawnStmt(line=t.line, column=t.column, func=fn, args=args)
    def _stmt_value(self, cls):
        t=self._advance(); cap=self.parse_capsule_id(); self._expect("COMMA"); val=self.parse_value_expr()
        if cls is StampStmt: return StampStmt(line=t.line, column=t.column, target=cap, value=val)
        raise ParserError("Unsupported _stmt_value class")
    def _stmt_duration(self, cls):
        t=self._advance(); cap=self.parse_capsule_id(); self._expect("COMMA"); dur=self._expect("DURATION")
        lit=Literal(line=dur.line, column=dur.column, kind="DURATION", value=dur.value)
        return ExpireStmt(line=t.line, column=t.column, target=cap, duration=lit)
    def _stmt_sleep(self) -> SleepStmt:
        t=self._expect("HASH_SLEEP"); dur=self._expect("DURATION")
        return SleepStmt(line=t.line, column=t.column, duration=Literal(line=dur.line, column=dur.column, kind="DURATION", value=dur.value))
    def _stmt_error(self) -> ErrorStmt:
        t=self._expect("HASH_ERROR"); cap=self.parse_capsule_id(); self._expect("COMMA"); code=self.parse_value_expr(); self._expect("COMMA"); msg=self._expect("STRING")
        return ErrorStmt(line=t.line, column=t.column, target=cap, code=code, message=Literal(line=msg.line, column=msg.column, kind="STRING", value=msg.value))
    def _stmt_if(self) -> IfStmt:
        it=self._expect("HASH_IF"); self._expect("LPAREN"); cond=self.parse_expr(); self._expect("RPAREN"); then_block=self.parse_block()
        else_block=None
        if self._match_kind("HASH_ELSE"): else_block=self.parse_block()
        self._expect("HASH_ENDIF")
        return IfStmt(line=it.line, column=it.column, cond=cond, then_block=then_block, else_block=else_block)
    def _stmt_loop(self) -> LoopStmt:
        lt=self._expect("HASH_LOOP"); self._expect("LPAREN"); cond=self.parse_expr(); self._expect("RPAREN"); body=self.parse_block()
        return LoopStmt(line=lt.line, column=lt.column, cond=cond, body=body)

    def parse_arg(self):
        t=self._peek()
        if t.kind=="DOLLAR_IDENT": return self.parse_capsule_id()
        if t.kind in ("INT","HEX","DURATION","STRING","BOOL"): return self.parse_value_expr()
        return self.parse_expr()

    def parse_value_expr(self) -> Literal:
        t=self._peek()
        if t.kind in ("INT","HEX","DURATION","STRING","BOOL"):
            tok=self._advance()
            return Literal(line=tok.line, column=tok.column, kind=tok.kind, value=tok.value)
        return self.parse_expr()

    # Expressions (precedence)
    def parse_expr(self) -> Expr: return self._parse_or()
    def _parse_or(self) -> Expr:
        left=self._parse_and()
        while self._match_kind("OROR"):
            right=self._parse_and(); left=BinaryOp(line=left.line, column=left.column, op="||", lhs=left, rhs=right)
        return left
    def _parse_and(self) -> Expr:
        left=self._parse_eq()
        while self._match_kind("ANDAND"):
            right=self._parse_eq(); left=BinaryOp(line=left.line, column=left.column, op="&&", lhs=left, rhs=right)
        return left
    def _parse_eq(self) -> Expr:
        left=self._parse_rel()
        while True:
            if self._match_kind("EQEQ"):   right=self._parse_rel(); left=BinaryOp(line=left.line, column=left.column, op="==", lhs=left, rhs=right)
            elif self._match_kind("BANGEQ"): right=self._parse_rel(); left=BinaryOp(line=left.line, column=left.column, op="!=", lhs=left, rhs=right)
            else: break
        return left
    def _parse_rel(self) -> Expr:
        left=self._parse_add()
        while True:
            if self._match_kind("LT"):   right=self._parse_add(); left=BinaryOp(line=left.line, column=left.column, op="<", lhs=left, rhs=right)
            elif self._match_kind("GT"): right=self._parse_add(); left=BinaryOp(line=left.line, column=left.column, op=">", lhs=left, rhs=right)
            elif self._match_kind("LTE"): right=self._parse_add(); left=BinaryOp(line=left.line, column=left.column, op="<=", lhs=left, rhs=right)
            elif self._match_kind("GTE"): right=self._parse_add(); left=BinaryOp(line=left.line, column=left.column, op=">=", lhs=left, rhs=right)
            else: break
        return left
    def _parse_add(self) -> Expr:
        left=self._parse_mul()
        while True:
            if self._match_kind("PLUS"):  right=self._parse_mul(); left=BinaryOp(line=left.line, column=left.column, op="+", lhs=left, rhs=right)
            elif self._match_kind("MINUS"): right=self._parse_mul(); left=BinaryOp(line=left.line, column=left.column, op="-", lhs=left, rhs=right)
            else: break
        return left
    def _parse_mul(self) -> Expr:
        left=self._parse_unary()
        while True:
            if self._match_kind("STAR"): right=self._parse_unary(); left=BinaryOp(line=left.line, column=left.column, op="*", lhs=left, rhs=right)
            elif self._match_kind("SLASH"): right=self._parse_unary(); left=BinaryOp(line=left.line, column=left.column, op="/", lhs=left, rhs=right)
            elif self._match_kind("PERCENT"): right=self._parse_unary(); left=BinaryOp(line=left.line, column=left.column, op="%", lhs=left, rhs=right)
            else: break
        return left
    def _parse_unary(self) -> Expr:
        if self._match_kind("BANG"):
            rhs=self._parse_unary(); return UnaryOp(line=rhs.line, column=rhs.column, op="!", rhs=rhs)
        if self._match_kind("TILDE"):
            rhs=self._parse_unary(); return UnaryOp(line=rhs.line, column=rhs.column, op="~", rhs=rhs)
        if self._match_kind("MINUS"):
            rhs=self._parse_unary(); return UnaryOp(line=rhs.line, column=rhs.column, op="u-", rhs=rhs)
        return self._parse_primary()
    def _parse_primary(self) -> Expr:
        t=self._peek()
        if t.kind in ("INT","HEX","DURATION","STRING","BOOL"):
            tok=self._advance(); return Literal(line=tok.line, column=tok.column, kind=tok.kind, value=tok.value)
        if t.kind=="DOLLAR_IDENT":
            tok=self._advance(); return Identifier(line=tok.line, column=tok.column, name=tok.value, is_dollar=True)
        if t.kind=="IDENT":
            tok=self._advance(); return Identifier(line=tok.line, column=tok.column, name=tok.lexeme, is_dollar=False)
        if t.kind=="LPAREN":
            self._advance(); e=self.parse_expr(); self._expect("RPAREN"); return e
        raise ParserError(f"Expected expression but got {t.kind} at {t.line}:{t.column}")

def parse_source_to_ast_json(text: str) -> dict:
    lx=lex.Lexer(text); toks=lx.tokenize(); p=Parser(toks); ast=p.parse_program(); return ast.to_json()

def main():
    import argparse
    ap=argparse.ArgumentParser(description="E Minor v1.0 Parser → AST JSON")
    ap.add_argument("file", help="source path or '-'")
    ap.add_argument("--pretty", action="store_true")
    args=ap.parse_args()
    if args.file == "-": src=sys.stdin.read()
    else:
        with open(args.file,"r",encoding="utf-8") as f: src=f.read()
    try:
        out=parse_source_to_ast_json(src)
        if args.pretty: print(json.dumps(out, indent=2))
        else: print(json.dumps(out, separators=(",",":")))
    except (ParserError, lex.LexerError) as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr); sys.exit(1)

if __name__=="__main__":
    main()
