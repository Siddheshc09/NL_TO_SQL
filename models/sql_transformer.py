import torch
import torch.nn as nn
import torch.nn.functional as F

from src.utils import get_allowed_tokens
from src.vocab import PAD, END, START, TOKEN2ID, ID2TOKEN, VOCAB_SIZE


'''class SQLTransformer(nn.Module):
    """
    Encoder-only Transformer with masked decoding support.

    Supports:
    - Phase-1 → Phase-3 (existing)
    - Phase-4 JOINs via external grammar masking (non-breaking)

    Grammar + schema constraints are enforced via get_allowed_tokens().
    """

    def __init__(
        self,
        vocab_size: int = VOCAB_SIZE,
        d_model: int = 128,
        nhead: int = 4,
        num_layers: int = 4,
        dim_ff: int = 256,
        dropout: float = 0.1,
        pad_token: str = PAD,
    ):
        super().__init__()

        self.pad_id = TOKEN2ID[pad_token]
        self.end_id = TOKEN2ID[END]

        # =============================
        # Embeddings
        # =============================
        self.embedding = nn.Embedding(
            vocab_size, d_model, padding_idx=self.pad_id
        )
        self.pos_embedding = nn.Embedding(512, d_model)

        # =============================
        # Transformer encoder
        # =============================
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=nhead,
            dim_feedforward=dim_ff,
            dropout=dropout,
            batch_first=True,
        )

        self.encoder = nn.TransformerEncoder(
            encoder_layer,
            num_layers=num_layers
        )

        # =============================
        # Output projection
        # =============================
        self.fc_out = nn.Linear(d_model, vocab_size)

    # ==================================================
    # Forward pass
    # ==================================================
    def forward(
        self,
        input_ids: torch.Tensor,
        attention_mask: torch.Tensor = None,
    ):
        """
        input_ids: (B, T)
        attention_mask: (B, T) -> 1 = keep, 0 = pad
        """

        B, T = input_ids.size()
        device = input_ids.device

        # positional encoding
        pos_ids = torch.arange(T, device=device).unsqueeze(0).expand(B, T)

        x = self.embedding(input_ids) + self.pos_embedding(pos_ids)

        # Transformer expects: True = masked
        if attention_mask is not None:
            src_key_padding_mask = attention_mask == 0
        else:
            src_key_padding_mask = None

        enc_out = self.encoder(
            x,
            src_key_padding_mask=src_key_padding_mask
        )

        logits = self.fc_out(enc_out)  # (B, T, vocab)
        return logits

    # ==================================================
    # Grammar masking (single decoding step)
    # ==================================================
    def apply_grammar_mask(
        self,
        logits: torch.Tensor,
        tokens_so_far: list,
        schema_tables: list,
        schema_columns: list,
    ):
        """
        logits: (vocab_size,)
        tokens_so_far: List[str]   ⚠️ STRING TOKENS ONLY
        """

        allowed_ids = get_allowed_tokens(
            tokens_so_far=tokens_so_far,
            schema_tables=schema_tables,
            schema_columns=schema_columns,
        )

        # mask everything except allowed tokens
        mask = torch.full_like(logits, float("-inf"))
        for idx in allowed_ids:
            mask[idx] = 0.0

        return logits + mask

    # ==================================================
    # Greedy decoding (inference)
    # ==================================================
    @torch.no_grad()
    def generate(
        self,
        input_ids,
        attention_mask,
        schema_tables,
        schema_columns,
        max_len=100,
    ):
        self.eval()
    
        generated_token_ids = []
        generated_tokens = [START]   # 🔥 CRITICAL FIX
    
        for _ in range(max_len):
            logits = self.forward(input_ids, attention_mask)
            next_logits = logits[:, -1, :][0]
    
            masked_logits = self.apply_grammar_mask(
                next_logits,
                tokens_so_far=generated_tokens,
                schema_tables=schema_tables,
                schema_columns=schema_columns,
            )
    
            if torch.all(masked_logits == float("-inf")):
                print("❌ Grammar dead-end reached")
                break
    
            next_id = torch.argmax(masked_logits).item()
            next_token = ID2TOKEN[next_id]
    
            generated_token_ids.append(next_id)
            generated_tokens.append(next_token)
    
            if next_id == self.end_id:
                break
    
            input_ids = torch.cat(
                [input_ids, torch.tensor([[next_id]], device=input_ids.device)],
                dim=1
            )
            attention_mask = torch.cat(
                [attention_mask, torch.ones((1, 1), device=input_ids.device)],
                dim=1
            )
    
        return generated_token_ids'''

class SQLTransformer(nn.Module):
    def __init__(
        self,
        vocab_size: int = VOCAB_SIZE,
        d_model: int = 128,
        nhead: int = 4,
        num_layers: int = 4,
        dim_ff: int = 256,
        dropout: float = 0.1,
        pad_token: str = PAD,
    ):
        super().__init__()
        self.pad_id = TOKEN2ID[pad_token]
        self.end_id = TOKEN2ID[END]

        self.embedding = nn.Embedding(vocab_size, d_model, padding_idx=self.pad_id)
        self.pos_embedding = nn.Embedding(512, d_model)

        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=nhead,
            dim_feedforward=dim_ff,
            dropout=dropout,
            batch_first=True,
        )
        self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        self.fc_out = nn.Linear(d_model, vocab_size)

    def forward(self, input_ids: torch.Tensor, attention_mask: torch.Tensor = None):
        B, T = input_ids.size()
        device = input_ids.device
        pos_ids = torch.arange(T, device=device).unsqueeze(0).expand(B, T)
        x = self.embedding(input_ids) + self.pos_embedding(pos_ids)
        
        src_key_padding_mask = (attention_mask == 0) if attention_mask is not None else None
        enc_out = self.encoder(x, src_key_padding_mask=src_key_padding_mask)
        return self.fc_out(enc_out)

    def apply_grammar_mask(self, logits, tokens_so_far, schema_tables, schema_columns, allowed_token_fn=None, intent_signals=None):
        # 🔥 FIX: Added intent_signals to the signature
        fn = allowed_token_fn if allowed_token_fn is not None else get_allowed_tokens
        
        # 🔥 FIX: Pass intent_signals into the allowed_token_fn
        allowed_ids = fn(
            tokens_so_far=tokens_so_far,
            schema_tables=schema_tables,
            schema_columns=schema_columns,
            intent_signals=intent_signals 
        )

        mask = torch.full_like(logits, float("-inf"))
        for idx in allowed_ids:
            if idx < logits.size(0): 
                mask[idx] = 0.0
        return logits + mask

    # @torch.no_grad()
    # def generate(
    #     self,
    #     input_ids,
    #     attention_mask,
    #     schema_tables,
    #     schema_columns,
    #     max_len=100,
    #     allowed_token_fn=None, # 🔥 ADDED THIS ARGUMENT
    # ):
    #     self.eval()
    #     generated_token_ids = []
    #     generated_tokens = [START]
    
    #     for _ in range(max_len):
    #         logits = self.forward(input_ids, attention_mask)
    #         next_logits = logits[0, -1, :] # Shape: (vocab_size)
    
    #         masked_logits = self.apply_grammar_mask(
    #             next_logits,
    #             tokens_so_far=generated_tokens,
    #             schema_tables=schema_tables,
    #             schema_columns=schema_columns,
    #             allowed_token_fn=allowed_token_fn # 🔥 Pass it through
    #         )
    
    #         if torch.all(masked_logits == float("-inf")):
    #             print("❌ Grammar dead-end reached")
    #             break
    
    #         next_id = torch.argmax(masked_logits).item()
    #         next_token = ID2TOKEN[next_id]
    
    #         generated_token_ids.append(next_id)
    #         generated_tokens.append(next_token)
    
    #         if next_id == self.end_id:
    #             break
    
    #         # Update inputs for next step
    #         new_id_tensor = torch.tensor([[next_id]], device=input_ids.device)
    #         input_ids = torch.cat([input_ids, new_id_tensor], dim=1)
            
    #         new_mask_tensor = torch.ones((1, 1), device=input_ids.device)
    #         attention_mask = torch.cat([attention_mask, new_mask_tensor], dim=1)
    
    #     return generated_token_ids
    
    # below is of gemini for phase4 join + where
    @torch.no_grad()
    def generate(self, input_ids, attention_mask, schema_tables, schema_columns, max_len=100, allowed_token_fn=None, intent_signals=None):
        self.eval()
        generated_token_ids = []
        generated_tokens = [START]
    
        for _ in range(max_len):
            logits = self.forward(input_ids, attention_mask)
            next_logits = logits[0, -1, :] 
    
            masked_logits = self.apply_grammar_mask(
                next_logits,
                tokens_so_far=generated_tokens,
                schema_tables=schema_tables,
                schema_columns=schema_columns,
                allowed_token_fn=allowed_token_fn,
                intent_signals=intent_signals # 🔥 Pass intent to mask
            )
    
            if torch.all(masked_logits == float("-inf")): break
            
            next_id = torch.argmax(masked_logits).item()
            generated_token_ids.append(next_id)
            generated_tokens.append(ID2TOKEN[next_id])
    
            if next_id == self.end_id: break
    
            # Standard input update [cite: 52, 53]
            new_id = torch.tensor([[next_id]], device=input_ids.device)
            input_ids = torch.cat([input_ids, new_id], dim=1)
            attention_mask = torch.cat([attention_mask, torch.ones((1, 1), device=input_ids.device)], dim=1)
    
        return generated_token_ids