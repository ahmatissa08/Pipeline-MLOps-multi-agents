import os
import boto3
from botocore.config import Config
from sklearn.datasets import fetch_openml

df = fetch_openml(data_id=1590, as_frame=True).frame
print("Dimensions :", df.shape)

os.makedirs("data", exist_ok=True)
local_path = "data/adult_v1.csv"
df.to_csv(local_path, index=False)

s3 = boto3.client(
    "s3",
    endpoint_url="http://localhost:9000",
    aws_access_key_id="minioadmin",
    aws_secret_access_key="minioadmin",
    region_name="us-east-1",
    config=Config(
        signature_version="s3v4",
        s3={"addressing_style": "path"},
        request_checksum_calculation="when_required",
        response_checksum_validation="when_required",
        retries={"max_attempts": 5},
    ),
)

s3.upload_file(local_path, "raw-data", "adult/adult_v1.csv")
print("Fichier déposé dans raw-data/adult/adult_v1.csv")