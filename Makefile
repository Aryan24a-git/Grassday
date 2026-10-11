.PHONY: setup demo test backend frontend clean

setup:
	pip install -r requirements.txt
	cd frontend && npm install

backend:
	python -m uvicorn api:app --host 127.0.0.1 --port 8000

demo:
	python demo.py
	python -m uvicorn api:app --host 127.0.0.1 --port 8000

frontend:
	cd frontend && npm run dev

test:
	pytest tests/ -v

clean:
	rm -rf __pycache__
	rm -rf tests/__pycache__
	rm -rf data/*.db
	rm -rf frontend/node_modules
	rm -rf frontend/dist
