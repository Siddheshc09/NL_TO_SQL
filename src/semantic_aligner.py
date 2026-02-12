from sentence_transformers import SentenceTransformer, util
from typing import List, Dict, Optional
import difflib
import logging

logger = logging.getLogger(__name__)


class SemanticAligner:
    """
    Semantic aligner with backward compatibility.

    Supports:
    - Phase-1: SELECT
    - Phase-2: WHERE
    - Phase-3: GROUP BY / HAVING
    - Phase-4: JOIN (multi-table, implicit joins)
    """

    def __init__(self):
        self.model = SentenceTransformer("all-MiniLM-L6-v2")

        # --------------------------------------------------
        # Synonym bias (non-breaking, deterministic override)
        # --------------------------------------------------
        self.synonym_bias = {
            # tables
            "employee": "employees",
            "staff": "employees",
            "worker": "employees",
            "department": "departments",

            # columns
            "department name": "dept_name",
            "dept name": "dept_name",
            "employee name": "first_name",
            "employee id": "emp_id",
            "department id": "dept_id",
            "salary": "salary",

            # generic
            "amount": "amount",
            "total": "amount"
        }

    # ==================================================
    # Fuzzy fallback
    # ==================================================
    def _fuzzy_match(
        self,
        term: str,
        candidates: List[str],
        cutoff: float = 0.6
    ) -> Optional[str]:
        matches = difflib.get_close_matches(
            term, candidates, n=1, cutoff=cutoff
        )
        return matches[0] if matches else None

    # ==================================================
    # Main aligner (STABLE SIGNATURE)
    # ==================================================
    def align(
        self,
        user_terms: List[str],
        schema_terms: List[str],
        column_terms: Optional[List[str]] = None
    ) -> Dict[str, str]:
        """
        Returns mapping:
        {
          "first_name": "employees.first_name",
          "dept_name": "departments.dept_name"
        }
        """

        if not user_terms or not schema_terms:
            return {}

        # -----------------------------------------------
        # Separate schema columns vs tables
        # -----------------------------------------------
        schema_columns = (
            column_terms if column_terms
            else [s for s in schema_terms if "." in s]
        )

        # -----------------------------------------------
        # Encode embeddings
        # -----------------------------------------------
        user_emb = self.model.encode(user_terms, convert_to_tensor=True)
        schema_emb = self.model.encode(schema_columns, convert_to_tensor=True)
        scores = util.cos_sim(user_emb, schema_emb)

        mapping: Dict[str, str] = {}

        # -----------------------------------------------
        # Alignment loop
        # -----------------------------------------------
        for i, term in enumerate(user_terms):

            # -------- synonym override (hard) --------
            if term in self.synonym_bias:
                syn = self.synonym_bias[term]
                for col in schema_columns:
                    if col.endswith("." + syn):
                        mapping[term] = col
                        continue

            # -------- embedding best match --------
            best_idx = scores[i].argmax().item()
            best_score = scores[i][best_idx].item()
            best_match = schema_columns[best_idx]

            # -------- weak confidence guard --------
            if best_score < 0.30:
                fallback = self._fuzzy_match(term, schema_columns)
                if fallback:
                    logger.info(f"Fuzzy matched '{term}' → '{fallback}'")
                    best_match = fallback
                else:
                    logger.warning(f"Low confidence for '{term}', skipped")
                    continue

            # -------- JOIN ambiguity guard --------
            col_name = best_match.split(".")[-1]
            same_cols = [
                s for s in schema_columns
                if s.endswith("." + col_name)
            ]

            if len(same_cols) > 1 and best_score < 0.45:
                logger.warning(
                    f"Ambiguous JOIN column '{term}' → {same_cols}, skipped"
                )
                continue

            mapping[term] = best_match

        return mapping