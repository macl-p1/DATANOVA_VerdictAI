import boto3, csv, sys
from decimal import Decimal

dynamodb = boto3.resource("dynamodb", region_name="us-east-1")

def parse_bool(value: str) -> bool:
    return value.strip().lower() == "true"

def seed(csv_path, table_name):
    table = dynamodb.Table(table_name)
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        count = 0
        for row in reader:
            table.put_item(Item={
                "code": row["code"],
                "ipcEquivalent": row.get("ipcEquivalent", ""),
                "title": row.get("title", ""),
                "maxYears": Decimal(row["maxYears"]),
                "lifeOrDeath": parse_bool(row["lifeOrDeath"]),
                "sourceUrl": row.get("sourceUrl", ""),
                "verifiedBy": row.get("verifiedBy", ""),
                "deathPossible": parse_bool(row.get("deathPossible", "false")),
                "lifePossible": parse_bool(row.get("lifePossible", "false")),
                "gradedOffence": parse_bool(row.get("gradedOffence", "false")),
                "punishmentText": row.get("punishmentText", ""),
                "confidence": row.get("confidence", ""),
            })
            count += 1
        print(f"Seeded {count} statutes into {table_name}")

if __name__ == "__main__":
    csv_path = sys.argv[1] if len(sys.argv) > 1 else "data/statutes.csv"
    table_name = sys.argv[2] if len(sys.argv) > 2 else "verdictai-StatutesTable-XXXX"
    seed(csv_path, table_name)