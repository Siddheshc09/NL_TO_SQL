class SchemaParser:
    def __init__(self, schema_json):
        """
        schema_json format:
        {
          "tables": {
              "employees": ["id", "name", "salary"]
          }
        }

        OR (typed schema):
        {
          "tables": {
              "employees": {
                  "numeric": ["id", "salary"],
                  "text": ["name"],
                  "date": []
              }
          }
        }
        """
        self.tables = schema_json["tables"]

        # detect schema style
        sample = next(iter(self.tables.values()))
        self.typed_schema = isinstance(sample, dict)

    # ==================================================
    # EXISTING METHODS (⚠️ UNCHANGED BEHAVIOR)
    # ==================================================
    def get_tables(self):
        return list(self.tables.keys())

    def get_columns(self, table_name):
        if not self.typed_schema:
            return self.tables.get(table_name, [])

        cols = []
        for v in self.tables.get(table_name, {}).values():
            cols.extend(v)
        return cols

    def get_all_columns(self):
        cols = []
        for table in self.get_tables():
            for col in self.get_columns(table):
                cols.append(f"{table}.{col}")
        return cols

    def get_table_columns(self, table):
        """Alias for clarity (non-breaking)."""
        return self.get_columns(table)

    def get_all_columns_with_types(self):
        col_map = {}

        if not self.typed_schema:
            for table, cols in self.tables.items():
                for col in cols:
                    col_map[f"{table}.{col}"] = "text"
            return col_map

        for table, type_map in self.tables.items():
            for t, cols in type_map.items():
                for col in cols:
                    col_map[f"{table}.{col}"] = t

        return col_map

    def get_column_type(self, table, column):
        if not self.typed_schema:
            return "text"

        for t, cols in self.tables.get(table, {}).items():
            if column in cols:
                return t
        return None

    def get_groupable_columns(self, table):
        if not self.typed_schema:
            return self.get_columns(table)

        cols = []
        cols.extend(self.tables[table].get("text", []))
        cols.extend(self.tables[table].get("date", []))
        return cols

    def resolve_column(self, table, col_name):
        """
        Phase-1/2/3 safe resolver
        """
        if col_name in self.get_columns(table):
            return f"{table}.{col_name}"
        return None

    # ==================================================
    # ✅ NEW — Phase-4 JOIN HELPERS (NON-BREAKING)
    # ==================================================
    def column_exists(self, table: str, column: str) -> bool:
        """Check if column exists in a table."""
        return column in self.get_columns(table)

    def resolve_column_global(self, col_name: str, tables: list):
        """
        Resolve column across multiple tables.
        Returns fully-qualified column or None / ambiguous.
        """
        matches = []
        for table in tables:
            if self.column_exists(table, col_name):
                matches.append(f"{table}.{col_name}")

        if len(matches) == 1:
            return matches[0]

        return None  # ambiguous or not found

    def validate_join(self, left_col: str, right_col: str) -> bool:
        """
        Validates join condition:
        left_col = right_col
        """
        try:
            lt, lc = left_col.split(".")
            rt, rc = right_col.split(".")
        except ValueError:
            return False

        return (
            self.column_exists(lt, lc)
            and self.column_exists(rt, rc)
        )

    def infer_join_candidates(self, table_a: str, table_b: str):
        """
        Heuristic FK inference:
        - id ↔ <table>_id
        - same column name
        """
        joins = []

        cols_a = self.get_columns(table_a)
        cols_b = self.get_columns(table_b)

        for ca in cols_a:
            for cb in cols_b:
                if ca == cb:
                    joins.append((f"{table_a}.{ca}", f"{table_b}.{cb}"))

                if ca == f"{table_b[:-1]}_id":
                    joins.append((f"{table_a}.{ca}", f"{table_b}.id"))

                if cb == f"{table_a[:-1]}_id":
                    joins.append((f"{table_a}.id", f"{table_b}.{cb}"))

        return joins