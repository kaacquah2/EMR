"""
Reference data for Ghana hospitals and common hospital departments.
Used for seeding and for API/UI dropdowns.
"""

# Ghana regions (16 as of current administrative structure)
GHANA_REGIONS = [
    "Greater Accra",
    "Ashanti",
    "Western",
    "Western North",
    "Central",
    "Eastern",
    "Volta",
    "Oti",
    "Northern",
    "Savannah",
    "North East",
    "Upper East",
    "Upper West",
    "Bono",
    "Bono East",
    "Ahafo",
]

# Sample Ghana hospitals: name, region, nhis_code (unique), optional address
GHANA_HOSPITALS = [
    {"name": "Korle Bu Teaching Hospital", "region": "Greater Accra", "nhis_code": "GAC-001", "address": "Accra"},
    {"name": "Ridge Regional Hospital", "region": "Greater Accra", "nhis_code": "GAC-002", "address": "Accra"},
    {"name": "37 Military Hospital", "region": "Greater Accra", "nhis_code": "GAC-003", "address": "Accra"},
    {"name": "Tema General Hospital", "region": "Greater Accra", "nhis_code": "GAC-004", "address": "Tema"},
    {"name": "Princess Marie Louise Hospital", "region": "Greater Accra", "nhis_code": "GAC-005", "address": "Accra"},
    {"name": "Komfo Anokye Teaching Hospital", "region": "Ashanti", "nhis_code": "ASH-001", "address": "Kumasi"},
    {"name": "Manhyia District Hospital", "region": "Ashanti", "nhis_code": "ASH-002", "address": "Kumasi"},
    {"name": "Effia Nkwanta Regional Hospital", "region": "Western", "nhis_code": "WES-001", "address": "Sekondi-Takoradi"},
    {"name": "Tamale Teaching Hospital", "region": "Northern", "nhis_code": "NOR-001", "address": "Tamale"},
    {"name": "Ho Teaching Hospital", "region": "Volta", "nhis_code": "VOL-001", "address": "Ho"},
    {"name": "Cape Coast Teaching Hospital", "region": "Central", "nhis_code": "CEN-001", "address": "Cape Coast"},
    {"name": "Sunyani Regional Hospital", "region": "Bono", "nhis_code": "BON-001", "address": "Sunyani"},
    {"name": "Bolgatanga Regional Hospital", "region": "Upper East", "nhis_code": "UE-001", "address": "Bolgatanga"},
    {"name": "Wa Regional Hospital", "region": "Upper West", "nhis_code": "UW-001", "address": "Wa"},
    {"name": "Koforidua Regional Hospital", "region": "Eastern", "nhis_code": "EAS-001", "address": "Koforidua"},
]

# Common hospital departments (Ghana / general)
GHANA_DEPARTMENTS = [
    "General Medicine",
    "Surgery",
    "Paediatrics",
    "Obstetrics & Gynaecology",
    "Emergency & Casualty",
    "Laboratory",
    "Pharmacy",
    "Radiology",
    "Anaesthesia",
    "Out-Patient Department (OPD)",
    "In-Patient Department (IPD)",
    "Maternity",
    "Mental Health",
    "Dental",
    "Eye (Ophthalmology)",
    "ENT",
    "Physiotherapy",
    "Nutrition",
    "Health Information / Records",
    "Other",
]
