# 🔹 Cell 4 — Phase-2 Inference Function (CORE LOGIC)
import torch
import sys
sys.path.append("..")

from models.sql_transformer import SQLTransformer
from src.schema_parser import SchemaParser
from src.nl_parser import NLParser
from src.semantic_aligner import SemanticAligner
from src.schema_binder import bind_schema_tokens
from src.ast_renderer import SQLRenderer
from src.where_parser import WhereParser
from src.utils import (
    tokens_to_ids,
    ids_to_tokens,
    create_attention_mask,
    get_device
)
from src.vocab import PAD

def infer_phase2_sql(schema_json, nl_query):
    # 1️⃣ Schema parsing
    schema_parser = SchemaParser(schema_json)
    tables = schema_parser.get_tables()
    columns = schema_parser.get_all_columns()

    # 2️⃣ NL parsing
    nl_parser = NLParser()
    signals = nl_parser.parse(nl_query)

    # 3️⃣ Resolve TABLE
    resolved_table = None
    for t in signals["entities"]:
        if t in tables:
            resolved_table = t
            break

    if resolved_table is None:
        raise ValueError("❌ Could not resolve table")

    table_meta = schema_json["tables"][resolved_table]

    # 🔑 backward + forward compatible
    table_cols = (
        table_meta["columns"]
        if isinstance(table_meta, dict)
        else table_meta
    )


    # 4️⃣ Resolve SELECT columns (STRICT & CORRECT)

    nl_lower = nl_query.lower()
    
    # Extract projection part (before WHERE)
    if "where" in nl_lower:
        projection_part = nl_lower.split("where", 1)[0]
    else:
        projection_part = nl_lower
    
    select_columns = [
        f"{resolved_table}.{col}"
        for col in table_cols
        if col in projection_part
    ]
    
    if not select_columns:
        raise ValueError("❌ No SELECT columns resolved")




    # 5️⃣ WHERE parsing (FULL BOOLEAN SUPPORT)
    where_ast = None
    if "where" in nl_lower:
        where_text = nl_lower.split("where", 1)[1]

        aligner = SemanticAligner()
        where_parser = WhereParser(nl_parser, aligner)

        tokens = where_parser.tokenize(where_text)
        where_ast = where_parser.build_tree(
            tokens,
            resolved_table,
            table_cols,
            columns
        )

    # 6️⃣ Render SQL
    renderer = SQLRenderer()
    sql = renderer.render({
        "select": [{"column": c, "agg": None} for c in select_columns],
        "from": [resolved_table],
        "where": where_ast
    })

    return sql