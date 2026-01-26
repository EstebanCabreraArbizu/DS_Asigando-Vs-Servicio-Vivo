import os
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
BASE_DIR = Path(__file__).resolve().parent.parent / "server"
load_dotenv(BASE_DIR / ".env")

def test_minio_connection():
    print("--- MinIO Connection Diagnostic ---")
    
    # helper to hide secrets
    def mask(s):
        return f"{s[:4]}...{s[-4:]}" if s and len(s) > 8 else "***"

    endpoint = os.getenv("AWS_S3_ENDPOINT_URL")
    access_key = os.getenv("AWS_ACCESS_KEY_ID")
    secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    bucket_name = os.getenv("AWS_STORAGE_BUCKET_NAME", "pavssv-artifacts")
    region = os.getenv("AWS_S3_REGION_NAME", "us-east-1")
    verify = os.getenv("AWS_S3_VERIFY", "true").lower() == "true"
    
    print(f"Endpoint: {endpoint}")
    print(f"Access Key: {mask(access_key)}")
    print(f"Secret Key: {mask(secret_key)}")
    print(f"Bucket: {bucket_name}")
    print(f"Region: {region}")
    print(f"Verify SSL: {verify}")
    print("-----------------------------------")

    if not endpoint or not access_key or not secret_key:
        print("ERROR: Missing required environment variables.")
        return

    session = boto3.session.Session()
    
    # Configure S3 client
    s3_config = boto3.session.Config(
        signature_version='s3v4',
        s3={'addressing_style': 'path'}
    )

    s3 = session.client(
        's3',
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region,
        config=s3_config,
        verify=verify
    )

    try:
        print(f"Attempting to list buckets at {endpoint}...")
        response = s3.list_buckets()
        print("Successfully connected! Buckets found:")
        for bucket in response['Buckets']:
            print(f" - {bucket['Name']}")
            
        print(f"\nChecking specific bucket access: {bucket_name}")
        # Try to head the bucket to check permissions
        s3.head_bucket(Bucket=bucket_name)
        print(f"Successfully accessed bucket '{bucket_name}'")
        
    except ClientError as e:
        print(f"\nCONNECTION FAILED: {e}")
        print(f"Error Code: {e.response.get('Error', {}).get('Code')}")
        print(f"Error Message: {e.response.get('Error', {}).get('Message')}")
        print(f"HTTP Status Code: {e.response.get('ResponseMetadata', {}).get('HTTPStatusCode')}")
        
    except Exception as e:
        print(f"\nUNEXPECTED ERROR: {e}")

if __name__ == "__main__":
    test_minio_connection()
