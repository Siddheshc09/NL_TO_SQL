# # after updating for left join
# import re

# class NLParser:
#     def __init__(self):
#         # ------------------------------
#         # Aggregation keywords
#         # ------------------------------
#         self.agg_map = {
#             "avg": ["average", "mean"],
#             "sum": ["sum", "total"],
#             "count": ["count", "number of", "how many"],
#             "max": ["maximum", "highest", "max"],
#             "min": ["minimum", "lowest", "min"]
#         }

#         # ------------------------------
#         # Textual operators
#         # ------------------------------
#         self.text_ops = {
#             ">=": ["greater than or equal to", "at least"],
#             "<=": ["less than or equal to", "at most"],
#             ">": ["greater than", "more than", "above"],
#             "<": ["less than", "below"],
#             "=": ["equals", "equal to", "is"]
#         }

#         # ------------------------------
#         # Stopwords
#         # ------------------------------
#         self.stopwords = {
#             "show", "get", "find", "list", "of", "from", "where",
#             "in", "on", "and", "or", "the", "is", "with", "by",
#             "having", "for"
#         }

#         # ------------------------------
#         # Synonym normalization
#         # ------------------------------
#         self.synonyms = {
#             "department name": "dept_name",
#             "employee name": "emp_name",
#             "employee id": "emp_id",
#             "product name": "product_name",
#             "product id": "product_id",
#             "salary": "salary",
#             "age": "age"
#         }
#          # 🔑 cache all aggregation words
#         self.agg_words = set()
#         for kws in self.agg_map.values():
#             self.agg_words.update(kws)

#     # ==================================================
#     # Normalize entities
#     # ==================================================
#     def normalize_entities(self, entities):
#         normalized = []
#         for e in entities:
#             key = e.strip().lower()
#             normalized.append(self.synonyms.get(key, e))
#         return normalized

#     # ==================================================
#     # Main parse
#     # ==================================================
#     def parse(self, query: str):
#         query = query.lower()

#         signals = {
#             "aggregations": [],
#             "entities": [],
#             "numbers": [],
#             "strings": [],
#             "operator": "=",
#             "value": None,
#             "intent": "select",
#             "group_by": [],
#             "where": False,
#             "where_conditions": [],
#             "having": False,
#             "having_agg": None,
#             "having_value": None,
#             "having_conditions": [],
#             "having_logic": "AND",
#             "tables": [],
#             "join": False,
#             # 🔥 NEW
#             "join_type": "INNER",
#             "join_confidence": "implicit"
#         }

#         # ------------------------------
#         # Aggregations
#         # ------------------------------
#         for agg, kws in self.agg_map.items():
#             if any(kw in query for kw in kws):
#                 signals["aggregations"].append(agg)

#         if signals["aggregations"]:
#             signals["intent"] = "aggregation"

#         # ------------------------------
#         # Numbers & strings
#         # ------------------------------
#         signals["numbers"] = re.findall(r"\b\d+\b", query)
#         quoted = re.findall(r"'(.*?)'|\"(.*?)\"", query)
#         signals["strings"] = [q[0] or q[1] for q in quoted]

#         # ------------------------------
#         # Tokenize
#         # ------------------------------
#         tokens = re.findall(r"[a-zA-Z_]+", query)
#         tokens = [t for t in tokens if t not in self.stopwords]
#         tokens = self.normalize_entities(tokens)
#         signals["entities"] = tokens

#         # ------------------------------
#         # Table extraction
#         # ------------------------------
#         tables = [
#             t for t in tokens
#             if (
#                 "_" not in t
#                 and t.isalpha()
#                 and t not in self.agg_words     # 🔥 key fix
#             )
#         ]

#         signals["tables"] = list(dict.fromkeys(tables))
#         signals["join"] = len(signals["tables"]) >= 2

#         # ------------------------------
#         # 🔥 JOIN TYPE DETECTION (NEW)
#         # ------------------------------
#         if signals["join"]:
#             # Explicit LEFT JOIN intent
#             left_join_phrases = [
#                 "with or without",
#                 "even if",
#                 "including",
#                 "including those",
#                 "all",
#                 "their"
#             ]

#             if any(p in query for p in left_join_phrases):
#                 signals["join_type"] = "LEFT"
#                 signals["join_confidence"] = "explicit"

#             # RIGHT JOIN (rare, but supported)
#             elif query.startswith("orders and their") or query.startswith("all orders"):
#                 signals["join_type"] = "RIGHT"
#                 signals["join_confidence"] = "explicit"

#             else:
#                 signals["join_type"] = "INNER"
#         # ------------------------------
#         # WHERE & Multi-Condition Detection
#         # ------------------------------
#         if " where " in query:
#             signals["where"] = True
#             where_clause = query.split(" where ", 1)[1]
#             # Split by logic operators 'and' or 'or'
#             parts = re.split(r'\b(and|or)\b', where_clause)
            
#             for part in parts:
#                 part = part.strip()
#                 if part in ['and', 'or'] or not part:
#                     continue
                
#                 # Extract specific entities and values within this chunk
#                 chunk_entities = re.findall(r"[a-zA-Z_]+", part)
#                 chunk_entities = [self.synonyms.get(e, e) for e in chunk_entities if e not in self.stopwords]
                
#                 chunk_nums = re.findall(r"\b\d+\b", part)
#                 chunk_strs = re.findall(r"'(.*?)'|\"(.*?)\"", part)
#                 chunk_val = (chunk_strs[0][0] or chunk_strs[0][1]) if chunk_strs else (chunk_nums[0] if chunk_nums else None)

#                 # Find which operator fits this chunk
#                 chunk_op = "="
#                 for op, phrases in self.text_ops.items():
#                     if any(phrase in part for phrase in phrases):
#                         chunk_op = op
#                         break
                
#                 if chunk_entities and chunk_val:
#                     signals["where_conditions"].append({
#                         "column": chunk_entities[0],
#                         "operator": chunk_op,
#                         "value": chunk_val
#                     })

#         # Set fallback global values for backward compatibility
#         if signals["strings"]:
#             signals["value"] = signals["strings"][0]
#         elif signals["numbers"]:
#             signals["value"] = int(signals["numbers"][0])

#         # ------------------------------
#         # GROUP BY
#         # ------------------------------
#         if " by " in query:
#             after = query.split(" by ", 1)[1]
#             gb = re.findall(r"[a-zA-Z_]+", after)
#             gb = [g for g in gb if g not in self.stopwords]
#             signals["group_by"] = self.normalize_entities(gb)

#         # ------------------------------
#         # GLOBAL operator (WHERE)
#         # ------------------------------
#         for op, phrases in self.text_ops.items():
#             if any(p in query for p in phrases):
#                 signals["operator"] = op
#                 break

#         if ">=" in query:
#             signals["operator"] = ">="
#         elif "<=" in query:
#             signals["operator"] = "<="
#         elif ">" in query:
#             signals["operator"] = ">"
#         elif "<" in query:
#             signals["operator"] = "<"
#         elif "=" in query:
#             signals["operator"] = "="

#         # ------------------------------
#         # Value
#         # ------------------------------
#         if signals["strings"]:
#             signals["value"] = signals["strings"][0]
#         elif signals["numbers"]:
#             signals["value"] = int(signals["numbers"][0])
#         elif signals["entities"]:
#             signals["value"] = signals["entities"][-1]

#         signals["having_value"] = signals["value"]
#         if signals["value"] is not None:
#             signals["where"] = True

#         # ------------------------------
#         # HAVING detection (FIXED)
#         # ------------------------------
#         if " having " in query:
#             signals["having"] = True
#             having_part = query.split(" having ", 1)[1]

#             if " or " in having_part:
#                 parts = having_part.split(" or ")
#                 signals["having_logic"] = "OR"
#             else:
#                 parts = having_part.split(" and ")
#                 signals["having_logic"] = "AND"

#             for part in parts:
#                 detected_agg = None
#                 for agg, kws in self.agg_map.items():
#                     if any(k in part for k in kws):
#                         detected_agg = agg
#                         break

#                 # 🔑 operator per HAVING condition
#                 detected_op = "="
#                 for op, phrases in self.text_ops.items():
#                     for phrase in phrases:
#                         if phrase in part:
#                             detected_op = op
#                             break
#                     if detected_op != "=":
#                         break

#                 if ">=" in part:
#                     detected_op = ">="
#                 elif "<=" in part:
#                     detected_op = "<="
#                 elif ">" in part:
#                     detected_op = ">"
#                 elif "<" in part:
#                     detected_op = "<"
#                 elif "=" in part:
#                     detected_op = "="

#                 nums = re.findall(r"\b\d+\b", part)
#                 detected_val = int(nums[0]) if nums else None

#                 if detected_agg and detected_val is not None:
#                     signals["having_conditions"].append({
#                         "agg": detected_agg,
#                         "op": detected_op,
#                         "value": detected_val
#                     })

#                     if signals["having_agg"] is None:
#                         signals["having_agg"] = detected_agg
#                         signals["having_value"] = detected_val

#         return signals



# after updating for right join
import re

class NLParser:
    def __init__(self):
        # ------------------------------
        # Aggregation keywords
        # ------------------------------
        self.agg_map = {
            "avg": ["average", "mean"],
            "sum": ["sum", "total"],
            "count": ["count", "number of", "how many"],
            "max": ["maximum", "highest", "max"],
            "min": ["minimum", "lowest", "min"]
        }

        # ------------------------------
        # Textual operators
        # ------------------------------
        self.text_ops = {
            ">=": ["greater than or equal to", "at least"],
            "<=": ["less than or equal to", "at most"],
            ">": ["greater than", "more than", "above"],
            "<": ["less than", "below"],
            "=": ["equals", "equal to", "is"]
        }

        # ------------------------------
        # Stopwords
        # ------------------------------
        self.stopwords = {
            "show", "get", "find", "list", "of", "from", "where",
            "in", "on", "and", "or", "the", "is", "with", "by",
            "having", "for"
        }

        # ------------------------------
        # Synonym normalization
        # ------------------------------
        self.synonyms = {
            "department name": "dept_name",
            "employee name": "emp_name",
            "employee id": "emp_id",
            "product name": "product_name",
            "product id": "product_id",
            "salary": "salary",
            "age": "age"
        }

        # 🔑 cache all aggregation words
        self.agg_words = set()
        for kws in self.agg_map.values():
            self.agg_words.update(kws)

    # ==================================================
    # Normalize entities
    # ==================================================
    def normalize_entities(self, entities):
        normalized = []
        for e in entities:
            key = e.strip().lower()
            normalized.append(self.synonyms.get(key, e))
        return normalized

    # ==================================================
    # Main parse
    # ==================================================
    def parse(self, query: str):
        query = query.lower()

        signals = {
            "aggregations": [],
            "entities": [],
            "numbers": [],
            "strings": [],
            "operator": "=",
            "value": None,
            "intent": "select",
            "group_by": [],
            "where": False,
            "where_conditions": [],
            "having": False,
            "having_agg": None,
            "having_value": None,
            "having_conditions": [],
            "having_logic": "AND",
            "tables": [],
            "join": False,
            # 🔥 existing
            "join_type": "INNER",
            "join_confidence": "implicit",
            # 🔥 NEW (generic outer join support)
            "preserve_table": None
        }

        # ------------------------------
        # Aggregations
        # ------------------------------
        for agg, kws in self.agg_map.items():
            if any(kw in query for kw in kws):
                signals["aggregations"].append(agg)

        if signals["aggregations"]:
            signals["intent"] = "aggregation"

        # ------------------------------
        # Numbers & strings
        # ------------------------------
        signals["numbers"] = re.findall(r"\b\d+\b", query)
        quoted = re.findall(r"'(.*?)'|\"(.*?)\"", query)
        signals["strings"] = [q[0] or q[1] for q in quoted]

        # ------------------------------
        # Tokenize
        # ------------------------------
        tokens = re.findall(r"[a-zA-Z_]+", query)
        tokens = [t for t in tokens if t not in self.stopwords]
        tokens = self.normalize_entities(tokens)
        signals["entities"] = tokens

        # ------------------------------
        # Table extraction
        # ------------------------------
        tables = [
            t for t in tokens
            if (
                "_" not in t
                and t.isalpha()
                and t not in self.agg_words
            )
        ]

        signals["tables"] = list(dict.fromkeys(tables))
        signals["join"] = len(signals["tables"]) >= 2

        # =========================================================
        # 🔥 GENERIC OUTER JOIN DETECTION (SCHEMA-AGNOSTIC)
        # =========================================================
        if signals["join"] and len(signals["tables"]) >= 2:

            table_list = signals["tables"]

            if "including" in query or "without" in query or "with no" in query:

                for t1 in table_list:
                    for t2 in table_list:
                        if t1 == t2:
                            continue

                        # Pattern: <t2> without <t1> → preserve t2 → RIGHT JOIN
                        if (
                            f"{t2} without {t1}" in query
                            or f"{t2} with no {t1}" in query
                        ):
                            signals["join_type"] = "RIGHT"
                            signals["join_confidence"] = "explicit"
                            signals["preserve_table"] = t2

                        # Pattern: <t1> without <t2> → preserve t1 → LEFT JOIN
                        elif (
                            f"{t1} without {t2}" in query
                            or f"{t1} with no {t2}" in query
                        ):
                            signals["join_type"] = "LEFT"
                            signals["join_confidence"] = "explicit"
                            signals["preserve_table"] = t1

            # Preserve backward compatibility
            if signals["preserve_table"] is None:
                left_join_phrases = [
                    "with or without",
                    "even if",
                    "including",
                    "including those",
                    "all",
                    "their"
                ]

                if any(p in query for p in left_join_phrases):
                    signals["join_type"] = "LEFT"
                    signals["join_confidence"] = "explicit"

                elif query.startswith("orders and their") or query.startswith("all orders"):
                    signals["join_type"] = "RIGHT"
                    signals["join_confidence"] = "explicit"

                else:
                    signals["join_type"] = "INNER"

        # ------------------------------
        # WHERE & Multi-Condition Detection
        # ------------------------------
        if " where " in query:
            signals["where"] = True
            where_clause = query.split(" where ", 1)[1]
            parts = re.split(r'\b(and|or)\b', where_clause)
            
            for part in parts:
                part = part.strip()
                if part in ['and', 'or'] or not part:
                    continue
                
                chunk_entities = re.findall(r"[a-zA-Z_]+", part)
                chunk_entities = [
                    self.synonyms.get(e, e)
                    for e in chunk_entities
                    if e not in self.stopwords
                ]
                
                chunk_nums = re.findall(r"\b\d+\b", part)
                chunk_strs = re.findall(r"'(.*?)'|\"(.*?)\"", part)
                chunk_val = (
                    (chunk_strs[0][0] or chunk_strs[0][1])
                    if chunk_strs else
                    (chunk_nums[0] if chunk_nums else None)
                )

                chunk_op = "="
                for op, phrases in self.text_ops.items():
                    if any(phrase in part for phrase in phrases):
                        chunk_op = op
                        break
                
                if chunk_entities and chunk_val:
                    signals["where_conditions"].append({
                        "column": chunk_entities[0],
                        "operator": chunk_op,
                        "value": chunk_val
                    })

        # Fallback global values
        if signals["strings"]:
            signals["value"] = signals["strings"][0]
        elif signals["numbers"]:
            signals["value"] = int(signals["numbers"][0])

        # ------------------------------
        # GROUP BY
        # ------------------------------
        if " by " in query:
            after = query.split(" by ", 1)[1]
            gb = re.findall(r"[a-zA-Z_]+", after)
            gb = [g for g in gb if g not in self.stopwords]
            signals["group_by"] = self.normalize_entities(gb)

        # ------------------------------
        # GLOBAL operator
        # ------------------------------
        for op, phrases in self.text_ops.items():
            if any(p in query for p in phrases):
                signals["operator"] = op
                break

        if ">=" in query:
            signals["operator"] = ">="
        elif "<=" in query:
            signals["operator"] = "<="
        elif ">" in query:
            signals["operator"] = ">"
        elif "<" in query:
            signals["operator"] = "<"
        elif "=" in query:
            signals["operator"] = "="

        # ------------------------------
        # Value
        # ------------------------------
        if signals["strings"]:
            signals["value"] = signals["strings"][0]
        elif signals["numbers"]:
            signals["value"] = int(signals["numbers"][0])
        elif signals["entities"]:
            signals["value"] = signals["entities"][-1]

        signals["having_value"] = signals["value"]
        if signals["value"] is not None:
            signals["where"] = True

        # ------------------------------
        # HAVING detection (UNCHANGED)
        # ------------------------------
        if " having " in query:
            signals["having"] = True
            having_part = query.split(" having ", 1)[1]

            if " or " in having_part:
                parts = having_part.split(" or ")
                signals["having_logic"] = "OR"
            else:
                parts = having_part.split(" and ")
                signals["having_logic"] = "AND"

            for part in parts:
                detected_agg = None
                for agg, kws in self.agg_map.items():
                    if any(k in part for k in kws):
                        detected_agg = agg
                        break

                detected_op = "="
                for op, phrases in self.text_ops.items():
                    for phrase in phrases:
                        if phrase in part:
                            detected_op = op
                            break
                    if detected_op != "=":
                        break

                if ">=" in part:
                    detected_op = ">="
                elif "<=" in part:
                    detected_op = "<="
                elif ">" in part:
                    detected_op = ">"
                elif "<" in part:
                    detected_op = "<"
                elif "=" in part:
                    detected_op = "="

                nums = re.findall(r"\b\d+\b", part)
                detected_val = int(nums[0]) if nums else None

                if detected_agg and detected_val is not None:
                    signals["having_conditions"].append({
                        "agg": detected_agg,
                        "op": detected_op,
                        "value": detected_val
                    })

                    if signals["having_agg"] is None:
                        signals["having_agg"] = detected_agg
                        signals["having_value"] = detected_val

        return signals
