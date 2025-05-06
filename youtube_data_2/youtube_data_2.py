import googleapiclient.discovery
import pandas as pd
import mysql.connector
from mysql.connector import Error

# YouTube API setup
api_service_name = "youtube"
api_version = "v3"
API_KEYS = [
    "AIzaSyDal06Y56qtoluWNK-11H7zHmOfiw51H3w",
    "AIzaSyBckFLmml-Bzlr4S_RJ_GO5Bwy0GJL9BWI",
    "AIzaSyCu2gLXBCGW9xJDxyZKD6rxmrkvLd_ueCo",
    "AIzaSyBeB0S4Ph9KTCcfGedAPACAErK-MjqXPWI",
    "AIzaSyBCocBBA9gRr8Pt7xNA6vVAe8FdIqSNfCg",
    "AIzaSyBflfeHCmNmiKbyTncKICuKvic-W1HaSOY"
]

quota_usage = {key: 0 for key in API_KEYS}  # Initialize quota usage tracker
MAX_QUOTA = 10000  # Maximum quota for a single API key per day

def get_youtube_service(api_key):
    """Returns a YouTube service client using the specified API key."""
    return googleapiclient.discovery.build(api_service_name, api_version, developerKey=api_key)

def check_quota(api_key):
    """Simulate a quota check for the API key."""
    remaining_quota = MAX_QUOTA - quota_usage.get(api_key, 0)
    return remaining_quota > 0

def print_quota_usage():
    """Print the remaining quota for each API key."""
    print("\nAPI Key Quota Usage:")
    for key, usage in quota_usage.items():
        remaining_quota = MAX_QUOTA - usage
        print(f"API Key {key[:10]}...: {remaining_quota} quota points remaining")

def update_quota_usage(key, cost):
    """Update quota usage for a specific API key."""
    if key in quota_usage:
        quota_usage[key] += cost

# Keywords to search
keywords = [
    "Fiesta Ready Meal", "Fiesta Ready To Go", "Fiesta Chicken Nugget", "Fiesta Crispy Bubble",
    "Fiesta Chicken Sausage", "Fiesta Tepung Roti", "Fiesta Tepung Bumbu", "Fiesta Bumbu Racik",
    "Fiesta Ready To Eat", "Fiesta Ready To Serve", "Champ Chicken Nugget", "Champ Sosis",
    "Okey Nugget Ayam", "Okey Sosis", "Asimo Nugget", "Asimo Sosis", "Akumo Nugget", "Fiesta Pizza",
    "Fiesta Ramen", "Kanzler Nugget", "Kanzler Sosis", "Kanzler Cordon Bleu", "Kanzler Singles",
    "Kimbo Sosis", "So Good Crispy Chicken Nugget", "So Nice Sosis Premium", "So Nice Sosis Siap Makan",
    "Bellfoods", "Sunny Gold Nugget", "Salam Nugget Ayam", "Salam Sosis Ayam", "Sasa Tepung Bumbu",
    "Bumbu Racik Indofood", "Sosis Gaga", "Kobe Bumbu", "Kobe Tepung", "Laukita"
]

def search_videos(youtube, query, api_key, max_results=10):
    """Searches for YouTube videos based on a query."""
    try:
        request = youtube.search().list(
            q=query,
            part="id,snippet",
            type="video",
            maxResults=max_results
        )
        response = request.execute()
        update_quota_usage(api_key, 100)  # Search API costs 100 quota points
        return response.get('items', [])
    except googleapiclient.errors.HttpError as e:
        print(f"Error with API key {api_key[:10]}...: {e}")
        return []

def fetch_video_details(youtube, video_ids, api_key):
    """Fetches video details for a list of video IDs."""
    try:
        request = youtube.videos().list(
            part="snippet,statistics",
            id=",".join(video_ids)
        )
        response = request.execute()
        update_quota_usage(api_key, len(video_ids))  # 1 point per video details request
        return response.get('items', [])
    except googleapiclient.errors.HttpError as e:
        print(f"Error fetching video details: {e}")
        return []

def fetch_channel_details(youtube, channel_ids, api_key):
    """Fetches channel details for a list of channel IDs."""
    try:
        request = youtube.channels().list(
            part="statistics",
            id=",".join(channel_ids)
        )
        response = request.execute()
        update_quota_usage(api_key, len(channel_ids))  # 1 point per channel details request
        return response.get('items', [])
    except googleapiclient.errors.HttpError as e:
        print(f"Error fetching channel details: {e}")
        return []

# Database connection
def insert_data_to_mysql(dataframe):
    """Inserts data into a MySQL database."""
    try:
        connection = mysql.connector.connect(
            host='localhost',
            database='ripple',
            user='root',
            password=''
        )
        cursor = connection.cursor()

        create_table_query = """
        CREATE TABLE IF NOT EXISTS youtube_data_2 (
            id INT AUTO_INCREMENT PRIMARY KEY,
            keyword VARCHAR(255),
            video_id VARCHAR(255) UNIQUE,
            title VARCHAR(255),
            tags TEXT,
            engagement_rate FLOAT,
            total_views INT,
            channel_name VARCHAR(255),
            subscriber_count INT,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
        cursor.execute(create_table_query)

        for _, row in dataframe.iterrows():
            check_query = "SELECT COUNT(*) FROM youtube_data_2 WHERE video_id = %s"
            cursor.execute(check_query, (row['video_id'],))
            if cursor.fetchone()[0] == 0:  # Avoid redundancy
                insert_query = """
                INSERT INTO youtube_data_2 (keyword, video_id, title, tags, engagement_rate, total_views, channel_name, subscriber_count)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """
                cursor.execute(insert_query, (
                    row['keyword'], row['video_id'], row['title'], row['tags'],
                    row['engagement_rate'], row['total_views'], row['channel_name'], row['subscriber_count']
                ))

        connection.commit()
        print("Data inserted successfully.")
    except Error as e:
        print(f"Error: {e}")
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

# Main process
def main():
    global quota_usage
    data = []
    for key in API_KEYS:
        if check_quota(key):
            youtube = get_youtube_service(key)
            for keyword in keywords:
                videos = search_videos(youtube, keyword, key)
                video_ids = [v['id']['videoId'] for v in videos]
                video_details = fetch_video_details(youtube, video_ids, key)

                for detail in video_details:
                    video_id = detail['id']
                    snippet = detail['snippet']
                    statistics = detail.get('statistics', {})
                    channel_name = snippet['channelTitle']
                    tags = ", ".join(snippet.get('tags', []))
                    total_views = int(statistics.get('viewCount', 0))
                    total_likes = int(statistics.get('likeCount', 0))
                    total_comments = int(statistics.get('commentCount', 0))
                    engagement_rate = ((total_likes + total_comments) / total_views) * 100 if total_views > 0 else 0.0

                    data.append({
                        "keyword": keyword,
                        "video_id": video_id,
                        "title": snippet['title'],
                        "tags": tags,
                        "engagement_rate": engagement_rate,
                        "total_views": total_views,
                        "channel_name": channel_name,
                        "subscriber_count": None
                    })
            print_quota_usage()

    df = pd.DataFrame(data)
    insert_data_to_mysql(df)

if __name__ == "__main__":
    main()
