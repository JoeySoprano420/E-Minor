#!/usr/bin/env python3
# E Minor v1.0 — Official FULL-LANGUAGE Lexer (Megalithic-Optimized)
# Drop-in replacement for eminor_lexer.py
# Usage (compatible):
#   python eminor_lexer.py <file>            # JSON (pretty)
#   echo '...' | python eminor_lexer.py -    # read stdin
# Extras (optional):
#   --emit=ndjson | --emit=json  (default=json)
#   --validate-only              (scan only, no token materialization)

import sys, json

# === Tables (hot path; kept at module scope for fast locals binding) ===
EMINOR_KEYWORDS = {
    "initialize":"KW_INITIALIZE","capsule":"KW_CAPSULE","assign":"KW_ASSIGN","value":"KW_VALUE","to":"KW_TO",
    "invoke":"KW_INVOKE","function":"KW_FUNCTION","with":"KW_WITH","terminate":"KW_TERMINATE","execution":"KW_EXECUTION",
    "if":"KW_IF","else":"KW_ELSE","loop":"KW_LOOP","goto":"KW_GOTO",
    "u8":"KW_U8","u16":"KW_U16","u32":"KW_U32","u64":"KW_U64",
    "i8":"KW_I8","i16":"KW_I16","i32":"KW_I32","i64":"KW_I64",
    "f32":"KW_F32","f64":"KW_F64","bool":"KW_BOOL","stamp":"KW_STAMP","duration":"KW_DURATION","byte":"KW_BYTE",
    "worker":"KW_WORKER","let":"KW_LET","true":"KW_TRUE","false":"KW_FALSE",
    "main":"KW_MAIN","entry_point":"KW_ENTRY_POINT","module":"KW_MODULE","export":"KW_EXPORT","import":"KW_IMPORT",
    "ns":"KW_NS","ms":"KW_MS","s":"KW_S","m":"KW_M","h":"KW_H",
}
KW_BOOL_LIT = {"true": True, "false": False}

HASH_DIRECTIVES = {
    "init":"HASH_INIT","load":"HASH_LOAD","call":"HASH_CALL","exit":"HASH_EXIT",
    "lease":"HASH_LEASE","sublease":"HASH_SUBLEASE","release":"HASH_RELEASE","check_exp":"HASH_CHECK_EXP",
    "render":"HASH_RENDER","input":"HASH_INPUT","output":"HASH_OUTPUT",
    "send":"HASH_SEND","recv":"HASH_RECV","spawn":"HASH_SPAWN","join":"HASH_JOIN",
    "stamp":"HASH_STAMP","expire":"HASH_EXPIRE","sleep":"HASH_SLEEP","yield":"HASH_YIELD",
    "error":"HASH_ERROR","if":"HASH_IF","else":"HASH_ELSE","endif":"HASH_ENDIF",
    "loop":"HASH_LOOP","break":"HASH_BREAK","continue":"HASH_CONTINUE",
}

AT_DIRECTIVES = {"main":"AT_MAIN","entry_point":"AT_ENTRY_POINT","module":"AT_MODULE","export":"AT_EXPORT","import":"AT_IMPORT"}

OP2 = {'=':{'=':"EQEQ"}, '!':{'=':"BANGEQ"}, '<':{'=':"LTE",'<':"LSHIFT"}, '>':{'=':"GTE",'>':"RSHIFT"}, '&':{'&':"ANDAND"}, '|':{'|':"OROR"}}
OP1 = {'=':"EQ", '<':"LT", '>':"GT", '+':"PLUS", '-':"MINUS", '*':"STAR", '/':"SLASH", '%':"PERCENT", '!':"BANG", '~':"TILDE",
       '&':"AMP", '|':"BAR", '^':"CARET", '(':"LPAREN", ')':"RPAREN", '{':"LBRACE", '}':"RBRACE", '[':"LBRACKET", ']':"RBRACKET",
       ',':"COMMA", ';':"SEMICOLON", ':':"COLON", '.':"DOT"}

DUR_NS = {"ns":1, "ms":1_000_000, "s":1_000_000_000, "m":60*1_000_000_000, "h":60*60*1_000_000_000}

HEX_SET = set("0123456789abcdefABCDEF")
DIG_SET = set("0123456789")
ID_SET_HEAD = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_")
ID_SET_BODY = ID_SET_HEAD | DIG_SET

class LexerError(Exception): pass

class Token:
    __slots__ = ("kind","lexeme","line","column","value")
    def __init__(self, kind, lexeme, line, column, value=None):
        self.kind=kind; self.lexeme=lexeme; self.line=line; self.column=column; self.value=value
    def as_dict(self):
        d={"kind":self.kind,"lexeme":self.lexeme,"line":self.line,"column":self.column}
        if self.value is not None: d["value"]=self.value
        return d
    def as_nd(self):
        if self.value is None: return f"{self.kind}\t{self.lexeme}\t{self.line}\t{self.column}"
        return f"{self.kind}\t{self.lexeme}\t{self.line}\t{self.column}\t{self.value}"

class Lexer:
    __slots__ = ("s","n","i","line","col")
    def __init__(self, text: str):
        self.s=text; self.n=len(text); self.i=0; self.line=1; self.col=1

    def _peek(self, k=0):
        j=self.i+k
        return self.s[j] if j<self.n else ""

    def _adv(self):
        ch=self.s[self.i]
        if ch=="\n": self.line+=1; self.col=1
        else: self.col+=1
        self.i+=1
        return ch

    def _skip_ws_comments(self):
        s=self.s; n=self.n; i=self.i; line=self.line; col=self.col
        while i<n:
            ch=s[i]
            if ch in " \t\r\n":
                if ch=="\n": line+=1; col=1
                else: col+=1
                i+=1; continue
            if ch=='/' and i+1<n and s[i+1]=='/':
                i+=2; col+=2
                j=s.find('\n', i)
                if j==-1:
                    self.i=n; self.line=line; self.col=col+(n-i); return
                line+=1; col=1; i=j+1; continue
            if ch=='/' and i+1<n and s[i+1]=='*':
                i+=2; col+=2
                while i<n:
                    if s[i]=='\n': line+=1; col=1; i+=1; continue
                    if s[i]=='*' and i+1<n and s[i+1]=='/':
                        i+=2; col+=2; break
                    i+=1; col+=1
                else:
                    raise LexerError(f"Unterminated block comment at line {line}")
                continue
            break
        self.i=i; self.line=line; self.col=col

    def _read_ident_or_kw(self):
        s=self.s; i=self.i; n=self.n; line=self.line; col=self.col
        j=i
        while j<n and s[j] in ID_SET_BODY: j+=1
        ident=s[i:j]
        self.i=j; self.col += (j-i)
        if ident in ("true","false"):
            return Token("BOOL", ident, line, col, ident=="true")
        kind=EMINOR_KEYWORDS.get(ident)
        if kind: return Token(kind, ident, line, col, None)
        return Token("IDENT", ident, line, col, None)

    def _read_dollar_ident(self):
        line=self.line; col=self.col
        self._adv()
        ch=self._peek()
        if not (ch and ch in ID_SET_HEAD):
            raise LexerError(f"Invalid identifier after $ at {line}:{col}")
        t=self._read_ident_or_kw()
        return Token("DOLLAR_IDENT", "$"+t.lexeme, line, col, t.lexeme)

    def _read_string(self):
        line=self.line; col=self.col
        assert self._adv()=='"'
        s=self.s; i=self.i; n=self.n
        out=[]
        while i<n:
            ch=s[i]
            if ch=='"':
                self.i=i+1; self.col += (i+1 - col)
                lex='"'+''.join(out)+'"'
                return Token("STRING", lex, line, col, ''.join(out))
            if ch=='\\':
                if i+1>=n: raise LexerError(f"Bad escape at {self.line}:{self.col}")
                esc=s[i+1]
                if esc=='n': out.append("\n"); i+=2
                elif esc=='t': out.append("\t"); i+=2
                elif esc=='"': out.append('"'); i+=2
                elif esc=='\\': out.append("\\"); i+=2
                elif esc=='x':
                    if i+3>=n: raise LexerError(f"Bad \\x escape at {self.line}:{self.col}")
                    h1=s[i+2]; h2=s[i+3]
                    if h1 not in "0123456789abcdefABCDEF" or h2 not in "0123456789abcdefABCDEF":
                        raise LexerError(f"Bad \\x escape at {self.line}:{self.col}")
                    out.append(chr(int(h1+h2,16))); i+=4
                else:
                    raise LexerError(f"Unknown escape \\{esc} at {self.line}:{self.col}")
                continue
            out.append(ch); i+=1
        raise LexerError(f"Unterminated string at {line}:{col}")

    def _read_number_or_duration(self):
        s=self.s; i=self.i; n=self.n; line=self.line; col=self.col
        if i+1<n and s[i]=='0' and (s[i+1]=='x' or s[i+1]=='X'):
            j=i+2
            while j<n and s[j] in "0123456789abcdefABCDEF": j+=1
            if j==i+2: raise LexerError(f"Invalid hex literal at {line}:{col}")
            lex=s[i:j]; self.i=j; self.col += (j-i)
            return Token("HEX", lex, line, col, int(lex[2:],16))
        j=i
        while j<n and s[j].isdigit(): j+=1
        if j==i: raise LexerError(f"Invalid number at {line}:{col}")
        num=s[i:j]; unit=""
        if j<n:
            c=s[j]
            if c=='n' and j+1<n and s[j+1]=='s': unit="ns"; j+=2
            elif c=='m' and j+1<n and s[j+1]=='s': unit="ms"; j+=2
            elif c in "smh": unit=c; j+=1
        lex=s[i:j]; self.i=j; self.col += (j-i)
        if unit:
            mult = 1 if unit=="ns" else (1_000_000 if unit=="ms" else (1_000_000_000 if unit=="s" else (60*1_000_000_000 if unit=="m" else 60*60*1_000_000_000)))
            return Token("DURATION", lex, line, col, int(num)*mult)
        return Token("INT", lex, line, col, int(num))

    def _read_hash(self):
        line=self.line; col=self.col
        self._adv()
        s=self.s; i=self.i; n=self.n; j=i
        while j<n and (s[j].isalnum() or s[j]=='_'): j+=1
        name=s[i:j]; self.i=j; self.col += (j-i)
        if not name: return Token("HASH", "#", line, col, None)
        kind=HASH_DIRECTIVES.get(name)
        if not kind: raise LexerError(f"Unknown hash directive '#{name}' at {line}:{col}")
        return Token(kind, "#"+name, line, col, None)

    def _read_at(self):
        line=self.line; col=self.col
        self._adv()
        s=self.s; i=self.i; n=self.n; j=i
        while j<n and (s[j].isalnum() or s[j]=='_'): j+=1
        name=s[i:j]; self.i=j; self.col += (j-i)
        kind=AT_DIRECTIVES.get(name)
        if not kind: raise LexerError(f"Unknown at-directive '@{name}' at {line}:{col}")
        return Token(kind, "@"+name, line, col, None)

    def _read_operator(self):
        line=self.line; col=self.col; s=self.s; i=self.i; n=self.n
        c1=s[i]
        tab=OP2.get(c1)
        if tab and i+1<n:
            c2=s[i+1]; kind=tab.get(c2)
            if kind:
                self.i=i+2; self.col+=2
                return Token(kind, c1+c2, line, col, None)
        kind=OP1.get(c1)
        if kind:
            self.i=i+1; self.col+=1
            return Token(kind, c1, line, col, None)
        return None

    def next_token(self):
        self._skip_ws_comments()
        if self.i>=self.n: return None
        c=self._peek()
        if c=='#': return self._read_hash()
        if c=='@': return self._read_at()
        if c=='"': return self._read_string()
        if c=='$': return self._read_dollar_ident()
        if c in OP1 or c in OP2:
            tok=self._read_operator()
            if tok: return tok
        if c and c.isdigit(): return self._read_number_or_duration()
        if c and (c in ID_SET_HEAD): return self._read_ident_or_kw()
        raise LexerError(f"Unexpected character '{c}' at {self.line}:{self.col}")

    def tokenize(self):
        out=[]
        while True:
            t=self.next_token()
            if t is None: break
            out.append(t)
        return out

def tokens_to_json(tokens):
    arr=[]
    for t in tokens:
        d=t.as_dict()
        arr.append(d)
    return arr

def main():
    import argparse
    ap=argparse.ArgumentParser(description="E Minor v1.0 Lexer (Megalithic)")
    ap.add_argument("file", help="file path or '-' for stdin")
    ap.add_argument("--emit", choices=["json","ndjson"], default="json")
    ap.add_argument("--validate-only", action="store_true")
    args=ap.parse_args()

    if args.file=="-":
        src=sys.stdin.read()
    else:
        with open(args.file,"r",encoding="utf-8") as f:
            src=f.read()
    try:
        lx=Lexer(src)
        if args.validate_only:
            lx.tokenize()  # run through tokens (materialized but OK)
            print(json.dumps({"ok": True})); return
        toks=lx.tokenize()
        if args.emit=="json":
            print(json.dumps(tokens_to_json(toks), indent=2))
        else:
            # NDJSON streaming
            w=sys.stdout.write
            for t in toks:
                w(t.as_nd()+"\n")
    except LexerError as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
