import csv
import os
from datetime import datetime

import requests

API_URL = "https://www.hut-reservation.org/api/v1/reservation/getHutAvailability"
HEADERS = {"User-Agent": "Mozilla/5.0"}
CSV_FILE = "historie.csv"
CSV_FIELDS = ["Abrufdatum", "Huette", "Buchungsdatum", "FreiePlaetze", "Kapazität", "Status"]

HUTS = [
    {"name": "Franz Senn Hütte", "id": 675},
    {"name": "Regensburger Hütte", "id": 275},
    {"name": "Starkenburger Hütte", "id": 693},
]


def ensure_csv_schema() -> None:
    """Migriert bestehende CSV-Dateien ohne 'Huette'-Spalte auf das neue Schema."""
    if not os.path.isfile(CSV_FILE):
        return

    with open(CSV_FILE, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        existing_fields = reader.fieldnames or []
        if "Huette" in existing_fields:
            return
        rows = list(reader)

    migrated_rows = []
    for row in rows:
        migrated_rows.append(
            {
                "Abrufdatum": row.get("Abrufdatum"),
                "Huette": "Franz Senn Hütte",
                "Buchungsdatum": row.get("Buchungsdatum"),
                "FreiePlaetze": row.get("FreiePlaetze"),
                "Kapazität": row.get("Kapazität"),
                "Status": row.get("Status"),
            }
        )

    with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(migrated_rows)


def fetch_availability(hut_id: int):
    response = requests.get(API_URL, params={"hutId": hut_id, "step": "WIZARD"}, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return response.json()


def main() -> None:
    ensure_csv_schema()

    today = datetime.today().strftime("%d-%m-%Y")
    file_exists = os.path.isfile(CSV_FILE)

    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)

        if not file_exists:
            writer.writeheader()

        for hut in HUTS:
            try:
                data = fetch_availability(hut["id"])
            except requests.RequestException as exc:
                print(f"Fehler bei {hut['name']} ({hut['id']}): {exc}")
                continue

            for day in data:
                writer.writerow(
                    {
                        "Abrufdatum": today,
                        "Huette": hut["name"],
                        "Buchungsdatum": day["dateFormatted"],
                        "FreiePlaetze": day["freeBeds"],
                        "Kapazität": day.get("totalSleepingPlaces", day["freeBeds"]),
                        "Status": day.get("hutStatus", "SERVICED"),
                    }
                )


if __name__ == "__main__":
    main()
