# Deployment

Package the Transformers `safetensors` checkpoint with its tokenizer, label map, and model metadata using `scripts/export_model.py`. Deploy the extraction API independently from rules. The caller must validate `ExtractionResult` and invoke deterministic rules separately; do not place a rule flag in the model response.
