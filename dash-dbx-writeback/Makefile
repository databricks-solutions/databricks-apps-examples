build-app:
	rm -rf ./.build
	uv build --package dash_dbx_writeback --wheel -o ./.build
	cd .build && ls *.whl > requirements.txt

deploy: build-app
	databricks -p $(profile) \
		bundle deploy \
			--var="databricks_catalog=$(catalog)"
			--var="databricks_schema=$(schema)"
# make sure you're running the app after the RAG pipeline
run-app:
	databricks -p $(profile) \
		bundle run dash_dbx_writeback\
			--var="databricks_catalog=$(catalog)"
			--var="databricks_schema=$(schema)"

all-app: deploy run-app