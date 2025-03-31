build:
	flake8 .
	poetry build

test:
	pytest tests/

publish:
	poetry publish

all:
	make test
	make build
	make publish
