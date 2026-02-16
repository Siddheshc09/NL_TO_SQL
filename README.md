# NL to SQL Transformer (4LA-CGT)

A modular Natural Language to SQL system using an encoder-only Transformer with phase-wise curriculum learning: from simple `SELECT` through `WHERE`, aggregates, `GROUP BY`/`HAVING`, and multi-table JOINs (INNER, LEFT, RIGHT).

---

## About

This repository contains a curriculum-trained NL-to-SQL model that translates natural language questions into SQL over a user-defined schema. It supports single-table queries, filters (`WHERE`), aggregations (`COUNT`, `SUM`, `AVG`, etc.), `GROUP BY`, `HAVING`, and multi-table JOINs (INNER, LEFT, RIGHT). Training is phase-wise: each phase adds a new capability (e.g. Phase 1 = SELECT, Phase 2 = + WHERE, Phase 4.5 = JOINs). Use the notebooks to train from scratch or run inference with your own schema and questions.



---

## Architecture Overview

The pipeline maps a natural language question and a schema to executable SQL via:

1. **Schema parsing** — Tables, columns, and PK/FK from a JSON schema.
2. **NL parsing** — Tokenization and intent detection (e.g., aggregation, join, filters).
3. **Semantic alignment** — Matching NL phrases to schema elements (e.g., "salary" → `employees.salary`).
4. **Schema binding** — Replacing abstract tokens (`<TABLE>`, `<COLUMN>`) with resolved table/column names.
5. **Transformer** — Encoder-only model that autoregressively generates SQL token sequences with grammar masking.
6. **AST adapter & renderer** — Token sequence → internal AST → final SQL string.

Grammar and schema constraints are enforced during decoding via `get_allowed_tokens()`, so the model only emits valid next tokens (e.g., valid columns for the chosen table, valid join types).

---

## Project Structure

```
nl_To_sql_4LA_CGT/
├── app/                              # Web application (FastAPI)
│   ├── main.py                       # FastAPI app, static/template mounting
│   ├── routes.py                     # API routes (e.g. /generate)
│   ├── inference_service.py          # NL → SQL inference
│   ├── model_loader.py               # Load transformer checkpoints
│   └── schemas.py                    # Request/response schemas
├── templates/                        # HTML templates
│   └── index.html                    # Web UI for NL-to-SQL
├── static/                           # Frontend assets
│   ├── style.css
│   └── app.js
├── data/
│   ├── create_sql_ast_phases.ipynb   # Builds phase-wise AST datasets
│   └── sql_ast/
│       ├── phase1_simple_select.json
│       ├── phase2_select_where.json
│       ├── phase3_groupby_having.json
│       ├── phase4_join.json
│       └── phase4.5_join.json
├── models/
│   └── sql_transformer.py            # Encoder-only Transformer + grammar masking
├── notebooks/
│   ├── 01_phase1_select.ipynb        # Phase 1: SELECT col FROM table
│   ├── 02_phase2_select_where.ipynb  # Phase 2: + WHERE
│   ├── 03_phase3_agg_groupby_having.ipynb  # Phase 3: Aggregations, GROUP BY, HAVING
│   ├── 04_phase4_join.ipynb         # Phase 4: JOIN / INNER JOIN
│   ├── 04.5_phase4.5_join.ipynb     # Phase 4.5: LEFT JOIN, RIGHT JOIN
│   ├── phase1_test.ipynb … phase4.5_test.ipynb  # Inference notebooks per phase
│   └── checkpoints/                  # Saved .pt weights (gitignored)
├── src/
│   ├── __init__.py
│   ├── schema_parser.py              # Parse schema JSON
│   ├── nl_parser.py                  # NL tokenization / intent
│   ├── semantic_aligner.py           # NL ↔ schema alignment
│   ├── schema_binder.py              # Bind <TABLE>/<COLUMN> to schema
│   ├── ast_adapter.py                # Token sequence → AST
│   ├── ast_renderer.py               # AST → SQL string
│   ├── where_parser.py               # WHERE clause parsing
│   ├── phase2_inference.py           # Phase 2 inference
│   ├── phase3_inference.py           # Phase 3 inference (uses Phase 2)
│   ├── utils.py                      # Training helpers, masking
│   ├── vocab.py                      # Token vocab, SQL keywords, placeholders
│   └── ...
├── requirements.txt                  # Python dependencies
├── .env                              # Optional: env vars (gitignored)
├── .gitignore
└── README.md
```

---

## Phase-wise Learning

| Phase | Scope | Description |
|-------|--------|-------------|
| **1** | Simple SELECT | `SELECT <COLUMN> FROM <TABLE>` |
| **2** | SELECT + WHERE | Add `WHERE` with comparisons and AND/OR |
| **3** | Aggregations | `COUNT`, `SUM`, `AVG`, `MIN`, `MAX`, `GROUP BY`, `HAVING` |
| **4** | JOIN | Two-table `JOIN` / `INNER JOIN` with `ON` |
| **4.5** | LEFT / RIGHT JOIN | `LEFT JOIN`, `RIGHT JOIN` in addition to INNER |

Each phase builds on the previous: later notebooks load earlier phase checkpoints and extend the vocabulary and grammar (e.g., join types, aggregate placeholders). Training uses the corresponding `sql_ast/*.json` datasets.

---

## Model Details

- **Type:** Encoder-only Transformer (PyTorch `nn.TransformerEncoder`).
- **Input:** Tokenized NL + schema-bound input (e.g. `SELECT <COLUMN> FROM <TABLE> …`) with padding/masking.
- **Output:** Autoregressive SQL token sequence with **grammar masking** so only valid next tokens are allowed (schema + SQL grammar).
- **Typical config:** `d_model=128`, `nhead=4`, `num_layers=4`, `dim_ff=256`, `dropout=0.1`. Vocabulary includes SQL keywords, placeholders (`<TABLE>`, `<COLUMN>`, `<VALUE>`, `<AGG>`, etc.), and schema-derived tokens.

---

## Features

- **JOIN support:** INNER, LEFT, RIGHT (and vocabulary for FULL/CROSS if needed).
- **GROUP BY and HAVING:** Aggregations and group filtering.
- **Schema-aware decoding:** Only valid columns/tables and next grammar tokens are permitted.
- **User schema:** JSON schema with tables, columns, optional PK/FK for join resolution.

---

## Example: NL → SQL

**Input (NL):**  
`"show first_name and dept_name from employees and departments where dept_name is ai"`

**Schema:**  
Tables `employees`, `departments` with appropriate columns and FK (e.g. `employees.dept_id` → `departments.dept_id`).

**Output (SQL):**  
```sql
SELECT employees.first_name, departments.dept_name
FROM employees
JOIN departments ON employees.dept_id = departments.dept_id
WHERE departments.dept_name = 'ai'
```

(Exact output depends on trained checkpoints and schema binding.)

---

## Installation

1. **Clone the repo**
   ```bash
   git clone https://github.com/Siddheshc09/NL_TO_SQL.git
   cd NL_TO_SQL
   ```

2. **Python environment** (Python 3.8+ recommended)
   ```bash
   python -m venv .venv
   .venv\Scripts\activate   # Windows
   # source .venv/bin/activate  # Linux/macOS
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```
   This installs FastAPI, Uvicorn, Jinja2, PyTorch, sentence-transformers, tqdm, and other required packages.

4. **Optional:** Add a `.env` file in the project root for API keys or custom paths. Do not commit `.env` (it is in `.gitignore`).

---

## Run the project locally

The project includes a **web app** (FastAPI) so you can run NL-to-SQL from the browser.

1. **From the project root** (the folder that contains `app/`, `templates/`, `static/`, and `requirements.txt`):
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

2. **Open in browser**
   - Web UI: [http://localhost:8000](http://localhost:8000)
   - API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

3. **Using the API**
   - **POST** `/generate` with JSON body: `{"db_schema": <your_schema>, "question": "<natural language question>"}`  
   - Response includes `generated_sql` or an `error` message.

**Note:** The app loads the Phase 4.5 checkpoint by default (`notebooks/checkpoints/phase4_5_best.pt`). Train the model using the notebooks first, or change `MODEL_PATH` in `app/model_loader.py` to use another checkpoint.

---

## How to Train

1. **Phase 1**  
   Open `notebooks/01_phase1_select.ipynb`, run all cells. Saves e.g. `notebooks/checkpoints/phase1_model.pt`.

2. **Phase 2**  
   Open `notebooks/02_phase2_select_where.ipynb`. It loads Phase 1 checkpoint and trains Phase 2. Saves `phase2_model.pt`.

3. **Phase 3**  
   Open `notebooks/03_phase3_agg_groupby_having.ipynb`. Load Phase 1/2 checkpoints, train Phase 3. Saves `phase3_model.pt`.

4. **Phase 4**  
   Open `notebooks/04_phase4_join.ipynb`. Load Phase 3 (and optionally Phase 4) checkpoint, train JOIN model. Saves to `notebooks/checkpoints/phase4_join/`.

5. **Phase 4.5**  
   Open `notebooks/04.5_phase4.5_join.ipynb`. Load Phase 3 (and Phase 4.5) checkpoint, train LEFT/RIGHT JOIN. Saves to `notebooks/checkpoints/phase4_5_join/` (e.g. `phase4_5_best.pt`).

Run notebooks from the **project root** (parent of `notebooks/`) so that `sys.path` and paths like `checkpoints/...` and `notebooks/checkpoints/...` resolve correctly.

---

## How to Run Inference

- **Phase 2:** Use `notebooks/phase2_test.ipynb` or call `infer_phase2_sql(schema_json, nl_query)` from `src.phase2_inference`.
- **Phase 3:** Use `notebooks/phase3_test.ipynb` or `infer_phase3_sql(schema_json, nl_query)` from `src.phase3_inference`.
- **Phase 4 / 4.5:** Use `notebooks/phase4_test.ipynb` or `notebooks/phase4.5_test.ipynb`: load the corresponding `.pt` checkpoint into `SQLTransformer`, then run the inference cells with your `USER_SCHEMA` and `USER_NL_QUERY`.

Ensure the checkpoint path in the notebook matches where you saved the model (e.g. `checkpoints/phase4_model.pt` or `notebooks/checkpoints/phase4_5_join/phase4_5_best.pt`).

---

## Future Improvements

- Add `ORDER BY` and `LIMIT`/`OFFSET` to the grammar and phases.
- Support more than two tables in a single query (multi-way JOINs).
- Optional: use a pre-trained encoder (e.g. BERT) for NL encoding.
- Evaluation on standard benchmarks (e.g. Spider, WikiSQL).
- Export to a small CLI or REST API for easy integration.

---

## License

MIT License. See `LICENSE` file in the repository for full text.
