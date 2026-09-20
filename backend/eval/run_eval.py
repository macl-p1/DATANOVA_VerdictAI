import boto3, time

s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")

BUCKET = "verdictai-uploadbucket-o5ti3lkgrnk6"
TABLE = "verdictai-CasesTable-90YBQYC7MLRJ"

TEST_CASES = [
    {"file": "test-case-2.txt", "expected_flag": "PAST_MAX"},
    {"file": "test-case-3.txt", "expected_flag": "NOT_ELIGIBLE"},
    {"file": "test-case-5.txt", "expected_flag": "PAST_HALF"},
    {"file": "test-case-6.txt", "expected_flag": "PAST_THIRD"},
    {"file": "test-case-7.txt", "expected_flag": "NEEDS_REVIEW"},
    {"file": "test-case-8.txt", "expected_flag": "NOT_ELIGIBLE"},
]

table = dynamodb.Table(TABLE)
correct = 0
results = []

for case in TEST_CASES:
    case_id = case["file"].replace(".txt", "") + "-eval"
    table.put_item(Item={"caseId": case_id, "status": "UPLOADED"})
    s3.upload_file(case["file"], BUCKET, f"uploads/{case_id}.txt")
    print(f"Uploaded {case['file']} as {case_id}, waiting...")
    time.sleep(15)

    resp = table.get_item(Key={"caseId": case_id})
    item = resp.get("Item", {})
    actual_flag = item.get("flag", "MISSING")
    passed = actual_flag == case["expected_flag"]
    correct += passed
    results.append((case["file"], case["expected_flag"], actual_flag, passed))
    print(f"  expected {case['expected_flag']}, got {actual_flag} — {'PASS' if passed else 'FAIL'}\n")

print("=" * 50)
print(f"RESULT: {correct}/{len(TEST_CASES)} correct ({correct/len(TEST_CASES)*100:.0f}%)")
print("=" * 50)
for file, expected, actual, passed in results:
    status = "✓" if passed else "✗"
    print(f"{status} {file}: expected={expected}, actual={actual}")