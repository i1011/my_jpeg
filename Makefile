all: .venv
.venv:
	python3 -m venv .venv
	bash -c "source .venv/bin/activate; pip install -r requirements.txt"

.PHONY: clean
clean:
	rm -rf .venv