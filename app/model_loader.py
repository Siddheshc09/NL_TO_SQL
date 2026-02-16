import torch
from models.sql_transformer import SQLTransformer

MODEL_PATH = "notebooks/checkpoints/phase4_5_best.pt"

def load_model():
    model = SQLTransformer()
    model.load_state_dict(torch.load(MODEL_PATH, map_location="cpu"))
    model.eval()
    return model

model = load_model()
