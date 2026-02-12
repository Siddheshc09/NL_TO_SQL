import re

class WhereParser:
    def __init__(self, nl_parser, semantic_aligner):
        self.nl_parser = nl_parser
        self.aligner = semantic_aligner

    # -----------------------------
    # Tokenize WHERE clause
    # -----------------------------
    def tokenize(self, where_text: str):
        # keep AND / OR as tokens
        tokens = re.split(r"\b(and|or)\b", where_text)
        return [t.strip() for t in tokens if t.strip()]

    # -----------------------------
    # Build Boolean Expression Tree
    # AND has higher precedence than OR
    # -----------------------------
    def build_tree(self, tokens, table, table_cols, all_columns):
        def precedence(op):
            return 2 if op == "AND" else 1

        values = []
        ops = []

        for tok in tokens:
            tok_upper = tok.upper()
            if tok_upper in ("AND", "OR"):
                while ops and precedence(ops[-1]) >= precedence(tok_upper):
                    values.append(self._combine(ops.pop(), values))
                ops.append(tok_upper)
            else:
                values.append(
                    self.parse_condition(tok, table, table_cols, all_columns)
                )

        while ops:
            values.append(self._combine(ops.pop(), values))

        return values[0]

    def _combine(self, op, values):
        right = values.pop()
        left = values.pop()
        return {
            "type": "boolean",
            "op": op,
            "left": left,
            "right": right
        }

    # -----------------------------
    # Parse a single condition
    # -----------------------------
    # def parse_condition(self, text, table, table_cols, all_columns):
    #     signals = self.nl_parser.parse(text)

    #     # resolve column
    #     column = None
    #     for e in signals["entities"]:
    #         if e in table_cols:
    #             column = f"{table}.{e}"
    #             break

    #     # fallback: semantic alignment
    #     if column is None:
    #         mapping = self.aligner.align(
    #             user_terms=signals["entities"],
    #             schema_terms=all_columns,
    #             column_terms=all_columns
    #         )
    #         for v in mapping.values():
    #             if v.startswith(table + "."):
    #                 column = v
    #                 break

    #     if column is None:
    #         raise ValueError(f"❌ Failed to resolve column in condition: {text}")

    #     return {
    #         "type": "condition",
    #         "column": column,
    #         "op": signals["operator"],
    #         "value": signals["value"]
    #     }
    # -----------------------------
    # Parse a single condition (Updated for Phase-4)
    # -----------------------------
    def parse_condition(self, text, table, table_cols, all_columns):
        # Use the updated NLParser to get entities, operators, and values [cite: 79, 85]
        signals = self.nl_parser.parse(text)

        column = None
        
        # 🔥 FIX: Use Semantic Alignment across ALL schema columns first
        # This allows it to find 'departments.manager_id' even if 'employees' is the base table.
        mapping = self.aligner.align(
            user_terms=signals["entities"],
            schema_terms=all_columns
        )
        
        if mapping:
            # Take the best semantic match from any resolved table [cite: 59, 61]
            column = list(mapping.values())[0]

        # Fallback: Check if the raw entity exists in the provided table_cols
        if column is None:
            for e in signals["entities"]:
                if e in table_cols:
                    column = f"{table}.{e}"
                    break

        if column is None:
            raise ValueError(f"❌ Failed to resolve column in condition: {text}")

        return {
            "type": "condition",
            "column": column,
            "op": signals["operator"],
            "value": signals["value"]
        }