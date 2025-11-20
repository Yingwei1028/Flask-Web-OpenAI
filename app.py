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

# --- 配置 ---
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
client = openai.OpenAI(api_key=OPENAI_API_KEY)

# AniList GraphQL URL
ANILIST_URL = "https://graphql.anilist.co"

def get_home_data():
    # 一次請求抓取兩組數據：trending (趨勢) 和 popular (正在連載的熱門)
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
        
        # 返回两组列表
        return data['data']['trending']['media'], data['data']['popular']['media']
    except Exception as e:
        print(f"AniList API Error: {e}")
        return [], []

# --- 輔助函數：調用 OpenAI 獲取推薦標題 ---
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
            model="gpt-4o", # 或者 gpt-4o
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

# --- 輔助函數：調用 AniList GraphQL 獲取詳情 ---
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

# --- 路由 ---
@app.route('/', methods=['GET', 'POST'])
def index():
    recommendations = [] # 搜索結果
    trending_list = []   # 首頁趨勢
    popular_list = []    # 首頁熱門
    user_input = ""
    
    if request.method == 'POST':
        # --- 用戶點擊了搜索 ---
        user_input = request.form.get('user_input')
        if user_input:
            titles = get_ai_recommendations(user_input)
            for title in titles:
                details = fetch_anime_details(title)
                if details:
                    recommendations.append(details)
    else:
        # --- 用戶剛進入首頁 (GET 請求) ---
        # 獲取首頁推薦數據
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