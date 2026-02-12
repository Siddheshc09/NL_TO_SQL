# ============================================================
'''# utils.py — PHASE-3 SAFE (BACKWARD COMPATIBLE)
# ============================================================
import torch
import random
import numpy as np
from typing import List, Set

from src.vocab import *

# ----------------------------
# Reproducibility
# ----------------------------
def set_seed(seed: int = 42):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)

def get_device():
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")

# ----------------------------
# Token ↔ ID helpers
# ----------------------------
def tokens_to_ids(tokens: List[str]) -> List[int]:
    return [TOKEN2ID.get(t, TOKEN2ID[UNK]) for t in tokens]

def ids_to_tokens(ids: List[int]) -> List[str]:
    return [ID2TOKEN.get(i, UNK) for i in ids]

# ----------------------------
# Padding & attention mask
# ----------------------------
def pad_sequence(seq: List[int], max_len: int, pad_id: int) -> List[int]:
    if len(seq) >= max_len:
        return seq[:max_len]
    return seq + [pad_id] * (max_len - len(seq))

def create_attention_mask(seq_ids: List[int], pad_id: int) -> List[int]:
    return [0 if tok == pad_id else 1 for tok in seq_ids]

# ----------------------------
# Decoder state inference
# ----------------------------
def infer_decoder_state(tokens: List[str]) -> str:
    """
    IMPORTANT:
    This function is ORDER-SENSITIVE.
    Later SQL clauses must dominate earlier ones.
    """

    if not tokens or tokens[-1] == START:
        return "START"

    # JOIN states (highest priority after FROM)
    if any(j in tokens for j in [
        INNER_JOIN, LEFT_JOIN, RIGHT_JOIN, FULL_JOIN, CROSS_JOIN
    ]):
        if ON in tokens and tokens[-1] != ON:
            return "JOIN_ON"
        return "JOIN"

    # GROUP BY → HAVING
    if GROUP_BY in tokens and HAVING not in tokens:
        return "GROUP_BY"

    if HAVING in tokens:
        return "HAVING"

    # WHERE (only before GROUP BY)
    if WHERE in tokens and GROUP_BY not in tokens:
        return "WHERE"

    # FROM
    if FROM in tokens and not any(
        x in tokens for x in [WHERE, GROUP_BY, HAVING]
    ):
        return "FROM"

    # SELECT
    if SELECT in tokens and FROM not in tokens:
        return "SELECT"

    # ORDER / LIMIT
    if ORDER_BY in tokens:
        return "ORDER_BY"

    if LIMIT in tokens or OFFSET in tokens:
        return "LIMIT_OFFSET"

    return "END"

# ----------------------------
# Allowed token mask
# ----------------------------
# utils.py (PATCH ONLY — rest unchanged)

def get_allowed_tokens(tokens_so_far, schema_tables, schema_columns):
    state = infer_decoder_state(tokens_so_far)
    allowed = set()

    # ---------- START ----------
    if state == "START":
        allowed.add(TOKEN2ID[SELECT])

    # ---------- SELECT ----------
    elif state == "SELECT":
        allowed |= {TOKEN2ID[a] for a in AGG_FUNCS}
        allowed.add(TOKEN2ID[SCHEMA_COLUMN])
        allowed.add(TOKEN2ID[FROM])   # 🔥 REQUIRED FOR Phase-4

    # ---------- FROM ----------
    elif state == "FROM":
        allowed.add(TOKEN2ID[SCHEMA_TABLE])
        allowed.add(TOKEN2ID[JOIN])
        allowed.add(TOKEN2ID[END])

    # ---------- JOIN ----------
    elif state == "JOIN":
        allowed.add(TOKEN2ID[SCHEMA_TABLE])

    elif state == "JOIN_ON":
        allowed |= {
            TOKEN2ID[ON],
            TOKEN2ID[SCHEMA_COLUMN]
        }

    # ---------- WHERE ----------
    elif state == "WHERE":
        allowed.add(TOKEN2ID[SCHEMA_COLUMN])

    # ---------- GROUP BY ----------
    elif state == "GROUP_BY":
        allowed.add(TOKEN2ID[SCHEMA_COLUMN])
        allowed |= {TOKEN2ID[HAVING], TOKEN2ID[END]}

    # ---------- HAVING ----------
    elif state == "HAVING":
        allowed |= {TOKEN2ID[a] for a in AGG_FUNCS}
        allowed.add(TOKEN2ID[SCHEMA_COLUMN])

    # ---------- END ----------
    else:
        allowed.add(TOKEN2ID[END])

    # ========= UNIVERSAL (SAFE) =========

    # Operators ONLY valid after column in WHERE / HAVING
    if tokens_so_far and tokens_so_far[-1] == SCHEMA_COLUMN:
        if state in {"WHERE", "HAVING"}:
            allowed |= {TOKEN2ID[o] for o in OPS}

    if tokens_so_far and tokens_so_far[-1] in OPS:
        allowed.add(TOKEN2ID[VALUE])

    if tokens_so_far and tokens_so_far[-1] == VALUE:
        allowed |= {TOKEN2ID[AND], TOKEN2ID[OR], TOKEN2ID[END]}

    return allowed'''

# 

# below is of gemini for phase4 join + where
# ============================================================
# utils.py — PHASE-3 SAFE (BACKWARD COMPATIBLE)
# ============================================================
import torch
import random
import numpy as np
from typing import List, Set

from src.vocab import *

# ----------------------------
# Reproducibility
# ----------------------------
def set_seed(seed: int = 42):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)

def get_device():
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")

# ----------------------------
# Token ↔ ID helpers
# ----------------------------
def tokens_to_ids(tokens: List[str]) -> List[int]:
    return [TOKEN2ID.get(t, TOKEN2ID[UNK]) for t in tokens]

def ids_to_tokens(ids: List[int]) -> List[str]:
    return [ID2TOKEN.get(i, UNK) for i in ids]

# ----------------------------
# Padding & attention mask
# ----------------------------
def pad_sequence(seq: List[int], max_len: int, pad_id: int) -> List[int]:
    if len(seq) >= max_len:
        return seq[:max_len]
    return seq + [pad_id] * (max_len - len(seq))

def create_attention_mask(seq_ids: List[int], pad_id: int) -> List[int]:
    return [0 if tok == pad_id else 1 for tok in seq_ids]

# ----------------------------
# Decoder state inference
# ----------------------------

def infer_decoder_state(tokens: List[str]) -> str:
    """
    Identifies the model's current position in the SQL structure.
    """
    if not tokens or tokens[-1] == START:
        return "START"

    last_token = tokens[-1]

    # --- 1. JOIN SEQUENCE TRACKING ---
    if last_token in [JOIN, INNER_JOIN, LEFT_JOIN]: return "JOIN_EXPECT_TABLE"
    if last_token == ON: return "JOIN_CONDITION_1"
    
    if ON in tokens:
        on_idx = len(tokens) - 1 - tokens[::-1].index(ON)
        tokens_since_on = tokens[on_idx+1:]
        # Patterns match the dataset generator: ON <COLUMN> <COLUMN>
        if len(tokens_since_on) == 1 and tokens_since_on[0] == SCHEMA_COLUMN:
            return "JOIN_CONDITION_2"
        if len(tokens_since_on) == 2:
            return "JOIN_FINISHED"

    # --- 2. CLAUSE DOMINANCE ---
    if LIMIT in tokens or OFFSET in tokens: return "LIMIT_OFFSET"
    if ORDER_BY in tokens: return "ORDER_BY"
    if HAVING in tokens: return "HAVING"
    if GROUP_BY in tokens: return "GROUP_BY"
    if WHERE in tokens: return "WHERE"
    
    if len(tokens) > 1 and tokens[-2] in [JOIN, INNER_JOIN, LEFT_JOIN]:
        return "JOIN_EXPECT_ON"

    if FROM in tokens: return "FROM"
    if SELECT in tokens: return "SELECT"

    return "END"

def get_allowed_tokens(tokens_so_far, schema_tables=None, schema_columns=None, intent_signals=None):
    state = infer_decoder_state(tokens_so_far)
    allowed = set()
    def add_safe(t):
        if t in TOKEN2ID: allowed.add(TOKEN2ID[t])

    last_token = tokens_so_far[-1] if tokens_so_far else None

    # Logic for START, SELECT, and FROM remains standard [cite: 163, 164]
    if state == "START":
        add_safe(SELECT)
    elif state == "SELECT":
        add_safe(AGG)
        add_safe(SCHEMA_COLUMN)
        add_safe(FROM)
    elif state == "FROM":
        add_safe(SCHEMA_TABLE)
        if last_token == SCHEMA_TABLE:
            for t in [JOIN, WHERE, GROUP_BY, ORDER_BY, END]: add_safe(t)
    elif state == "JOIN_FINISHED":
        # 🔥 INTENT BIAS: If a WHERE signal was detected, force it by blocking <END>
        options = [JOIN, WHERE, GROUP_BY, ORDER_BY, END]
        if intent_signals and intent_signals.get("where") and END in options:
            options.remove(END)
        for t in options: add_safe(t)

    # JOIN structural transitions [cite: 164, 165]
    elif state == "JOIN_EXPECT_TABLE":
        add_safe(SCHEMA_TABLE)
    elif state == "JOIN_EXPECT_ON":
        add_safe(ON)
    elif state in ["JOIN_CONDITION_1", "JOIN_CONDITION_2"]:
        add_safe(SCHEMA_COLUMN)

    elif state == "JOIN_FINISHED":
        # 🔥 INTENT BIAS: If WHERE signal exists in NL, block END to force WHERE
        options = [JOIN, WHERE, GROUP_BY, ORDER_BY, END]
        if intent_signals and intent_signals.get("where") and END in options:
            options.remove(END)
        for t in options: add_safe(t)

    elif state == "WHERE":
        add_safe(SCHEMA_COLUMN)
        if last_token == VALUE:
            for t in [AND, OR, GROUP_BY, ORDER_BY, END]: add_safe(t)

    elif state == "GROUP_BY":
        add_safe(SCHEMA_COLUMN)
        if last_token == SCHEMA_COLUMN:
            # 🔥 INTENT BIAS: Force HAVING if needed
            opts = [HAVING, ORDER_BY, END]
            if intent_signals and intent_signals.get("having") and END in opts:
                opts.remove(END)
            for t in opts: add_safe(t)

    # Universal operator and value rules [cite: 166, 178]
    if last_token == SCHEMA_COLUMN:
        if state in ["WHERE", "HAVING", "JOIN_CONDITION_1", "JOIN_CONDITION_2"]:
            for o in OPS: add_safe(o)
    if last_token in OPS:
        add_safe(VALUE)
        add_safe(SCHEMA_COLUMN) 

    if not allowed: add_safe(END)
    return allowed