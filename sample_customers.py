from pymongo import MongoClient
from datetime import datetime, timedelta
import random
import os
from dotenv import load_dotenv

load_dotenv()

client = MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017/"))
db = client["citizen_portal"]
users_col = db["users"]

# Clear existing sample data
users_col.delete_many({"sample_data": True})

# Sample customer data
sample_customers = []

# Government employees without degrees (target for degree programs)
for i in range(15):
    age = random.randint(35, 45)
    children_count = random.randint(1, 3)
    children_ages = [random.randint(5, 20) for _ in range(children_count)]
    
    customer = {
        "sample_data": True,
        "profile": {
            "basic": {
                "name": f"Government Employee {i+1}",
                "age": age,
                "location": random.choice(["Colombo", "Kandy", "Gampaha", "Kalutara", "Galle"]),
                "phone": f"07{random.randint(10000000, 99999999)}"
            }
        },
        "extended_profile": {
            "family": {
                "marital_status": "married",
                "children": [f"Child {j+1}" for j in range(children_count)],
                "children_ages": children_ages,
                "children_education": [random.choice(["primary", "secondary", "ol", "al", "tuition"]) for _ in range(children_count)],
                "dependents": children_count
            },
            "education": {
                "highest_qualification": random.choice(["ol", "al", "diploma"]),
                "institution": "Local School/College",
                "year_graduated": 2000 + random.randint(0, 10),
                "field_of_study": "General"
            },
            "career": {
                "current_job": f"Government {random.choice(['Clerk', 'Officer', 'Administrator', 'Supervisor'])}",
                "years_experience": age - 22,
                "skills": ["administration", "management", "public_service"],
                "career_goals": ["degree_completion", "promotion", "skill_development"]
            },
            "interests": {
                "hobbies": ["reading", "family_time", "community_service"],
                "learning_interests": ["degree_programs", "professional_courses", "language_courses"],
                "service_preferences": ["education", "career_development", "family_services"]
            },
            "consent": {
                "marketing_emails": True,
                "personalized_ads": True,
                "data_analytics": True
            }
        },
        "created": datetime.utcnow() - timedelta(days=random.randint(1, 365)),
        "last_active": datetime.utcnow() - timedelta(hours=random.randint(1, 72))
    }
    sample_customers.append(customer)

# Young professionals (target for career development)
for i in range(15):
    age = random.randint(25, 35)
    customer = {
        "sample_data": True,
        "profile": {
            "basic": {
                "name": f"Young Professional {i+1}",
                "age": age,
                "location": random.choice(["Colombo", "Kandy", "Negombo", "Moratuwa"]),
                "phone": f"07{random.randint(10000000, 99999999)}"
            }
        },
        "extended_profile": {
            "family": {
                "marital_status": random.choice(["single", "married"]),
                "children": [] if random.random() > 0.3 else ["Child 1"],
                "children_ages": [] if random.random() > 0.3 else [random.randint(1, 5)],
                "dependents": 0
            },
            "education": {
                "highest_qualification": random.choice(["degree", "diploma", "al"]),
                "institution": random.choice(["Local University", "Private Institute", "Government School"]),
                "year_graduated": 2015 + random.randint(0, 8),
                "field_of_study": random.choice(["IT", "Business", "Engineering", "Arts"])
            },
            "career": {
                "current_job": f"{random.choice(['IT', 'Marketing', 'Sales', 'Finance'])} {random.choice(['Executive', 'Officer', 'Associate'])}",
                "years_experience": age - 22,
                "skills": ["communication", "technical_skills", "teamwork"],
                "career_goals": ["overseas_opportunities", "higher_education", "skill_development"]
            },
            "interests": {
                "hobbies": ["technology", "travel", "learning", "socializing"],
                "learning_interests": ["ielts", "overseas_jobs", "professional_certifications"],
                "service_preferences": ["career_services", "education", "travel"]
            },
            "consent": {
                "marketing_emails": True,
                "personalized_ads": True,
                "data_analytics": True
            }
        },
        "created": datetime.utcnow() - timedelta(days=random.randint(1, 365)),
        "last_active": datetime.utcnow() - timedelta(hours=random.randint(1, 72))
    }
    sample_customers.append(customer)

# Parents with school-going children (target for education services)
for i in range(20):
    age = random.randint(40, 55)
    children_count = random.randint(1, 4)
    children_ages = [random.randint(5, 18) for _ in range(children_count)]
    
    customer = {
        "sample_data": True,
        "profile": {
            "basic": {
                "name": f"Parent {i+1}",
                "age": age,
                "location": random.choice(["Colombo", "Kandy", "Kurunegala", "Ratnapura", "Badulla"]),
                "phone": f"07{random.randint(10000000, 99999999)}"
            }
        },
        "extended_profile": {
            "family": {
                "marital_status": "married",
                "children": [f"Child {j+1}" for j in range(children_count)],
                "children_ages": children_ages,
                "children_education": [random.choice(["primary", "secondary", "ol_prep", "al_prep", "tuition"]) for _ in range(children_count)],
                "dependents": children_count
            },
            "education": {
                "highest_qualification": random.choice(["ol", "al", "degree", "diploma"]),
                "institution": "Various",
                "year_graduated": 1990 + random.randint(0, 15),
                "field_of_study": "General"
            },
            "career": {
                "current_job": random.choice(["Business Owner", "Teacher", "Government Officer", "Private Employee", "Professional"]),
                "years_experience": age - 25,
                "skills": ["management", "communication", "problem_solving"],
                "career_goals": ["children_education", "financial_security", "retirement_planning"]
            },
            "interests": {
                "hobbies": ["family_activities", "community_events", "reading"],
                "learning_interests": ["children_education", "exam_preparation", "extracurricular"],
                "service_preferences": ["education_services", "family_products", "financial_services"]
            },
            "consent": {
                "marketing_emails": True,
                "personalized_ads": True,
                "data_analytics": True
            }
        },
        "created": datetime.utcnow() - timedelta(days=random.randint(1, 365)),
        "last_active": datetime.utcnow() - timedelta(hours=random.randint(1, 72))
    }
    sample_customers.append(customer)

# Insert all sample customers
if sample_customers:
    users_col.insert_many(sample_customers)
    print(f"Inserted {len(sample_customers)} sample customers")
    print(f"Total users in database: {users_col.count_documents({})}")
