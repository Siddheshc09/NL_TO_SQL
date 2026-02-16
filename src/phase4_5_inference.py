# 🔹 Cell 1 — Imports & Setup
import torch
import sys
import os
sys.path.append("..")

from src.schema_parser import SchemaParser
from src.nl_parser import NLParser
from src.semantic_aligner import SemanticAligner
from src.schema_binder import bind_schema_tokens
from src.ast_adapter import adapt_token_ast
from src.ast_renderer import SQLRenderer
from src.where_parser import WhereParser
from src.phase2_inference import infer_phase2_sql
from src.phase3_inference import infer_phase3_sql

from src.utils import (
    tokens_to_ids,
    ids_to_tokens,
    create_attention_mask,
    get_device,
    get_allowed_tokens
)

from src.vocab import START, PAD, TOKEN2ID, ID2TOKEN, tokens_to_ast,ast_to_tokens
from models.sql_transformer import SQLTransformer


# 🔹 Cell 5 - phase4 Inference updated for right join
def infer_phase4_sql(schema_json, nl_query):
    # ============================================================
    # Phase-4.5 NL → SQL (UPDATED — LEFT + RIGHT JOIN SAFE)
    # ============================================================

    nl_lower = nl_query.lower()
    nl_parser = NLParser()
    signals = nl_parser.parse(nl_query)

    schema_tables = list(schema_json["tables"].keys())
    resolved_tables = [t for t in signals["tables"] if t in schema_tables]

    # ----------------------------
    # Phase routing
    # ----------------------------
    if len(resolved_tables) < 2:
        if signals["aggregations"] or signals["group_by"] or signals["having"]:
            return infer_phase3_sql(schema_json, nl_query)
        return infer_phase2_sql(schema_json, nl_query)

    base_table, join_table = resolved_tables[:2]

    # ----------------------------
    # TRUE aggregation intent
    # ----------------------------
    agg_verbs = ["average", "avg", "count", "number of", "how many"]
    has_agg_intent = any(v in nl_lower for v in agg_verbs)
    plain_join = not has_agg_intent

    # ----------------------------
    # Discover JOIN (schema-agnostic)
    # ----------------------------
    pk_fk = discover_pk_fk_relationships(schema_json)
    rel = next(
        r for r in pk_fk
        if {r["left_table"], r["right_table"]} == {base_table, join_table}
    )

    join_type = signals.get("join_type", "INNER")
    preserve_table = signals.get("preserve_table")

    # ============================================================
    # 🔥 NEW: Derive JOIN type from preserve_table (SAFE & GENERIC)
    # ============================================================
    if preserve_table:
        if preserve_table == base_table:
            join_type = "LEFT"
        elif preserve_table == join_table:
            join_type = "RIGHT"

    ast = {
        "select": [],
        "from": [base_table],
        "joins": [{
            "type": join_type,
            "table": join_table,
            "on": {
                "left": f"{rel['left_table']}.{rel['left_col']}",
                "op": "=",
                "right": f"{rel['right_table']}.{rel['right_col']}",
                "extra_conditions": []
            }
        }],
        "where": None,
        "group_by": [],
        "having": []
    }

    # ============================================================
    # A. PLAIN JOIN (NO AGG)
    # ============================================================
    if plain_join:
        projection_text = nl_lower.split(" where ")[0]

        for t in resolved_tables:
            for c in schema_json["tables"][t]["columns"]:
                if c in projection_text:
                    ast["select"].append({
                        "agg": None,
                        "column": f"{t}.{c}"
                    })

        if not ast["select"]:
            for t in resolved_tables:
                cols = schema_json["tables"][t]["columns"]
                readable = next((c for c in cols if not c.endswith("_id")), cols[0])
                ast["select"].append({
                    "agg": None,
                    "column": f"{t}.{readable}"
                })

        if " where " in nl_lower:
            where_parser = WhereParser(nl_parser, SemanticAligner())
            where_ast = where_parser.build_tree(
                where_parser.tokenize(nl_lower.split("where", 1)[1]),
                base_table,
                schema_json["tables"][base_table]["columns"],
                [
                    f"{t}.{c}"
                    for t in resolved_tables
                    for c in schema_json["tables"][t]["columns"]
                ]
            )

            # ============================================================
            # GENERIC OUTER JOIN WHERE SAFETY
            # ============================================================
            if join_type in ["LEFT", "RIGHT"] and preserve_table:
                preserved = preserve_table
                nullable = join_table if preserved == base_table else base_table

                safe = []
                for cond in where_ast if isinstance(where_ast, list) else [where_ast]:
                    if cond["column"].startswith(f"{nullable}."):
                        ast["joins"][0]["on"]["extra_conditions"].append(cond)
                    else:
                        safe.append(cond)

                ast["where"] = safe or None
            else:
                ast["where"] = where_ast

        return SQLRenderer().render(ast)

    # ============================================================
    # B. AGGREGATION (JOIN + GROUP BY + HAVING)
    # ============================================================

    agg_func = "COUNT" if "count" in nl_lower else "AVG"

    # ----------------------------
    # GROUP BY resolution
    # ----------------------------
    group_col = None

    if " by " in nl_lower:
        after_by = nl_lower.split(" by ", 1)[1]
        for t in resolved_tables:
            for c in schema_json["tables"][t]["columns"]:
                if c in after_by:
                    group_col = f"{t}.{c}"
                    break
            if group_col:
                break

    if not group_col:
        projection_text = nl_lower.split(" where ")[0]
        for t in resolved_tables:
            for c in schema_json["tables"][t]["columns"]:
                if (
                    c in projection_text
                    and not c.endswith("_id")
                ):
                    group_col = f"{t}.{c}"
                    break
            if group_col:
                break

    if not group_col:
        raise ValueError("❌ GROUP BY column not resolved")

    ast["group_by"] = [group_col]

    # ----------------------------
    # Aggregation column (schema-agnostic)
    # ----------------------------
    if agg_func == "COUNT":
        pk = schema_json["tables"][join_table]["pk"]
        agg_col = f"{join_table}.{pk}"
    else:
        agg_col = None
        for t in resolved_tables:
            for c in schema_json["tables"][t]["columns"]:
                if c in nl_lower and not c.endswith("_id"):
                    agg_col = f"{t}.{c}"
                    break
            if agg_col:
                break

        if not agg_col:
            raise ValueError("❌ Aggregation column not resolved")

    ast["select"] = [
        {"agg": None, "column": group_col},
        {"agg": agg_func, "column": agg_col}
    ]

    # ----------------------------
    # HAVING
    # ----------------------------
    if signals["numbers"]:
        ast["having"] = {
            "agg": agg_func,
            "column": agg_col,
            "op": ">",
            "value": int(signals["numbers"][0])
        }

    return SQLRenderer().render(ast)