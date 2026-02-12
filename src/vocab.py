# ============================================================
# 1. SPECIAL TOKENS
# ============================================================
PAD = "<PAD>"
START = "<START>"
END = "<END>"
UNK = "<UNK>"

SPECIAL_TOKENS = [PAD, START, END, UNK]

# ============================================================
# 2. CORE SQL KEYWORDS
# ============================================================
SELECT = "SELECT"
FROM = "FROM"
WHERE = "WHERE"
GROUP_BY = "GROUP_BY"
HAVING = "HAVING"
ORDER_BY = "ORDER_BY"
LIMIT = "LIMIT"
OFFSET = "OFFSET"
DISTINCT = "DISTINCT"

SQL_KEYWORDS = [
    SELECT, FROM, WHERE, GROUP_BY, HAVING,
    ORDER_BY, LIMIT, OFFSET, DISTINCT
]

# ============================================================
# 3. JOIN KEYWORDS (Phase-4)
# ============================================================
JOIN = "JOIN"
INNER_JOIN = "INNER_JOIN"
LEFT_JOIN = "LEFT_JOIN"
RIGHT_JOIN = "RIGHT_JOIN"
FULL_JOIN = "FULL_JOIN"
CROSS_JOIN = "CROSS_JOIN"
ON = "ON"
USING = "USING"

JOIN_KEYWORDS = [
    JOIN, INNER_JOIN, LEFT_JOIN,
    RIGHT_JOIN, FULL_JOIN, CROSS_JOIN,
    ON, USING
]

# ============================================================
# 4. AGGREGATION FUNCTIONS
# ============================================================
AGG_FUNCS = ["COUNT", "SUM", "AVG", "MIN", "MAX"]

# ============================================================
# 5. OPERATORS
# ============================================================
OPS = [
    "=", "!=", ">", "<", ">=", "<=",
    "IN", "NOT_IN",
    "BETWEEN",
    "LIKE", "NOT_LIKE",
    "IS_NULL", "IS_NOT_NULL"
]

# ============================================================
# 6. LOGICAL / ORDER TOKENS
# ============================================================
AND = "AND"
OR = "OR"
NOT = "NOT"
ASC = "ASC"
DESC = "DESC"

LOGICAL_TOKENS = [AND, OR, NOT, ASC, DESC]

# ============================================================
# 7. POINTER / ABSTRACT TOKENS (UPDATED)
# ============================================================
SCHEMA_TABLE = "<TABLE>"
SCHEMA_COLUMN = "<COLUMN>"
VALUE = "<VALUE>"
ALIAS = "<ALIAS>"
AGG = "<AGG>"  # 🔥 ADD THIS: Matches your phase4_join.json

ABSTRACT_TOKENS = [
    SCHEMA_TABLE,
    SCHEMA_COLUMN,
    VALUE,
    ALIAS,
    AGG        # 🔥 ADD THIS
]

# ============================================================
# 8. FINAL VOCAB (Remains same, but now includes AGG)
# ============================================================
BASE_VOCAB = (
    SPECIAL_TOKENS
    + SQL_KEYWORDS
    + JOIN_KEYWORDS
    + AGG_FUNCS
    + OPS
    + LOGICAL_TOKENS
    + ABSTRACT_TOKENS
)

TOKEN2ID = {tok: idx for idx, tok in enumerate(BASE_VOCAB)}
ID2TOKEN = {idx: tok for tok, idx in TOKEN2ID.items()}
VOCAB_SIZE = len(TOKEN2ID)

# ============================================================
# 9. SAFE HELPERS
# ============================================================
def token_to_id(token: str) -> int:
    return TOKEN2ID.get(token, TOKEN2ID[UNK])

def id_to_token(idx: int) -> str:
    return ID2TOKEN.get(idx, UNK)

# ============================================================
# 10. AST → TOKEN SEQUENCE
# ============================================================
def ast_to_tokens(ast: dict):
    """
    Deterministic AST linearization.
    Schema values are NEVER learned, only abstracted.
    """

    tokens = [START, SELECT]

    # ---------- SELECT ----------
    for item in ast.get("select", []):
        if item.get("agg"):
            tokens.append(item["agg"])
        tokens.append(SCHEMA_COLUMN)

    # ---------- FROM ----------
    tokens.append(FROM)
    tokens.append(SCHEMA_TABLE)

    # ---------- JOIN ----------
    for _ in ast.get("joins", []):
        tokens.extend([
            JOIN,
            SCHEMA_TABLE,
            ON,
            SCHEMA_COLUMN,
            SCHEMA_COLUMN
        ])

    # ---------- WHERE ----------
    if ast.get("where"):
        tokens.append(WHERE)
        for i, cond in enumerate(ast["where"]):
            tokens.extend([
                SCHEMA_COLUMN,
                cond["op"],
                VALUE
            ])
            if i < len(ast["where"]) - 1:
                tokens.append(AND)

    # ---------- GROUP BY ----------
    if ast.get("group_by"):
        tokens.append(GROUP_BY)
        tokens.extend([SCHEMA_COLUMN] * len(ast["group_by"]))

    # ---------- HAVING ----------
    if ast.get("having"):
        tokens.append(HAVING)
        for cond in ast["having"]:
            tokens.extend([
                cond["agg"],
                SCHEMA_COLUMN,
                cond["op"],
                VALUE
            ])

    # ---------- ORDER BY ----------
    if ast.get("order_by"):
        tokens.append(ORDER_BY)
        for ob in ast["order_by"]:
            tokens.extend([
                SCHEMA_COLUMN,
                ob.get("direction", ASC)
            ])

    # ---------- LIMIT / OFFSET ----------
    if ast.get("limit") is not None:
        tokens.extend([LIMIT, VALUE])

    if ast.get("offset") is not None:
        tokens.extend([OFFSET, VALUE])

    tokens.append(END)
    return tokens

# ============================================================
# 11. TOKEN SEQUENCE → AST  (FIXED)
# ============================================================
def tokens_to_ast(tokens: list):
    """
    Robust version of tokens_to_ast. 
    Handles both abstract placeholders (<COLUMN>) and bound names (employees.id).
    """
    ast = {
        "select": [], "from": [], "joins": [], "where": [],
        "group_by": [], "having": [], "order_by": [],
        "limit": None, "offset": None
    }

    i = 0
    N = len(tokens)
    
    # Helper to identify if a token is a structural keyword
    keywords = {SELECT, FROM, WHERE, GROUP_BY, HAVING, ORDER_BY, LIMIT, OFFSET, JOIN, ON, END, START}

    while i < N:
        tok = tokens[i]

        # ---------- SELECT ----------
        if tok == SELECT:
            i += 1
            while i < N and tokens[i] not in {FROM, END}:
                agg = None
                if tokens[i] in AGG_FUNCS or tokens[i] == "<AGG>":
                    agg = tokens[i]
                    i += 1
                
                # If it's not a keyword, it's a column (placeholder or real name)
                if i < N and tokens[i] not in keywords:
                    ast["select"].append({"agg": agg, "column": tokens[i]})
                    i += 1
                else:
                    # Safety increment if we hit something unexpected to prevent infinite loop
                    if i < N and tokens[i] not in keywords: i += 1
                    else: break

        # ---------- FROM ----------
        elif tok == FROM:
            i += 1
            if i < N and tokens[i] not in keywords:
                ast["from"].append(tokens[i])
                i += 1

        # ---------- JOIN ----------
        elif tok in [JOIN, INNER_JOIN, LEFT_JOIN, RIGHT_JOIN]:
            join_type = "INNER"
            if tok == LEFT_JOIN:
                join_type = "LEFT"
            elif tok == RIGHT_JOIN:
                join_type = "RIGHT"
        
            i += 1
            table = tokens[i]
            i += 2  # skip ON
            left = tokens[i]; right = tokens[i+1]
            i += 2
        
            ast["joins"].append({
                "type": join_type,
                "table": table,
                "on": {"left": left, "right": right}
            })

            # Skip any remaining noise until next clause
            while i < N and tokens[i] not in {WHERE, GROUP_BY, HAVING, ORDER_BY, LIMIT, OFFSET, END}:
                i += 1

        # ---------- WHERE ----------
        elif tok == WHERE:
            i += 1
            while i < N and tokens[i] not in {GROUP_BY, HAVING, ORDER_BY, LIMIT, OFFSET, END}:
                if tokens[i] not in keywords and i + 2 < N:
                    ast["where"].append({
                        "column": tokens[i],
                        "op": tokens[i + 1],
                        "value": tokens[i + 2]
                    })
                    i += 3
                elif tokens[i] == AND or tokens[i] == OR:
                    i += 1
                else:
                    break

        # ---------- GROUP BY ----------
        elif tok == GROUP_BY:
            i += 1
            while i < N and tokens[i] not in {HAVING, ORDER_BY, LIMIT, OFFSET, END}:
                if tokens[i] not in keywords:
                    ast["group_by"].append(tokens[i])
                    i += 1
                else: break

        # ---------- OTHERS (Standard else) ----------
        else:
            i += 1

    return ast