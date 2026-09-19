import pytest

torch = pytest.importorskip("torch")

from verdictai.inference.pipeline import predict_text


class Tokenizer:
    is_fast = True

    def __call__(self, *_args, **_kwargs):
        return {
            "input_ids": torch.tensor([[1, 0]]),
            "attention_mask": torch.tensor([[1, 1]]),
            "offset_mapping": torch.tensor([[[0, 4], [0, 0]]]),
            "overflow_to_sample_mapping": torch.tensor([0]),
        }


class Model(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.anchor = torch.nn.Parameter(torch.zeros(1))
        self.config = type("Config", (), {"id2label": {0: "O", 1: "B-CASE_ID"}})()

    # This intentionally accepts only real model tensors.  The test catches
    # accidental forwarding of tokenizer bookkeeping fields.
    def forward(self, input_ids, attention_mask):
        return type("Output", (), {"logits": torch.tensor([[[0.0, 5.0], [5.0, 0.0]]])})()


def test_predict_does_not_forward_overflow_metadata_to_model():
    result = predict_text(Model(), Tokenizer(), "FIR1", "CASE_1")
    assert result.entities[0].type == "CASE_ID"
    assert result.entities[0].evidence.text == "FIR1"
