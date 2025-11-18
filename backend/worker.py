# worker.py (Đã cập nhật 2 buckets)
import os
import json
import time
import boto3
from botocore.exceptions import ClientError

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
INPUT_QUEUE_URL = os.getenv("INPUT_QUEUE_URL")
# Xóa S3_BUCKET, vì worker sẽ nhận bucket name từ SQS
RESULT_S3_PREFIX = os.getenv("RESULT_S3_PREFIX", "results/")

if not INPUT_QUEUE_URL:
    raise RuntimeError("Missing required env var: INPUT_QUEUE_URL")

session = boto3.session.Session(region_name=AWS_REGION)
sqs = session.client("sqs")
s3 = session.client("s3")
rekognition = session.client("rekognition")

# (Hàm run_inference_on_bytes không đổi)
def run_inference_on_bytes(img_bytes, filename):
    print(f"Bắt đầu gọi Rekognition cho file: {filename}")
    try:
        response = rekognition.detect_labels(
            Image={'Bytes': img_bytes},
            MaxLabels=10,
            MinConfidence=80.0
        )
        labels = []
        for label in response.get('Labels', []):
            labels.append({
                "name": label.get('Name'),
                "confidence": label.get('Confidence')
            })
        print(f"Rekognition thành công, tìm thấy {len(labels)} nhãn.")
        return {
            "filename": filename,
            "analysis_service": "aws_rekognition",
            "labels": labels
        }
    except ClientError as e:
        print(f"Lỗi khi gọi Rekognition: {e}")
        return {
            "filename": filename,
            "analysis_service": "aws_rekognition",
            "error": str(e)
        }
    except Exception as e:
        print(f"Lỗi không xác định: {e}")
        return {
            "filename": filename,
            "error": f"Unknown error: {str(e)}"
        }

# --- THAY ĐỔI: Sửa hàm process_message ---
def process_message(msg):
    body = json.loads(msg['Body'])
    
    # Đọc tên bucket và key từ message
    uid = body.get('uid')
    s3_bucket_in = body.get('s3_bucket_in')
    s3_key_in = body.get('s3_key_in')
    s3_bucket_out = body.get('s3_bucket_out')
    filename = body.get('filename', 'unknown')

    # Kiểm tra message mới
    if not (uid and s3_bucket_in and s3_key_in and s3_bucket_out):
        print("Malformed message (missing bucket info), skipping:", msg.get('MessageId'))
        return False

    try:
        # Tải ảnh từ BUCKET_IN
        print(f"Đang tải ảnh từ: {s3_bucket_in}/{s3_key_in}")
        obj = s3.get_object(Bucket=s3_bucket_in, Key=s3_key_in)
        img_bytes = obj['Body'].read()
    except ClientError as e:
        print("Failed to download image from S3:", e)
        return False

    # Chạy nhận diện (không đổi)
    result_data = run_inference_on_bytes(img_bytes, filename)
    result_data.update({"uid": uid})

    result_key = f"{RESULT_S3_PREFIX}{uid}.json"
    try:
        # Upload kết quả lên BUCKET_OUT
        print(f"Đang upload kết quả lên: {s3_bucket_out}/{result_key}")
        s3.put_object(Bucket=s3_bucket_out, Key=result_key, Body=json.dumps(result_data, indent=2), ContentType='application/json')
    except ClientError as e:
        print("Failed to put result to S3:", e)
        return False

    return True
# --- KẾT THÚC THAY ĐỔI ---

# (Hàm poll_loop không đổi)
def poll_loop():
    print("Worker started. Polling SQS:", INPUT_QUEUE_URL)
    while True:
        try:
            resp = sqs.receive_message(
                QueueUrl=INPUT_QUEUE_URL,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=20,
                MessageAttributeNames=['All']
            )
            messages = resp.get('Messages', [])
            if not messages:
                continue
            
            for m in messages:
                receipt = m['ReceiptHandle']
                print(f"Đang xử lý message ID: {m['MessageId']}")
                success = process_message(m)
                
                if success:
                    print(f"Xử lý thành công, xóa message: {m['MessageId']}")
                    sqs.delete_message(QueueUrl=INPUT_QUEUE_URL, ReceiptHandle=receipt)
                else:
                    print("Processing failed for message. Leaving it in queue.")
        
        except Exception as e:
            print("Worker exception:", e)
            time.sleep(5)

if __name__ == "__main__":
    poll_loop()