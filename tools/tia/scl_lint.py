"""Static checks for the TIA source files in plc/src (G5).

TIA Portal can't compile without a STEP 7 licence, so this catches the mistakes a compiler
would: unbalanced blocks, undeclared #locals, unknown "globals", wrong member names on DBs,
UDTs and multi-instances. It is not a full SCL parser.

    python tools/tia/scl_lint.py            # exit 1 on any problem
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "plc" / "src"
TAGS = ROOT / "plc" / "tags.md"

# Members of the system types the code uses (TIA documentation)
SYSTEM_TYPES: dict[str, dict[str, str]] = {
    "TON_TIME": {"Q": "Bool", "ET": "Time", "IN": "Bool", "PT": "Time"},
    "DTL": {k: "USInt" for k in ("MONTH", "DAY", "WEEKDAY", "HOUR", "MINUTE", "SECOND")}
    | {"YEAR": "UInt", "NANOSECOND": "UDInt"},
    "TCON_IP_v4": {
        "InterfaceId": "HW_ANY",
        "ID": "CONN_OUC",
        "ConnectionType": "Byte",
        "ActiveEstablished": "Bool",
        "RemoteAddress": "IP_V4",
        "RemotePort": "UInt",
        "LocalPort": "UInt",
    },
    "MB_SERVER": {"NDR": "Bool", "DR": "Bool", "ERROR": "Bool", "STATUS": "Word"},
    "Modbus_Master": {
        "DONE": "Bool",
        "BUSY": "Bool",
        "ERROR": "Bool",
        "STATUS": "Word",
        "MB_DB": "P2P_MB_BASE",
    },
    "Modbus_Comm_Load": {"DONE": "Bool", "ERROR": "Bool", "STATUS": "Word"},
}
BUILTIN_FUNCS = {
    "RD_LOC_T",
    "T_DIFF",
    "SHR",
    "SHL",
    "LEN",
    "INT_TO_REAL",
    "INT_TO_USINT",
    "INT_TO_DINT",
    "INT_TO_WORD",
    "INT_TO_UINT",
    "INT_TO_UDINT",
    "WORD_TO_INT",
    "REAL_TO_INT",
    "DINT_TO_INT",
    "DINT_TO_TIME",
    "TIME_TO_DINT",
    "USINT_TO_INT",
}
BLOCK_PAIRS = [
    ("TYPE", "END_TYPE"),
    ("DATA_BLOCK", "END_DATA_BLOCK"),
    ("FUNCTION_BLOCK", "END_FUNCTION_BLOCK"),
    ("FUNCTION", "END_FUNCTION"),
    ("ORGANIZATION_BLOCK", "END_ORGANIZATION_BLOCK"),
]
CTRL_PAIRS = [
    ("IF", "END_IF"),
    ("CASE", "END_CASE"),
    ("FOR", "END_FOR"),
    ("REGION", "END_REGION"),
]

problems: list[str] = []


def strip(text: str) -> str:
    """Remove // comments, (* *) comments and '...' strings, keeping line numbers."""
    text = re.sub(
        r"\(\*.*?\*\)", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S
    )
    text = re.sub(r"//[^\n]*", "", text)
    return re.sub(r"'[^'\n]*'", "''", text)


def parse_vars(section: str) -> dict[str, str]:
    out = {}
    for m in re.finditer(
        r"^\s*(\w+)\s*:\s*([^;:=]+?)\s*(?::=[^;]*)?;", section, flags=re.M
    ):
        out[m.group(1)] = m.group(2).strip()
    return out


def elem_type(t: str) -> str:
    m = re.match(r"Array\s*\[.*?\]\s*of\s*(.+)$", t, flags=re.I)
    return (m.group(1) if m else t).strip().strip('"')


# ── collect declarations ─────────────────────────────────────
types: dict[str, dict[str, str]] = dict(SYSTEM_TYPES)
dbs: dict[str, dict[str, str]] = {}
blocks: dict[str, dict] = {}
files = sorted(SRC.glob("*.*"))
texts = {f: strip(f.read_text(encoding="utf-8")) for f in files}

for f, t in texts.items():
    for m in re.finditer(r'\bTYPE\s+"(\w+)"(.*?)\bEND_TYPE', t, flags=re.S):
        types[m.group(1)] = parse_vars(m.group(2))
    for m in re.finditer(r'\bDATA_BLOCK\s+"(\w+)"(.*?)\bEND_DATA_BLOCK', t, flags=re.S):
        body = m.group(2)
        inst = re.search(r'^\s*"(\w+)"\s*$', body.split("BEGIN")[0], flags=re.M)
        dbs[m.group(1)] = (
            {"__instance_of__": inst.group(1)}
            if inst
            else parse_vars(body.split("BEGIN")[0])
        )
    for kind, end in (
        ("FUNCTION_BLOCK", "END_FUNCTION_BLOCK"),
        ("FUNCTION", "END_FUNCTION"),
        ("ORGANIZATION_BLOCK", "END_ORGANIZATION_BLOCK"),
    ):
        for m in re.finditer(
            rf'\b{kind}\s+"(\w+)"(\s*:\s*(\w+(?:\[\d+\])?))?(.*?)\b{end}\b',
            t,
            flags=re.S,
        ):
            name, body = m.group(1), m.group(4)
            head, _, code = body.partition("\nBEGIN")
            decl = {}
            for sec in re.finditer(
                r"\bVAR(?:_INPUT|_OUTPUT|_IN_OUT|_TEMP|\s+CONSTANT)?\b(.*?)\bEND_VAR",
                head,
                flags=re.S,
            ):
                decl.update(parse_vars(sec.group(1)))
            if kind == "FUNCTION":
                decl[name] = m.group(3) or "Void"
            blocks[name] = {"kind": kind, "decl": decl, "code": code, "file": f.name}
            if kind == "FUNCTION_BLOCK":
                types[name] = {k: v for k, v in decl.items()}

tags = set(re.findall(r'^\|\s*"(\w+)"', TAGS.read_text(encoding="utf-8"), flags=re.M))
for name, db in list(dbs.items()):
    if "__instance_of__" in db:
        dbs[name] = types.get(db["__instance_of__"], {})


def walk(base_type: str, members: list[str], where: str) -> None:
    t = base_type
    for mem in members:
        t = elem_type(t)
        fields = types.get(t)
        if fields is None:
            return  # elementary or unknown system type: can't check deeper
        if mem not in fields:
            problems.append(f"{where}: '{mem}' is not a member of {t}")
            return
        t = fields[mem]


REF = re.compile(
    r'((?<![\w#])#[A-Za-z_]\w*|"[\w~]+")((?:\s*\[[^\]]*\])?(?:\.\w+(?:\s*\[[^\]]*\])?)*)'
)

# ── check every file ─────────────────────────────────────────
for f, t in texts.items():
    for open_kw, close_kw in BLOCK_PAIRS:
        o = len(re.findall(rf"^\s*{open_kw}\s+\"", t, flags=re.M))
        c = len(re.findall(rf"\b{close_kw}\b", t))
        if o != c:
            problems.append(f"{f.name}: {o} {open_kw} vs {c} {close_kw}")

for name, b in blocks.items():
    code, where = b["code"], f"{b['file']} {name}"
    for o, c in CTRL_PAIRS:
        # the lookbehind keeps END_IF from counting as an IF
        if len(re.findall(rf"(?<![\w_]){o}\b", code)) != len(
            re.findall(rf"\b{c}\b", code)
        ):
            problems.append(f"{where}: {o}/{c} not balanced")
    for m in REF.finditer(code):
        head, rest = m.group(1), m.group(2)
        members = re.findall(r"\.(\w+)", re.sub(r"\[[^\]]*\]", "", rest))
        if head.startswith("#"):
            var = head[1:]
            if var not in b["decl"]:
                problems.append(f"{where}: #{var} is not declared")
                continue
            walk(b["decl"][var], members, f"{where} #{var}")
        else:
            g = head.strip('"')
            if g in dbs:
                if members:
                    if members[0] not in dbs[g]:
                        problems.append(f'{where}: "{g}".{members[0]} does not exist')
                    else:
                        walk(
                            dbs[g][members[0]],
                            members[1:],
                            f'{where} "{g}".{members[0]}',
                        )
            elif g in blocks or g in tags or g.startswith("Local~"):
                pass
            else:
                problems.append(f'{where}: unknown global "{g}"')
    for fn in re.findall(r"\b([A-Z][A-Z0-9_]+)\s*\(", code):
        if fn not in BUILTIN_FUNCS and fn not in {"IF", "AND", "OR", "NOT", "ELSIF"}:
            problems.append(f"{where}: unknown function {fn}(")
    # every statement must end with ';' (allow continuation lines)
    stmt = ""
    for raw in code.splitlines():
        s = raw.strip()
        if not s:
            continue
        if re.match(r"^END_(IF|FOR|CASE|WHILE|REPEAT)\b", s) and not s.endswith(";"):
            problems.append(f"{where}: missing ';' after {s}")
        if stmt and ":=" in stmt and re.match(r"^(ELSIF|ELSE|END_)", s):
            problems.append(f"{where}: missing ';' at the end of: {stmt[:50]}")
            stmt = ""
        if (
            stmt
            and ":=" in stmt
            and re.match(r'^(#\w|"\w)[^=]*?:=', s)
            and not stmt.endswith((",", "(", "AND", "OR", "+", "-", "*", "/"))
        ):
            problems.append(f"{where}: missing ';' before: {s[:50]}")
            stmt = ""
        stmt = (stmt + " " + s).strip()
        if (
            stmt.endswith((";", "THEN", "DO", "ELSE", "OF", ":"))
            or re.match(r"^(REGION|END_REGION)\b", stmt)
            or re.match(r"^\d+(\.\.\d+)?\s*:", stmt)
        ):
            stmt = ""
    if stmt and not stmt.startswith("END_"):
        problems.append(f"{where}: statement not terminated near: {stmt[:60]}")

print(
    f"checked {len(files)} files: {len(types) - len(SYSTEM_TYPES)} types/FBs, {len(dbs)} DBs, "
    f"{len(blocks)} blocks, {len(tags)} tags"
)
for p in problems:
    print("  PROBLEM", p)
sys.exit(1 if problems else 0)
