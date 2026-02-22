import requests
import csv
from datetime import datetime
import os

url = "https://www.hut-reservation.org/api/v1/reservation/getHutAvailability?hutId=675&step=WIZARD"

headers = {
    "User-Agent": "Mozilla/5.0"
}

response = requests.get(url, headers=headers)
data = response.json()

today = datetime.today().strftime("%d-%m-%Y")
file_exists = os.path.isfile("historie.csv")

with open("historie.csv", "a", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)

    # Header nur schreiben, wenn Datei neu
    if not file_exists:
        writer.writerow(["Abrufdatum", "Buchungsdatum", "FreiePlaetze", "Kapazität", "Status"])

    for day in data:
        writer.writerow([
            today,
            day["dateFormatted"],
            day["freeBeds"],      # freie Plätze aktuell
            day.get("totalSleepingPlaces", day["freeBeds"]),  # Kapazität für diesen Tag
            day.get("hutStatus", "SERVICED")         # Status, falls vorhanden
        ])
