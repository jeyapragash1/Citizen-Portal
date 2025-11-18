from recommendation_engine import RecommendationEngine
from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()
MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/')
client = MongoClient(MONGO_URI)
db = client['citizen_portal']

engine = RecommendationEngine(db)

# Test with a bogus user id (should return ['unknown'] or empty recommendations)
user_id = '000000000000000000000000'
print('get_user_segment for', user_id, '->', engine.get_user_segment(user_id))
print('get_personalized_ads for', user_id, '->', engine.get_personalized_ads(user_id))
print('generate_education_recommendations for', user_id, '->', engine.generate_education_recommendations(user_id))
