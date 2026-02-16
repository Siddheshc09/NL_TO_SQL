from src.phase4_5_inference import infer_phase4_sql

def generate_sql_from_nl(schema_json, question):
    return infer_phase4_sql(schema_json, question)
