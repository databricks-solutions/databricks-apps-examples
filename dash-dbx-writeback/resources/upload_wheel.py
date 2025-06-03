import io
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()

# Read file into bytes
with open("local_file.csv", "rb") as f:
    file_bytes = f.read()
binary_data = io.BytesIO(file_bytes)

# Specify volume path and upload
volume_path = "main.marketing.raw_files"

parts = volume_path.strip().split(".")

catalog = parts[0]
schema = parts[1]
volume_name = parts[2]

volume_file_path = f"/Volumes/{catalog}/{schema}/{volume_name}/local_file.csv"
w.files.upload(volume_file_path, binary_data, overwrite=True)
