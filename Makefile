all: .venv
.venv:
	python3 -m venv .venv
	bash -c "source .venv/bin/activate; pip install numpy==2.1.3"

.PHONY: clean
clean:
	rm -rf .venv