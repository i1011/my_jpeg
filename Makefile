all: .venv
.venv:
	python3 -m venv .venv
	bash -c "source .venv/bin/activate; pip install -r requirements.txt"

.PHONY: clean perf
perf:
	time python3 -m jpeg Image/monalisa.jpg
	time python3 -m jpeg Image/gig-sn01.jpg
	time python3 -m jpeg Image/gig-sn08.jpg
	time python3 -m jpeg Image/teatime.jpg
clean:
	rm -rf .venv
