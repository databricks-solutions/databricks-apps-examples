# Writeback to Databricks with Dash AG-Grid 

Author: [David O'Keeffe](https://www.linkedin.com/in/dgokeeffe/)

This is an example of reading and writing tables to Databricks using Dash AG-Grid, one of the most powerful Javascript libraries for Tabular visualization on the market.

It includes the ability to add validation steps and show warnings for duplicate keys and missing inputs, and disable submitting the table if the validations aren't acceptable. It is a common use case that is asked for by Databricks customers, who essentially want that "Microsoft Excel" like experience for their users to do things in Databricks, like submit a request for a forecast.

It's also one of the most complete examples we have for building sophisticated multi-page apps using the latest libraries in the Python and Databricks ecosystem. This includes tools like `uv`, `pytest` (for TDD and automated unit tests), and [Databricks Asset Bundles](https://docs.databricks.com/aws/en/dev-tools/bundles/).


## Deploying as a Databricks App
1. Install the [Databricks CLI](https://docs.databricks.com/en/dev-tools/cli/index.html) and authenticate with your Databricks workspace using [OAuth U2M](https://docs.databricks.com/en/dev-tools/auth/oauth-u2m.html), for example:

   ```bash
   databricks auth login --host https://my-workspace.cloud.databricks.com/
   ```
2. Unfortunately currently you can not currently pass variables to Apps deployed by Databricks Asset Bundles, so edit the following variables in `app.yml` to the UC Catalog and Schema you want to use for the application to read and write into.

   ```yaml
   env:
      - name: 'DATABRICKS_CATALOG'
         value: 'daveok'
      - name: 'DATABRICKS_SCHEMA'
         value: 'excel_app'
   ```
3. Simply run this to deploy with Databricks Asset Bundles
   ```bash
   databricks bundle deploy && databricks bundle run dash-dbx-writeback 
   ```
4. When you login to the app for the first time, be sure to give it a little bit to initialize the table (got to build a waiting window for it).

## Running Locally

1. Clone this repo to your local machine and switch into the `auth-demo` folder:
   ```bash
   git clone https://github.com/databricks-solutions/databricks-apps-examples.git
   cd databricks-apps-examples/dash-dbx-writeback
   ```
2. Create and activate a Python virtual environment in this folder [`venv`](https://docs.python.org/3/library/venv.html):
   ```bash
   uv venv --python 3.11
   source .venv/bin/activate

   uv pip compile pyproject.toml -o requirements.txt

   uv pip install -r pyproject.toml --all-extras
   ```

3. Set the ENVIRONMENTAL Variables using a .env file and create a catalog in UC

   ```sql
   CREATE CATALOG daveok;
   CREATE SCHEMA daveok.dash_writeback;
   ```

   ```bash
   touch .env 

   DATABRICKS_HOST=https://my-workspace.cloud.databricks.com/
   DATABRICKS_WAREHOUSE_ID=<navigate to sql warehouse in compute pane and find ID in brackets under Name>
   DATABRICKS_TOKEN=<PAT_TOKEN>
   DATABRICKS_CATALOG=<YOUR_CATALOG>
   DATABRICKS_SCHEMA="dash_writeback"
   ```

   ```bash
   export $(grep -v '^#' .env | xargs)      
   ```
3. Run the app:
   ```bash
   uv run python -m src.dash_dbx_writeback

   python -m src/dash_dbx_writeback
   ```

> [!NOTE]
>
> - When running locally, on-behalf-of-user authorization will not work due to the missing `X-Forwarded-Access-Token` header.
> - The service principal authorization section of the app will instead use your user credentials as configured with the CLI.

---

&copy; 2025 Databricks, Inc. All rights reserved. The source in this repository is provided subject to the Databricks License [https://databricks.com/db-license-source]. All included or referenced third party libraries are subject to the licenses set forth below.

| library                  | description                                        | license      | source                                              |
| ------------------------ | -------------------------------------------------- | ------------ | --------------------------------------------------- |
| dash                     | Framework for building analytical web applications | MIT          | https://github.com/plotly/dash                      |
| dash-ag-grid | AG Grid Plugin for Dash apps                      | MIT          | https://github.com/plotly/dash-ag-grid            |
| dash_mantine_components  | Mantine components for Dash                        | MIT          | https://github.com/snehilvj/dash-mantine-components |
| databricks-sdk           | Databricks SDK for Python                          | Apache 2.0   | https://github.com/databricks/databricks-sdk-py     |
| databricks-sql-connector | Databricks SQL Connector for Python                | Apache 2.0   | https://github.com/databricks/databricks-sql-python |
| pandas                   | Data analysis and manipulation library             | BSD 3-Clause | https://github.com/pandas-dev/pandas                |
| pyarrow                  | Python library for Apache Arrow                    | Apache 2.0   | https://github.com/apache/arrow/tree/main/python    |

Databricks support doesn't cover this content. For questions or bugs, please open a github issue and the team will help on a best effort basis.

---

## Questions and issues
Please file an issue on this repository when and if you run into errors with the deployed applications. Thanks!
