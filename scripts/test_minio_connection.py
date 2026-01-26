import os
import boto3
import uuid
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
    
    # Buckets to test
    buckets = {
        "Main": os.getenv("AWS_STORAGE_BUCKET_NAME", "pavssv-artifacts"),
        "Inputs": os.getenv("AWS_INPUTS_BUCKET", "pavssv-inputs"),
        "Artifacts": os.getenv("AWS_ARTIFACTS_BUCKET", "pavssv-artifacts"),
        "Exports": os.getenv("AWS_EXPORTS_BUCKET", "pavssv-exports"),
    }
    
    print(f"Endpoint: {endpoint}")
    print(f"Access Key: {mask(access_key)}")
    print(f"Secret Key: {mask(secret_key)}")
    print(f"Buckets to test: {list(buckets.values())}")
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
        print("Successfully connected! Buckets found on server:")
        for bucket in response['Buckets']:
            print(f" - {bucket['Name']}")
            
        print("\n--- Testing Specific Buckets ---")
        for label, bucket_name in buckets.items():
            print(f"\nTurning to bucket: [{label}] -> {bucket_name}")
            try:
                # 1. Head Bucket (Check existence/permission)
                s3.head_bucket(Bucket=bucket_name)
                print(f"[OK] Head Bucket '{bucket_name}' successful.")
                
                # 2. Check NON-EXISTENT Object (Critical for Django get_available_name)
                # Django checks if file exists. If this returns 403 instead of 404, Django crashes.
                missing_key = f"non_existent_{uuid.uuid4()}.txt"
                try:
                    s3.head_object(Bucket=bucket_name, Key=missing_key)
                    print(f"[WARNING] Head Object on missing key '{missing_key}' found an object! (Unexpected)")
                except ClientError as e:
                    code = e.response.get('Error', {}).get('Code')
                    if code == "404":
                        print(f"[OK] Head Object on missing key returned 404 (Correct behavior).")
                    elif code == "403":
                        print(f"[CRITICAL FAILURE] Head Object on missing key returned 403 Forbidden!")
                        print("   -> This causes Django to crash. MinIO config needs s3:ListBucket permission or AWS_S3_FILE_OVERWRITE=True.")
                    else:
                        print(f"[INFO] Head Object on missing key returned {code}: {e}")

                # 3. Put Object (Write Test)
                test_file_key = "test_connection_file.txt"
                s3.put_object(Bucket=bucket_name, Key=test_file_key, Body=b"test content")
                print(f"[OK] Put Object '{test_file_key}' successful.")
                
                # 4. Head Object (Read/Existence Check - verifying the operation that failed in logs)
                s3.head_object(Bucket=bucket_name, Key=test_file_key)
                print(f"[OK] Head Object '{test_file_key}' successful.")
                
                # Cleanup
                s3.delete_object(Bucket=bucket_name, Key=test_file_key)
                print(f"[OK] Delete Object '{test_file_key}' successful.")
                
            except ClientError as e:
                print(f"[FAILED] Error interacting with bucket '{bucket_name}': {e}")
                print(f"  Code: {e.response.get('Error', {}).get('Code')}")
                print(f"  Message: {e.response.get('Error', {}).get('Message')}")
        
    except ClientError as e:
        print(f"\nCONNECTION FAILED: {e}")
        print(f"Error Code: {e.response.get('Error', {}).get('Code')}")
        print(f"Error Message: {e.response.get('Error', {}).get('Message')}")
        
    except Exception as e:
        print(f"\nUNEXPECTED ERROR: {e}")

if __name__ == "__main__":
    test_minio_connection()
