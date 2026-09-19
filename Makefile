.PHONY: validate ingest split test train evaluate predict

validate:
	python scripts/validate_dataset.py

ingest:
	python scripts/import_annotations.py

split:
	python scripts/split_dataset.py

test:
	python -m pytest

train:
	python scripts/train.py --config configs/training.yaml

evaluate:
	python scripts/evaluate.py

predict:
	python scripts/predict.py --input sample.txt
