.PHONY: install run test lint simulate clean

install:
	pip install -r requirements.txt

run:
	flask run --host=0.0.0.0 --port=5000

test:
	python -m pytest tests/ -v

lint:
	flake8 --max-line-length=120 --exclude=.venv,__pycache__

simulate:
	python scripts/simulate_traffic.py --count 100

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
