up:
	docker compose up --build

down:
	docker compose down

test:
	docker compose run --rm backend pytest -q

ingest:
	docker compose run --rm backend python -m app.cli ingest

generate-client:
	docker compose run --rm frontend npm run generate:client
