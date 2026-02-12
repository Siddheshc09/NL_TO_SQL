# below one is after updating for left join


class SQLRenderer:
    """
    SQL AST → SQL string renderer

    Supports:
    - Phase-1: SELECT / FROM
    - Phase-2: WHERE (flat + recursive)
    - Phase-3: AGGREGATION, GROUP BY, HAVING
    - Phase-3+: Multi-HAVING with AND / OR
    - Phase-4: JOINs (INNER / LEFT, multiple joins)

    ⚠️ Backward compatible with all previous phases
    """

    # =============================
    # Public entry
    # =============================
    def render(self, ast: dict) -> str:
        sql = "SELECT "

        # ---------- SELECT ----------
        sql += ", ".join(
            self._render_select(item) for item in ast.get("select", [])
        )

        
        # ---------- FROM ----------
        from_tables = [
            t for t in ast.get("from", [])
            if t and not t.startswith("<")
        ]
        
        if not from_tables:
            raise ValueError("❌ Renderer received unresolved <TABLE> in FROM clause")
        
        sql += " FROM " + ", ".join(from_tables)


        # ---------- JOIN (Phase-4) ----------
        if ast.get("joins"):
            for j in ast["joins"]:
                sql += " " + self._render_join(j)

        # ---------- WHERE ----------
        if ast.get("where"):
            sql += " WHERE " + self._render_where(ast["where"])

        # ---------- GROUP BY ----------
        if ast.get("group_by"):
            sql += " GROUP BY " + ", ".join(ast["group_by"])

        # ---------- HAVING ----------
        if ast.get("having"):
            having_logic = ast.get("having_logic", "AND")
            sql += " HAVING " + self._render_having(
                ast["having"], having_logic
            )

        # ---------- ORDER BY (future-safe) ----------
        if ast.get("order_by"):
            sql += " ORDER BY " + ", ".join(
                f"{o['column']} {o['direction'].upper()}"
                for o in ast["order_by"]
            )

        # ---------- LIMIT (future-safe) ----------
        if ast.get("limit") is not None:
            sql += f" LIMIT {ast['limit']}"

        # ---------- OFFSET (future-safe) ----------
        if ast.get("offset") is not None:
            sql += f" OFFSET {ast['offset']}"

        return sql

    # =============================
    # SELECT
    # =============================
    def _render_select(self, item: dict) -> str:
        """
        Examples:
        { "agg": None, "column": "employees.name" }
        { "agg": "SUM", "column": "salary" }
        """
        if item.get("agg"):
            return f"{item['agg']}({item['column']})"
        return item["column"]

    # =============================
    # JOIN (Phase-4)
    # =============================
    def _render_join(self, join: dict) -> str:
        """
        Supports:
        - INNER / LEFT / RIGHT JOIN
        - Extra ON conditions (Phase-4.5)
        """

        join_type = join.get("type", "INNER").upper()
        table = join["table"]
        on = join["on"]

        # Base ON condition
        on_parts = [
            f"{on['left']} {on.get('op', '=')} {on['right']}"
        ]

        # 🔑 Extra ON conditions (LEFT JOIN safety)
        for cond in on.get("extra_conditions", []):
            on_parts.append(self._render_simple_condition(cond))

        on_clause = " AND ".join(on_parts)

        return f"{join_type} JOIN {table} ON {on_clause}"
    

    # =============================
    # WHERE (supports 2 formats)
    # =============================
    def _render_where(self, node):
        """
        Supports:
        1️⃣ Recursive tree:
           { type: "condition" }
           { op: "AND"/"OR", left: {}, right: {} }

        2️⃣ Flat list:
           [ {column, op, value}, ... ]
        """

        # ---- flat WHERE list ----
        if isinstance(node, list):
            return " AND ".join(
                self._render_simple_condition(c) for c in node
            )

        # ---- recursive condition ----
        if node.get("type") == "condition":
            return self._render_simple_condition(node)

        # ---- logical node ----
        left = self._render_where(node["left"])
        right = self._render_where(node["right"])
        return f"({left} {node['op']} {right})"

    def _render_simple_condition(self, cond: dict) -> str:
        val = cond["value"]

        if isinstance(val, (int, float)):
            val = str(val)
        else:
            val = f"'{val}'"

        return f"{cond['column']} {cond['op']} {val}"

    # =============================
    # HAVING
    # =============================
    def _render_having(self, having, logic="AND"):
        """
        Supports:
        - single HAVING condition (dict)
        - multiple HAVING conditions (list)
        - AND / OR logic
        """

        # ---- multiple HAVING ----
        if isinstance(having, list):
            joiner = f" {logic} "
            return joiner.join(
                self._render_having_condition(h) for h in having
            )

        # ---- single HAVING ----
        return self._render_having_condition(having)

    def _render_having_condition(self, h: dict) -> str:
        """
        Example:
        {
          agg: "SUM",
          column: "salary",
          op: ">",
          value: 5000
        }
        """
        val = h["value"]

        if isinstance(val, (int, float)):
            val = str(val)
        else:
            val = f"'{val}'"

        return f"{h['agg']}({h['column']}) {h['op']} {val}"