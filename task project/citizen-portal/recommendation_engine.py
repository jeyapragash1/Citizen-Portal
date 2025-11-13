from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

class RecommendationEngine:
    def __init__(self, db=None):
        # Accept an existing db instance (preferred) or create a new connection
        if db is not None:
            self.db = db
        else:
            uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
            client = MongoClient(uri)
            self.db = client[os.getenv("MONGO_DB", "citizen_portal")]
        self.users_col = self.db["users"]
        self.eng_col = self.db["engagements"]
        self.ads_col = self.db["ads"]

    def get_user_segment(self, user_id):
        """Segment users based on demographics and behavior. Returns list of segment tags."""
        try:
            user_obj = ObjectId(user_id)
        except Exception:
            user = self.users_col.find_one({"_id": user_id})
        else:
            user = self.users_col.find_one({"_id": user_obj})

        if not user:
            return ["unknown"]

        profile = user.get('extended_profile', {})
        # Try to find age in common places
        age = None
        age = profile.get('family', {}).get('age') or user.get('profile', {}).get('basic', {}).get('age')
        try:
            age = int(age) if age is not None else None
        except Exception:
            age = None

        education = profile.get('education', {}).get('highest_qualification', 'unknown')
        children = profile.get('family', {}).get('children', []) or []
        job = profile.get('career', {}).get('current_job', 'unknown') or 'unknown'

        segment = []

        # Age-based segments
        if age:
            if age < 25:
                segment.append("young_adult")
            elif 25 <= age <= 35:
                segment.append("early_career")
            elif 36 <= age <= 45:
                segment.append("mid_career_family")
            elif 46 <= age <= 60:
                segment.append("established_professional")
            else:
                segment.append("senior")

        # Education-based segments
        if education in ['none', 'school', 'ol']:
            segment.append("needs_qualification")
        elif education in ['al', 'diploma']:
            segment.append("mid_education")
        elif education in ['degree', 'masters', 'phd']:
            segment.append("highly_educated")

        # Family-based segments
        if children:
            segment.append("parent")
            children_ages = profile.get('family', {}).get('children_ages', [])
            for a in children_ages:
                try:
                    ai = int(a)
                    if 5 <= ai <= 10:
                        segment.append("primary_school_parent")
                    if 11 <= ai <= 16:
                        segment.append("secondary_school_parent")
                    if 17 <= ai <= 20:
                        segment.append("university_age_parent")
                except Exception:
                    continue

        # Career-based segments
        try:
            job_lower = job.lower()
            if 'government' in job_lower:
                segment.append("government_employee")
            if any(word in job_lower for word in ['manager', 'director', 'head']):
                segment.append("management")
        except Exception:
            pass

        return list(set(segment))

    def get_personalized_ads(self, user_id, limit=5):
        segments = self.get_user_segment(user_id)
        user_engagements = list(self.eng_col.find({"user_id": user_id}))

        interests = []
        for eng in user_engagements:
            interests.extend(eng.get('desires', []) or [])
            if eng.get('question_clicked'):
                interests.append(eng['question_clicked'])
            if eng.get('service'):
                interests.append(eng['service'])

        ads = list(self.ads_col.find({"active": True}))
        scored_ads = []

        for ad in ads:
            score = 0
            ad_tags = ad.get('tags', []) or []
            ad_segments = ad.get('target_segments', []) or []

            segment_match = len(set(segments) & set(ad_segments))
            score += segment_match * 10

            interest_match = len(set(interests) & set(ad_tags))
            score += interest_match * 5

            if ad.get('created'):
                try:
                    days_old = (datetime.utcnow() - ad['created']).days
                    if days_old < 7:
                        score += 5
                    elif days_old < 30:
                        score += 2
                except Exception:
                    pass

            scored_ads.append((ad, score))

        scored_ads.sort(key=lambda x: x[1], reverse=True)
        return [ad for ad, score in scored_ads[:limit]]

    def generate_education_recommendations(self, user_id):
        try:
            user_obj = ObjectId(user_id)
        except Exception:
            user = self.users_col.find_one({"_id": user_id})
        else:
            user = self.users_col.find_one({"_id": user_obj})

        if not user:
            return []

        profile = user.get('extended_profile', {})
        education = profile.get('education', {})
        career = profile.get('career', {})
        age = profile.get('family', {}).get('age')
        try:
            age = int(age) if age is not None else None
        except Exception:
            age = None

        recommendations = []

        if (education.get('highest_qualification') in ['ol', 'al', 'diploma'] and
            'government' in career.get('current_job', '').lower() and
            age and 25 <= age <= 50):
            recommendations.append({
                "type": "education",
                "title": "Complete Your Degree",
                "message": "Enhance your career with a recognized degree program",
                "priority": "high",
                "tags": ["degree", "government", "career_advancement"]
            })

        children_ages = profile.get('family', {}).get('children_ages', [])
        children_education = profile.get('family', {}).get('children_education', [])

        for i, a in enumerate(children_ages):
            try:
                ai = int(a)
            except Exception:
                continue
            ce = (children_education[i] if i < len(children_education) else "").lower()
            if 15 <= ai <= 18 and 'ol' not in ce:
                recommendations.append({
                    "type": "child_education",
                    "title": "O/L Exam Preparation",
                    "message": "Special courses for your child's O/L exams",
                    "priority": "medium",
                    "tags": ["ol_exams", "tuition", "secondary_education"]
                })
            if 17 <= ai <= 20 and 'al' not in ce:
                recommendations.append({
                    "type": "child_education",
                    "title": "A/L Stream Selection Guidance",
                    "message": "Expert guidance for A/L subject selection",
                    "priority": "medium",
                    "tags": ["al_exams", "career_guidance", "higher_education"]
                })

        return recommendations
