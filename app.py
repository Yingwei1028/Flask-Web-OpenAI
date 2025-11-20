import os
os.environ['NO_PROXY'] = '*'
os.environ['no_proxy'] = '*'
from flask import Flask, render_template, request
import openai
import requests
import json
from dotenv import load_dotenv 
load_dotenv() 
import os
import openai

app = Flask(__name__)

# --- Configuration ---
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
client = openai.OpenAI(api_key=OPENAI_API_KEY)

# AniList GraphQL URL
ANILIST_URL = "https://graphql.anilist.co"

def get_home_data():
    # Fetch both datasets in a single request: trending and popular (currently airing)
    query = '''
    query {
      trending: Page(page: 1, perPage: 5) {
        media(sort: TRENDING_DESC, type: ANIME) {
          ...mediaFields
        }
      }
      popular: Page(page: 1, perPage: 5) {
        media(sort: POPULARITY_DESC, type: ANIME, status: RELEASING) {
          ...mediaFields
        }
      }
    }
    
    fragment mediaFields on Media {
      id
      title {
        english
        romaji
      }
      coverImage {
        large
      }
      averageScore
      siteUrl
      description
    }
    '''
    
    try:
        response = requests.post(ANILIST_URL, json={'query': query})
        data = response.json()
        if 'errors' in data:
            print(data['errors'])
            return None, None
        
        return data['data']['trending']['media'], data['data']['popular']['media']
    except Exception as e:
        print(f"AniList API Error: {e}")
        return [], []

# --- Call OpenAI to get recommended titles ---
def get_ai_recommendations(user_input):
    prompt = f"""
    User request: "{user_input}"
    
    Please recommend 3 to 5 anime titles based on the request.
    Return ONLY a strictly valid JSON object with a key "anime_list" containing the titles.
    Example: {{"anime_list": ["Naruto", "Bleach"]}}
    Use English or Romaji titles that are easy to search on AniList.
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o", 
            messages=[
                {"role": "system", "content": "You are an expert anime recommender."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content
        data = json.loads(content)
        return data.get("anime_list", [])
    except Exception as e:
        print(f"OpenAI Error: {e}")
        return []

# --- Fetch anime details from AniList GraphQL ---
def fetch_anime_details(title):
    query = '''
    query ($search: String) {
      Media (search: $search, type: ANIME) {
        id
        title {
          romaji
          english
          native
        }
        coverImage {
          large
        }
        description
        averageScore
        siteUrl
      }
    }
    '''
    
    variables = {'search': title}
    
    try:
        response = requests.post(ANILIST_URL, json={'query': query, 'variables': variables})
        data = response.json()
        if 'errors' in data:
            print(f"AniList not found for: {title}")
            return None
        return data['data']['Media']
    except Exception as e:
        print(f"AniList API Error: {e}")
        return None

# --- route ---
@app.route('/', methods=['GET', 'POST'])
def index():
    recommendations = [] # Search results
    trending_list = []   # Homepage trending
    popular_list = []    # Homepage popular
    user_input = ""
    
    if request.method == 'POST':
        # --- User clicked search ---
        user_input = request.form.get('user_input')
        if user_input:
            titles = get_ai_recommendations(user_input)
            for title in titles:
                details = fetch_anime_details(title)
                if details:
                    recommendations.append(details)
    else:
        # --- User just entered homepage (GET request) ---
        # Fetch homepage recommendation data
        trending_list, popular_list = get_home_data()
    
    return render_template(
        'index.html', 
        recommendations=recommendations, 
        trending=trending_list, 
        popular=popular_list,
        last_input=user_input
    )

if __name__ == '__main__':
    app.run(debug=True)