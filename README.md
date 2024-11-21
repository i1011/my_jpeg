# my_jpeg
## Introduction
This repo contains a simple JPEG baseline decoder.
Currently, the supported markers are:

<details open>

* [x] SOI
* [x] APP0
* [x] COM
* [x] DQT
* [x] SOF0
* [x] DHT
* [x] **Single** SOS
* [x] EOI

</details>

## Environment

- Python: 3.12.3

It is recommended to use [virtualenv](https://docs.python.org/3/library/venv.html) to set up the environment.

``` bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Or simply:
``` bash
make
```

## Execution
``` bash
# activates the environment
source .venv/bin/activate
python3 -m jpeg monalisa.jpg
```
