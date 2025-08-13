#!/usr/bin/env python3
# E Minor v1.0 — Star-Code Validator
# Performs AOT validations on the AST produced by eminor_parser.py

import sys, json
from typing import List, Dict, Any, Optional

def _walk(node, fn):
    if isinstance(node, dict):
        fn(node)
        for k, v in node.items():
            if isinstance(v, (dict, list)):
                _walk(v, fn)
    elif isinstance(node, list):
        for x in node: _walk(x, fn)

SEVERITY = {"ERROR":"ERROR","WARN":"WARN","INFO":"INFO"}

def validate(ast: Dict[str, Any]) -> List[Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []
    declared_caps = set()   # from LetDecl
    inited_caps   = set()   # after InitStmt
    leased_caps   = set()   # after Lease/Sublease/Release
    labels        = set()   # defined labels
    gotos         = []      # (label, line, col)

    # First pass: collect labels and lets
    def pass1(n):
        if n.get("_type") == "LetDecl":
            name = n["name"]["name"]
            declared_caps.add(name)
        elif n.get("_type") == "LabelStmt":
            labels.add(n["name"])

    _walk(ast, pass1)

    def report(kind, msg, line, col, code):
        issues.append({"severity":kind,"code":code,"message":msg,"line":line,"column":col})

    # Second pass: validations
    def pass2(n):
        t = n.get("_type")
        if t == "InitStmt":
            name = n["target"]["name"]
            inited_caps.add(name)
        elif t in ("LoadStmt","RenderStmt","InputStmt","OutputStmt","StampStmt","ExpireStmt"):
            name = n["target"]["name"]
            if name not in inited_caps and name not in declared_caps:
                report(SEVERITY["WARN"], f"Capsule ${name} used before init/let", n["line"], n["column"], "SC001")
        elif t in ("SendStmt","RecvStmt"):
            a = n["chan"]["name"]; b = n["pkt"]["name"]
            if a not in inited_caps and a not in declared_caps:
                report(SEVERITY["WARN"], f"Channel ${a} used before init/let", n["line"], n["column"], "SC002")
            if b not in inited_caps and b not in declared_caps:
                report(SEVERITY["WARN"], f"Packet ${b} used before init/let", n["line"], n["column"], "SC003")
        elif t == "LeaseStmt":
            nm = n["target"]["name"]
            if nm in leased_caps:
                report(SEVERITY["ERROR"], f"Capsule ${nm} double-lease without release", n["line"], n["column"], "SC010")
            leased_caps.add(nm)
        elif t in ("SubleaseStmt",):
            nm = n["target"]["name"]
            if nm not in leased_caps:
                report(SEVERITY["WARN"], f"Sublease on non-leased capsule ${nm}", n["line"], n["column"], "SC011")
        elif t == "ReleaseStmt":
            nm = n["target"]["name"]
            if nm not in leased_caps:
                report(SEVERITY["WARN"], f"Release on non-leased capsule ${nm}", n["line"], n["column"], "SC012")
            leased_caps.discard(nm)
        elif t == "SleepStmt":
            # duration must be integer nanoseconds
            dur = n["duration"]["value"]
            if not isinstance(dur, int) or dur < 0:
                report(SEVERITY["ERROR"], "Sleep duration must be non-negative integer nanoseconds", n["line"], n["column"], "SC020")
        elif t == "ExpireStmt":
            dur = n["duration"]["value"]
            if not isinstance(dur, int) or dur < 0:
                report(SEVERITY["ERROR"], "Expire duration must be non-negative integer nanoseconds", n["line"], n["column"], "SC021")
        elif t == "GotoStmt":
            gotos.append((n["label"], n["line"], n["column"]))
        elif t == "IfStmt":
            # shallow type-ish check: cond should be literal bool or an expression (assume ok); warn if literal non-bool
            c = n["cond"]
            if c.get("_type") == "Literal" and c.get("kind") != "BOOL":
                report(SEVERITY["WARN"], "Non-boolean literal used as condition", n["line"], n["column"], "SC030")

    _walk(ast, pass2)

    # Post: check gotos
    for label, line, col in gotos:
        if label not in labels:
            report(SEVERITY["ERROR"], f"goto :{label} targets undefined label", line, col, "SC040")

    return issues

def main():
    import argparse
    ap = argparse.ArgumentParser(description="E Minor Star-Code Validator")
    ap.add_argument("ast_json", help="path to AST JSON (from eminor_parser.py)")
    args = ap.parse_args()
    with open(args.ast_json, "r", encoding="utf-8") as f:
        ast = json.load(f)
    issues = validate(ast)
    print(json.dumps({"issues": issues}, indent=2))

if __name__ == "__main__":
    main()
