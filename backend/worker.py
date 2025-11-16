# worker.py
import os
import json
import time
import boto3
from botocore.exceptions import ClientError

# --- 1. LẤY BIẾN MÔI TRƯỜNG ---
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
INPUT_QUEUE_URL = os.getenv("INPUT_QUEUE_URL")
S3_BUCKET = os.getenv("S3_BUCKET")
RESULT_S3_PREFIX = os.getenv("RESULT_S3_PREFIX", "results/")

# --- 2. KIỂM TRA BIẾN MÔI TRƯỜNG ---
# (Nếu các biến này bị thiếu, script sẽ dừng ở đây)
if not INPUT_QUEUE_URL or not S3_BUCKET:
    raise RuntimeError("Missing required env vars: INPUT_QUEUE_URL and S3_BUCKET")

# --- 3. KHỞI TẠO CLIENTS ---
session = boto3.session.Session(region_name=AWS_REGION)
sqs = session.client("sqs")
s3 = session.client("s3")
rekognition = session.client("rekognition")


# --- 4. HÀM NHẬN DIỆN ---
def run_inference_on_bytes(img_bytes, filename):
    """
    Hàm này gọi API Amazon Rekognition để nhận diện nhãn (labels)
    từ nội dung bytes của ảnh.
    """
    print(f"Bắt đầu gọi Rekognition cho file: {filename}")
    try:
        response = rekognition.detect_labels(
            Image={
                'Bytes': img_bytes  # Truyền trực tiếp nội dung bytes của ảnh
            },
            MaxLabels=10,
            MinConfidence=80.0 # Chỉ lấy các nhãn có độ tin cậy > 80%
        )
        
        # Xử lý kết quả trả về từ Rekognition
        labels = []
        for label in response.get('Labels', []):
            labels.append({
                "name": label.get('Name'),
                "confidence": label.get('Confidence')
            })

        print(f"Rekognition thành công, tìm thấy {len(labels)} nhãn.")
        
        # Trả về kết quả theo dạng dict
        return {
            "filename": filename,
            "analysis_service": "aws_rekognition",
            "labels": labels
        }

    except ClientError as e:
        print(f"Lỗi khi gọi Rekognition: {e}")
        # Nếu lỗi, trả về một dict thông báo lỗi
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

# --- 5. HÀM XỬ LÝ MESSAGE ---
def process_message(msg):
    body = json.loads(msg['Body'])
    uid = body.get('uid')
    s3_bucket = body.get('s3_bucket')
    s3_key = body.get('s3_key')
    filename = body.get('filename', 'unknown')

    if not (uid and s3_bucket and s3_key):
        print("Malformed message, skipping:", msg.get('MessageId'))
        return False

    try:
        obj = s3.get_object(Bucket=s3_bucket, Key=s3_key)
        img_bytes = obj['Body'].read()
    except ClientError as e:
        print("Failed to download image from S3:", e)
        return False

    # Chạy nhận diện
    result_data = run_inference_on_bytes(img_bytes, filename)
    result_data.update({"uid": uid})

    result_key = f"{RESULT_S3_PREFIX}{uid}.json"
    try:
        s3.put_object(Bucket=S3_BUCKET, Key=result_key, Body=json.dumps(result_data, indent=2), ContentType='application/json')
    except ClientError as e:
        print("Failed to put result to S3:", e)
        return False

    return True

# --- 6. VÒNG LẶP CHÍNH ---
def poll_loop():
    # DÒNG NÀY SẼ ĐƯỢC IN RA NẾU KHÔNG CÓ LỖI GÌ
    print("Worker started. Polling SQS:", INPUT_QUEUE_URL)
    while True:
        try:
            resp = sqs.receive_message(
                QueueUrl=INPUT_QUEUE_URL,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=20,  # long polling
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

# --- 7. ĐIỂM BẮT ĐẦU CHẠY ---
if __name__ == "__main__":
    poll_loop()