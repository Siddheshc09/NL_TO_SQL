from src.vocab import (
    SELECT, WHERE, GROUP_BY, HAVING,
    SCHEMA_COLUMN, SCHEMA_TABLE, VALUE,
    JOIN, ON
)

import difflib
import logging

logger = logging.getLogger(__name__)


# ============================================================
# Helper: fuzzy match
# ============================================================
def _fuzzy_match(term, candidates, cutoff=0.6):
    if not candidates:
        return None
    matches = difflib.get_close_matches(term, candidates, n=1, cutoff=cutoff)
    return matches[0] if matches else None


# ============================================================
# Main schema binder (Phase-1 → Phase-4 safe)
# ============================================================
# def bind_schema_tokens(tokens, schema_bindings):
#     """
#     Phase-aware schema token binding.

#     ✔ Phase-1  : SELECT
#     ✔ Phase-2  : WHERE
#     ✔ Phase-3  : GROUP BY / HAVING
#     ✔ Phase-4  : JOIN ... ON ...

#     Does NOT change earlier behaviour.
#     """

#     bound = []

#     # ----------------------------
#     # State tracking
#     # ----------------------------
#     state = "select"
#     join_mode = False
#     on_side = None   # left | right

#     # ----------------------------
#     # Bindings
#     # ----------------------------
#     table_vals = schema_bindings.get("<TABLE>", [])
#     col_vals = schema_bindings.get("<COLUMN>", [])
#     value_val = schema_bindings.get("<VALUE>")

#     table_idx = 0
#     col_idx = 0

#     last_table = None

#     # ========================================================
#     # Token loop
#     # ========================================================
#     for t in tokens:

#         # ---------- STATE ----------
#         if t == SELECT:
#             state = "select"
#             join_mode = False
#             bound.append(t)

#         elif t == WHERE:
#             state = "where"
#             join_mode = False
#             bound.append(t)

#         elif t == GROUP_BY:
#             state = "group_by"
#             join_mode = False
#             bound.append(t)

#         elif t == HAVING:
#             state = "having"
#             join_mode = False
#             bound.append(t)

#         elif t == JOIN:
#             join_mode = True
#             on_side = None
#             bound.append(t)

#         elif t == ON:
#             on_side = "left"
#             bound.append(t)

#         # ---------- TABLE ----------
#         elif t == SCHEMA_TABLE:
#             if isinstance(table_vals, list) and table_vals:
#                 table = table_vals[min(table_idx, len(table_vals) - 1)]
#                 table_idx += 1
#             else:
#                 table = table_vals

#             last_table = table
#             bound.append(table)

#         # ---------- COLUMN ----------
#         elif t == SCHEMA_COLUMN:
#             col = None

#             if isinstance(col_vals, list) and col_vals:
#                 col = col_vals[min(col_idx, len(col_vals) - 1)]
#                 col_idx += 1

#             elif isinstance(col_vals, dict):
#                 col = col_vals.get(state)

#             # Fallback
#             if col is None:
#                 candidates = col_vals if isinstance(col_vals, list) else []
#                 fallback = _fuzzy_match(state, candidates)
#                 if fallback:
#                     col = fallback
#                 else:
#                     col = "<UNRESOLVED_COLUMN>"
#                     logger.warning("Column unresolved, inserting placeholder")

#             bound.append(col)

#             # Switch ON side after left column
#             if join_mode and on_side == "left":
#                 on_side = "right"

#         # ---------- VALUE ----------
#         elif t == VALUE:
#             if isinstance(value_val, (int, float)):
#                 bound.append(str(value_val))
#             else:
#                 bound.append(f"'{value_val}'")

#         # ---------- PASSTHROUGH ----------
#         else:
#             bound.append(t)

#     return bound


# below is of gemini for phase4 join + where

def bind_schema_tokens(tokens, schema_bindings):
    """
    Clause-aware schema binding. Handles bucketed dictionaries 
    with multiple columns per clause.
    """
    bound = []
    state = "select"
    on_side = None   # left | right

    # Extract buckets from schema_bindings
    table_vals = schema_bindings.get("<TABLE>", [])
    col_data = schema_bindings.get("<COLUMN>", [])
    value_vals = schema_bindings.get("<VALUE>", [])
    
    # Ensure value_vals is a list for index tracking
    if not isinstance(value_vals, list):
        value_vals = [value_vals] if value_vals is not None else []

    # 🔥 Independent indices for each clause bucket
    indices = {
        "select": 0, "join_left": 0, "join_right": 0, 
        "where": 0, "group_by": 0, "having": 0, 
        "table": 0, "value": 0
    }

    for t in tokens:
        # ---------- STATE TRACKING ----------
        if t == SELECT: 
            state = "select"
            bound.append(t)
        elif t == WHERE: 
            state = "where"
            bound.append(t)
        elif t == GROUP_BY: 
            state = "group_by"
            bound.append(t)
        elif t == HAVING: 
            state = "having"
            bound.append(t)
        elif t == JOIN: 
            on_side = None # Reset join side
            bound.append(t)
        elif t == ON: 
            on_side = "left"
            bound.append(t)

        # ---------- TABLE BINDING ----------
        elif t == SCHEMA_TABLE:
            idx = indices["table"]
            table = table_vals[min(idx, len(table_vals)-1)] if table_vals else "<UNRESOLVED_TABLE>"
            bound.append(table)
            indices["table"] += 1

        # ---------- COLUMN BINDING ----------
        elif t == SCHEMA_COLUMN:
            col = None
            # Determine which bucket to pull from
            bucket_key = "join_left" if on_side == "left" else "join_right" if on_side == "right" else state
            
            if isinstance(col_data, dict):
                bucket = col_data.get(bucket_key, [])
                # Handle cases where bucket might be a single string instead of a list
                if isinstance(bucket, str):
                    col = bucket
                elif bucket:
                    idx = indices.get(bucket_key, 0)
                    col = bucket[min(idx, len(bucket)-1)]
                    indices[bucket_key] += 1
            else:
                # Backward compatibility for flat lists
                idx = indices["select"]
                col = col_data[min(idx, len(col_data)-1)] if col_data else "<UNRESOLVED_COLUMN>"
                indices["select"] += 1

            bound.append(col or "<UNRESOLVED_COLUMN>")
            
            # Auto-advance JOIN side
            if on_side == "left": 
                on_side = "right"
            elif on_side == "right":
                on_side = None

        # ---------- VALUE BINDING ----------
        elif t == VALUE:
            idx = indices["value"]
            val = value_vals[min(idx, len(value_vals)-1)] if value_vals else "NULL"
            # Format strings with quotes
            bound.append(f"'{val}'" if isinstance(val, str) else str(val))
            indices["value"] += 1

        # ---------- PASSTHROUGH ----------
        else:
            bound.append(t)

    return bound