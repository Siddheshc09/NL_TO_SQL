"""
AST Adapter
===========
Bridges token-level AST to renderer-level AST.

This is the SINGLE entry point used by inference.
Supports:
- Phase-1: SELECT
- Phase-2: WHERE
- Phase-3: AGG / GROUP BY / HAVING
- Phase-4: JOINs (single & multiple joins)
"""

def adapt_token_ast(token_ast: dict) -> dict:
    """
    Public API used by notebooks and inference pipeline.
    """
    return adapt_query(token_ast)


def adapt_query(token_ast: dict) -> dict:
    """
    Converts token-level AST into renderer-level AST.
    """

    renderer = {
        "select": [],
        "from": [],
        "joins": [],
        "where": [],
        "group_by": [],
        "having": [],
        "order_by": [],
        "limit": None,
        "offset": None
    }

    # ==================================================
    # SELECT
    # ==================================================
    for item in token_ast.get("select", []):
        renderer["select"].append({
            "agg": item.get("agg"),        # None or AGG
            "column": item["column"],      # fully-qualified
            "alias": item.get("alias")     # optional
        })

    # ==================================================
    # FROM (Phase-1 → Phase-4)
    # ==================================================
    # Phase-1/2/3: ["employees"]
    # Phase-4:     ["products"] (base table)
    renderer["from"] = token_ast.get("from", [])

    # ==================================================
    # JOIN (Phase-4 — NEW, non-breaking)
    # ==================================================
    # token_ast["joins"] format:
    # [
    #   {
    #     "type": "INNER" | "LEFT",
    #     "table": "inventory",
    #     "on": {
    #         "left": "products.product_id",
    #         "right": "inventory.product_id"
    #     }
    #   }
    # ]
    for join in token_ast.get("joins", []):
        renderer["joins"].append({
            "type": join.get("type", "INNER"),   # default INNER
            "table": join["table"],
            "on": {
                "left": join["on"]["left"],
                "op": "=",                        # fixed for now
                "right": join["on"]["right"]
            }
        })

    # ==================================================
    # WHERE (unchanged)
    # ==================================================
    renderer["where"] = token_ast.get("where", [])

    # ==================================================
    # GROUP BY (unchanged)
    # ==================================================
    renderer["group_by"] = token_ast.get("group_by", [])

    # ==================================================
    # HAVING (unchanged, supports multi-conditions upstream)
    # ==================================================
    renderer["having"] = token_ast.get("having", [])

    # ==================================================
    # ORDER BY (future-safe)
    # ==================================================
    renderer["order_by"] = token_ast.get("order_by", [])

    # ==================================================
    # LIMIT / OFFSET (future-safe)
    # ==================================================
    renderer["limit"] = token_ast.get("limit")
    renderer["offset"] = token_ast.get("offset")

    return renderer