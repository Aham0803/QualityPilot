"""
Synthetic Master Data Generator with Realistic Defects & Ground Truth.
Generates 50,000+ records across 3 sources (CRM_Salesforce, ERP_SAP, Web_Portal).
Injects realistic MDM defects (duplicates, format errors, typos, missing values, conflicts).
Maintains hidden 'true_entity_id' for precision/recall evaluation.
"""

import os
import random
import csv
import json
from datetime import datetime, timedelta, timezone

try:
    from faker import Faker
    fake = Faker()
    HAS_FAKER = True
except ImportError:
    HAS_FAKER = False

# Seed for reproducibility
random.seed(42)

# Fallback names & cities if faker is not ready
FIRST_NAMES = [
    "Rahul", "Priya", "Amit", "Sneha", "Vikram", "Ananya", "Rohan", "Pooja",
    "John", "Sarah", "Michael", "Emily", "David", "Jessica", "James", "Emma",
    "Daniel", "Sophia", "Matthew", "Olivia", "Alexander", "Isabella", "Andrew",
    "Arjun", "Kavita", "Siddharth", "Neha", "Rajesh", "Sunita", "Deepak"
]

LAST_NAMES = [
    "Sharma", "Verma", "Patel", "Gupta", "Singh", "Kumar", "Iyer", "Nair",
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Miller", "Davis",
    "Wilson", "Taylor", "Anderson", "Thomas", "Jackson", "White", "Harris",
    "Deshmukh", "Choudhury", "Bhattacharya", "Reddy", "Mehta", "Joshi"
]

INDIAN_CITIES = [
    ("Indore", "Madhya Pradesh", "452001", "IN"),
    ("Bhopal", "Madhya Pradesh", "462001", "IN"),
    ("Mumbai", "Maharashtra", "400001", "IN"),
    ("Pune", "Maharashtra", "411001", "IN"),
    ("Bengaluru", "Karnataka", "560001", "IN"),
    ("Hyderabad", "Telangana", "500001", "IN"),
    ("Delhi", "Delhi", "110001", "IN"),
    ("Chennai", "Tamil Nadu", "600001", "IN"),
    ("Kolkata", "West Bengal", "700001", "IN"),
    ("Ahmedabad", "Gujarat", "380001", "IN"),
    ("Jaipur", "Rajasthan", "302001", "IN"),
    ("Lucknow", "Uttar Pradesh", "226001", "IN")
]

US_CITIES = [
    ("New York", "New York", "10001", "US"),
    ("Los Angeles", "California", "90001", "US"),
    ("Chicago", "Illinois", "60601", "US"),
    ("Houston", "Texas", "77001", "US"),
    ("Phoenix", "Arizona", "85001", "US"),
    ("Seattle", "Washington", "98101", "US"),
    ("San Francisco", "California", "94102", "US"),
    ("Boston", "Massachusetts", "02108", "US")
]

CITY_TYPOS = {
    "Indore": ["Indor", "indore mp", "INDORE (M.P.)", "Indorre", "Indor MP"],
    "Bhopal": ["Bhopall", "bhopal mp", "BHOPAL", "Bhopal (M.P.)"],
    "Mumbai": ["Bombay", "Mumbaai", "MUMBAI MH", "mumbai"],
    "Pune": ["Poona", "Punne", "PUNE MH"],
    "Bengaluru": ["Bangalore", "BLR", "Banglore", "bengaluru kar"],
    "Hyderabad": ["Hyd", "Hyderabaad", "HYDERABAD TS"],
    "New York": ["NYC", "new york ny", "N.Y.C.", "New York City"],
    "Los Angeles": ["LA", "L.A.", "los angeles ca"],
    "San Francisco": ["SF", "San Fran", "san francisco ca"]
}

STREET_NAMES = [
    "MG Road", "Park Street", "Ring Road", "Link Road", "Station Road",
    "Main Street", "Broadway", "Oak Avenue", "Maple Drive", "Sunset Blvd"
]

def generate_base_entity(entity_idx: int) -> dict:
    """Generate a clean canonical ground-truth entity."""
    if HAS_FAKER:
        first = fake.first_name()
        last = fake.last_name()
    else:
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
    
    full_name = f"{first} {last}"
    email = f"{first.lower()}.{last.lower()}{random.randint(1, 999)}@example.com"
    
    # 70% Indian demographics, 30% US/Global
    if random.random() < 0.7:
        city_info = random.choice(INDIAN_CITIES)
        phone = f"+91{random.choice(['98', '97', '99', '94', '91'])}{random.randint(10000000, 99999999)}"
    else:
        city_info = random.choice(US_CITIES)
        phone = f"+1{random.randint(201, 989)}{random.randint(1000000, 9999999)}"

    city, state, postal, country = city_info
    street = f"{random.randint(10, 999)}, {random.choice(STREET_NAMES)}"
    age = random.randint(20, 75)
    
    # Calculate birth date consistent with age
    today = datetime.now(timezone.utc)
    birth_year = today.year - age
    birth_date = datetime(birth_year, random.randint(1, 12), random.randint(1, 28)).strftime("%Y-%m-%d")
    
    created_dt = today - timedelta(days=random.randint(30, 800))
    updated_dt = created_dt + timedelta(days=random.randint(0, 20))

    return {
        "true_entity_id": f"ENT-{entity_idx:06d}",
        "full_name": full_name,
        "first_name": first,
        "last_name": last,
        "email": email,
        "phone": phone,
        "address": street,
        "city": city,
        "state": state,
        "postal_code": postal,
        "country_code": country,
        "age": age,
        "birth_date": birth_date,
        "created_at": created_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "updated_at": updated_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "job_title": random.choice([
            "Software Engineer", "Sales Manager", "Financial Analyst",
            "Operations Lead", "Marketing Specialist", "Director of Product",
            "VP Engineering", "Staff Physician", "Executive Assistant", "Customer Support"
        ])
    }

def inject_defects(record: dict, source: str) -> dict:
    """Inject realistic dirty master-data defects into a record."""
    r = dict(record)
    r["source"] = source
    r["source_record_id"] = f"{source[:3].upper()}-{random.randint(1000000, 9999999)}"

    # 1. Typos in City
    if random.random() < 0.25 and r["city"] in CITY_TYPOS:
        r["city"] = random.choice(CITY_TYPOS[r["city"]])

    # 2. Typos in Full Name (abbreviations, Jr., drop char)
    if random.random() < 0.15:
        first, last = r["first_name"], r["last_name"]
        t = random.choice(["initial", "jr", "swap", "typo"])
        if t == "initial":
            r["full_name"] = f"{first[0]}. {last}"
        elif t == "jr":
            r["full_name"] = f"{first} {last} Jr."
        elif t == "swap":
            r["full_name"] = f"{last}, {first}"
        elif t == "typo" and len(first) > 3:
            r["full_name"] = f"{first[:-1]} {last}"

    # 3. Missing values (5-10% for email, phone, city, age)
    if random.random() < 0.08:
        r["email"] = None
    if random.random() < 0.07:
        r["phone"] = None
    if random.random() < 0.05:
        r["city"] = None
    if random.random() < 0.06:
        r["age"] = None

    # 4. Format errors (Date formats, phone patterns, mixed casing)
    if random.random() < 0.20 and r["email"]:
        # mixed casing or whitespace
        r["email"] = r["email"].upper() if random.random() < 0.5 else f"  {r['email']} "

    if random.random() < 0.18 and r["birth_date"]:
        # Change YYYY-MM-DD to MM/DD/YYYY or DD-MM-YYYY
        try:
            dt = datetime.strptime(r["birth_date"], "%Y-%m-%d")
            r["birth_date"] = dt.strftime("%m/%d/%Y") if random.random() < 0.5 else dt.strftime("%d-%m-%Y")
        except Exception:
            pass

    if random.random() < 0.20 and r["phone"]:
        raw_phone = r["phone"].replace("+91", "").replace("+1", "")
        if random.random() < 0.5:
            r["phone"] = f"({raw_phone[:3]}) {raw_phone[3:6]}-{raw_phone[6:]}"
        else:
            r["phone"] = f"{raw_phone[:5]} {raw_phone[5:]}"

    # 5. Invalid values (bad emails, impossible ages, wrong pincodes)
    if random.random() < 0.03:
        r["email"] = "abc@@invalid.domain..com" if random.random() < 0.5 else "missing_at_symbol.com"

    if random.random() < 0.02:
        r["age"] = random.choice([240, -5, 0, 999])

    if random.random() < 0.02:
        r["postal_code"] = "999999999"  # invalid length

    # 6. Conflicting values across sources (e.g., address changed)
    if source == "Web_Portal" and random.random() < 0.12:
        r["city"] = "Pune" if r["city"] != "Pune" else "Mumbai"
        r["address"] = f"{random.randint(1, 50)}, Secondary Branch Road"

    # 7. Date order defect: updated_at earlier than created_at
    if random.random() < 0.02:
        r["updated_at"] = (datetime.strptime(r["created_at"], "%Y-%m-%d %H:%M:%S") - timedelta(days=10)).strftime("%Y-%m-%d %H:%M:%S")

    return r

def generate_dataset(total_records: int = 50000, output_dir: str = "data/raw"):
    """
    Generate 50,000+ total records with duplicates and defects.
    Outputs:
      - CRM_Salesforce_extract.csv (~22,500 rows)
      - ERP_SAP_extract.csv (~20,000 rows)
      - Web_Portal_extract.json (~7,500 rows API payload)
      - ground_truth_clusters.json (True entity clusters for precision/recall validation)
    """
    os.makedirs(output_dir, exist_ok=True)
    print(f"[*] Starting synthetic data generation for {total_records} records...")

    # We need ~45,000 distinct true entities, and ~5,000-7,000 duplicates across sources (10-14% duplication)
    distinct_count = int(total_records * 0.88)
    duplicate_count = total_records - distinct_count

    print(f"[*] Generating {distinct_count} unique base entities...")
    base_entities = [generate_base_entity(i + 1) for i in range(distinct_count)]

    # Select candidates for duplicate pairs/triplets across sources
    duplicate_bases = random.sample(base_entities, duplicate_count)

    sources = ["CRM_Salesforce", "ERP_SAP", "Web_Portal"]
    source_allocations = {
        "CRM_Salesforce": [],
        "ERP_SAP": [],
        "Web_Portal": []
    }

    # Distribute base entities across sources (approx 45% Salesforce, 40% SAP, 15% Web Portal)
    for idx, entity in enumerate(base_entities):
        roll = random.random()
        if roll < 0.45:
            src = "CRM_Salesforce"
        elif roll < 0.85:
            src = "ERP_SAP"
        else:
            src = "Web_Portal"
        source_allocations[src].append(inject_defects(entity, src))

    # Inject duplicate instances into OTHER sources for cross-source matching
    for entity in duplicate_bases:
        # Choose a target source different from where it originated if possible
        target_src = random.choice(sources)
        source_allocations[target_src].append(inject_defects(entity, target_src))

    # Print summary counts
    crm_records = source_allocations["CRM_Salesforce"]
    erp_records = source_allocations["ERP_SAP"]
    web_records = source_allocations["Web_Portal"]

    print(f"[*] CRM_Salesforce count: {len(crm_records)}")
    print(f"[*] ERP_SAP count:         {len(erp_records)}")
    print(f"[*] Web_Portal count:      {len(web_records)}")
    total_generated = len(crm_records) + len(erp_records) + len(web_records)
    print(f"[*] Total records generated: {total_generated}")

    # Field headers
    fields = [
        "source_record_id", "source", "true_entity_id", "full_name",
        "first_name", "last_name",
        "email", "phone", "address", "city", "state", "postal_code",
        "country_code", "age", "birth_date", "created_at", "updated_at", "job_title"
    ]

    # Write CRM CSV
    crm_path = os.path.join(output_dir, "CRM_Salesforce_extract.csv")
    with open(crm_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(crm_records)
    print(f"[+] Wrote {crm_path}")

    # Write ERP CSV
    erp_path = os.path.join(output_dir, "ERP_SAP_extract.csv")
    with open(erp_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(erp_records)
    print(f"[+] Wrote {erp_path}")

    # Write Web Portal JSON (simulating REST API extract)
    web_path = os.path.join(output_dir, "Web_Portal_extract.json")
    with open(web_path, mode="w", encoding="utf-8") as f:
        json.dump(web_records, f, indent=2)
    print(f"[+] Wrote {web_path}")

    # Write Ground Truth Mapping for Precision/Recall measurement
    # Maps true_entity_id -> list of source_record_ids
    ground_truth = {}
    for r in crm_records + erp_records + web_records:
        tid = r["true_entity_id"]
        s_id = r["source_record_id"]
        if tid not in ground_truth:
            ground_truth[tid] = []
        ground_truth[tid].append(s_id)

    gt_path = os.path.join(output_dir, "ground_truth_clusters.json")
    with open(gt_path, mode="w", encoding="utf-8") as f:
        json.dump(ground_truth, f, indent=2)
    print(f"[+] Wrote ground truth with {len(ground_truth)} unique clusters to {gt_path}")

    return {
        "crm_path": crm_path,
        "erp_path": erp_path,
        "web_path": web_path,
        "ground_truth_path": gt_path,
        "total_records": total_generated
    }

if __name__ == "__main__":
    generate_dataset(50000)
