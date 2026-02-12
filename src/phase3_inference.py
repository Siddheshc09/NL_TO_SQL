# # 🔹 Cell 1 — imports

import torch
import sys
sys.path.append("..")

from src.schema_parser import SchemaParser
from src.nl_parser import NLParser
from src.semantic_aligner import SemanticAligner
from src.schema_binder import bind_schema_tokens
from src.ast_renderer import SQLRenderer
from src.phase2_inference import infer_phase2_sql
from src.utils import (
    tokens_to_ids,
    ids_to_tokens,
    create_attention_mask,
    get_device
)

from src.vocab import PAD
from models.sql_transformer import SQLTransformer

# # 🔹 Cell 4 — inference
def infer_phase3_sql(schema_json, nl_query):
    # ==================================================
    # 1️⃣ Schema parsing
    # ==================================================
    schema_parser = SchemaParser(schema_json)
    tables = schema_parser.get_tables()
    all_columns = schema_parser.get_all_columns()
    #print(tables)
    #print(all_columns)

    # ==================================================
    # 2️⃣ NL parsing
    # ==================================================
    nl_parser = NLParser()
    signals = nl_parser.parse(nl_query)
    nl_lower = nl_query.lower()
    #print(signals)
    # ==================================================
    # 🔒 VALIDATION: HAVING requires aggregation
    # ==================================================
    if signals.get("having") and not signals["aggregations"]:
        raise ValueError("❌ HAVING clause requires aggregation")

    # ==================================================
    # 3️⃣ Resolve TABLE
    # ==================================================
    resolved_table = None
    for t in signals["entities"]:
        if t in tables:
            resolved_table = t
            break

    if resolved_table is None:
        raise ValueError("❌ Could not resolve table from NL query")

    # ==================================================
    # 4️⃣ Semantic alignment
    # ==================================================
    aligner = SemanticAligner()
    mapping = aligner.align(
        user_terms=signals["entities"],
        schema_terms=all_columns,
        column_terms=all_columns
    )
    #print(mapping)
    # ==================================================
    # 5️⃣ Resolve SELECT (BACKWARD COMPATIBLE)
    # ==================================================
    select_items = []

    is_pure_projection = (
        not signals["aggregations"]
        and not signals.get("group_by")
        and not signals.get("having")
    )

    # ----------------------------------
    # 🔁 Phase-1 / Phase-2 behavior
    # ----------------------------------
    if is_pure_projection:
        for term, mapped in mapping.items():
            if mapped.startswith(resolved_table + ".") and term in nl_lower:
                select_items.append({
                    "agg": None,
                    "column": mapped.split(".")[1]
                })

        if not select_items:
            raise ValueError("❌ No SELECT columns resolved")

    # ----------------------------------
    # 🧠 Phase-3 aggregation behavior
    # ----------------------------------
    else:
        agg = signals["aggregations"][0].upper()

        preferred_cols = [
            mapped for term, mapped in mapping.items()
            if mapped.startswith(resolved_table + ".") and term in nl_lower
        ]

        if not preferred_cols:
            heuristic_numeric = {
                "salary", "age", "marks", "amount",
                "price", "quantity", "weight", "total"
            }
            preferred_cols = [
                f"{resolved_table}.{c}"
                for c in schema_parser.get_columns(resolved_table)
                if c in heuristic_numeric
            ]

        if not preferred_cols:
            raise ValueError("❌ No valid aggregation column found")

        select_items.append({
            "agg": agg,
            "column": preferred_cols[0].split(".")[1]
        })

    # ==================================================
    # 6️⃣ GROUP BY (MULTI + SAFE)
    # ==================================================
    group_by_cols = []
    seen = set()

    agg_col = select_items[0]["column"] if select_items[0]["agg"] else None

    for g in signals.get("group_by", []):
        if g == agg_col:
            continue

        col = schema_parser.resolve_column(resolved_table, g)
        if col and col not in seen:
            group_by_cols.append(col)
            seen.add(col)

    # ==================================================
    # 7️⃣ HAVING (MULTI + BACKWARD SAFE)
    # ==================================================
    having_clause = []

    # ----------------------------------
    # ✅ MULTI-HAVING (preferred)
    # ----------------------------------
    if signals.get("having_conditions"):
        for cond in signals["having_conditions"]:
            having_clause.append({
                "agg": cond["agg"].upper(),
                "column": select_items[0]["column"],
                "op": cond["op"],
                "value": cond["value"]
            })

    # ----------------------------------
    # 🔁 BACKWARD FALLBACK (single HAVING)
    # ----------------------------------
    elif signals.get("having"):
        having_agg = (
            signals["having_agg"].upper()
            if signals.get("having_agg")
            else signals["aggregations"][0].upper()
        )

        having_clause.append({
            "agg": having_agg,
            "column": select_items[0]["column"],
            "op": signals["operator"],
            "value": signals["having_value"]
        })

    # ==================================================
    # 🔟 Render SQL
    # ==================================================
    renderer = SQLRenderer()
    sql = renderer.render({
        "select": select_items,
        "from": [resolved_table],
        "where": [],
        "group_by": group_by_cols,
        "having": having_clause,
        "having_logic": signals.get("having_logic", "AND")
    })
    return sql