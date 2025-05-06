import googleapiclient.discovery
import pandas as pd
import mysql.connector
from mysql.connector import Error

# YouTube API setup with multiple keys
api_service_name = "youtube"
api_version = "v3"

API_KEYS = [
    "AIzaSyDal06Y56qtoluWNK-11H7zHmOfiw51H3w",
    "AIzaSyBckFLmml-Bzlr4S_RJ_GO5Bwy0GJL9BWI",
    "AIzaSyCu2gLXBCGW9xJDxyZKD6rxmrkvLd_ueCo",
    "AIzaSyBeB0S4Ph9KTCcfGedAPACAErK-MjqXPWI",
    "AIzaSyBflfeHCmNmiKbyTncKICuKvic-W1HaSOY"
]

current_key_index = 0

def get_youtube_service():
    global current_key_index
    api_key = API_KEYS[current_key_index]
    return googleapiclient.discovery.build(
        api_service_name, api_version, developerKey=api_key
    )

youtube = get_youtube_service()

def rotate_api_key():
    global current_key_index, youtube
    current_key_index = (current_key_index + 1) % len(API_KEYS)
    youtube = get_youtube_service()

def search_videos(query, max_results=10):
    try:
        request = youtube.search().list(
            q=query,
            part="id,snippet",
            type="video",
            maxResults=max_results
        )
        response = request.execute()

        video_data = [{
            'videoId': item['id']['videoId'],
            'title': item['snippet']['title']
        } for item in response['items']]
        return video_data
    except googleapiclient.errors.HttpError as e:
        if e.resp.status == 403 and 'quotaExceeded' in str(e):
            print("Quota exceeded. Rotating API key...")
            rotate_api_key()
            return search_videos(query, max_results)
        raise

def check_comments_enabled(video_id):
    try:
        request = youtube.commentThreads().list(
            part="snippet",
            videoId=video_id,
            maxResults=1
        )
        response = request.execute()
        return True
    except googleapiclient.errors.HttpError:
        print(f"Comments are disabled or restricted for video: {video_id}")
        return False

def get_comments(video, title, keyword):
    try:
        request = youtube.commentThreads().list(
            part="snippet",
            videoId=video,
            maxResults=100
        )

        comments = []
        response = request.execute()

        for item in response['items']:
            comment = item['snippet']['topLevelComment']['snippet']
            public = item['snippet']['isPublic']
            comments.append([
                keyword,  # Add the keyword for each comment
                comment['authorDisplayName'],
                comment['publishedAt'],
                comment['likeCount'],
                comment['textOriginal'],
                video,  # Video ID
                title,  # Video title
                public
            ])

        while 'nextPageToken' in response:
            nextPageToken = response['nextPageToken']
            nextRequest = youtube.commentThreads().list(
                part="snippet",
                videoId=video,
                maxResults=100,
                pageToken=nextPageToken
            )
            response = nextRequest.execute()
            for item in response['items']:
                comment = item['snippet']['topLevelComment']['snippet']
                public = item['snippet']['isPublic']
                comments.append([
                    keyword,  # Add the keyword for each comment
                    comment['authorDisplayName'],
                    comment['publishedAt'],
                    comment['likeCount'],
                    comment['textOriginal'],
                    video,  # Video ID
                    title,  # Video title
                    public
                ])

        df2 = pd.DataFrame(comments, columns=['keyword', 'author', 'updated_at', 'like_count', 'text', 'video_id', 'title', 'public'])
        return df2
    except googleapiclient.errors.HttpError as e:
        if e.resp.status == 403 and 'quotaExceeded' in str(e):
            print("Quota exceeded during comments fetch. Rotating API key...")
            rotate_api_key()
            return get_comments(video, title, keyword)
        print(f"Comments are disabled for video: {video}")
        return pd.DataFrame()

# List of keywords
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

# Search videos and retrieve comments for each keyword
df = pd.DataFrame()
for keyword in keywords:
    video_data = search_videos(keyword)  # Use the keyword
    enabled_videos = [data for data in video_data if check_comments_enabled(data['videoId'])]
    for video in enabled_videos:
        video_id = video['videoId']
        title = video['title']
        df2 = get_comments(video_id, title, keyword)  # Pass the keyword explicitly
        df = pd.concat([df, df2], ignore_index=True)

# Database connection and insertion with redundancy check
def insert_data_to_mysql(dataframe):
    try:
        connection = mysql.connector.connect(
            host='localhost',
            database='ripple',
            user='root',  # Replace with your MySQL username
            password=''   # Replace with your MySQL password
        )
        cursor = connection.cursor()

        # Create table if not exists
        create_table_query = """
        CREATE TABLE IF NOT EXISTS youtube_data (
            id INT AUTO_INCREMENT PRIMARY KEY,
            keyword VARCHAR(255),
            author VARCHAR(255),
            updated_at DATETIME,
            like_count INT,
            text TEXT,
            video_id VARCHAR(255),
            title VARCHAR(255),
            public BOOLEAN
        )
        """
        cursor.execute(create_table_query)

        # Insert data into the table, avoiding redundancy
        for _, row in dataframe.iterrows():
            # Check for redundancy
            check_query = """
            SELECT COUNT(*) FROM youtube_data
            WHERE video_id = %s AND text = %s
            """
            cursor.execute(check_query, (row['video_id'], row['text']))
            result = cursor.fetchone()

            if result[0] == 0:  # If no existing record matches
                insert_query = """
                INSERT INTO youtube_data (keyword, author, updated_at, like_count, text, video_id, title, public)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """
                cursor.execute(insert_query, tuple(row))

        connection.commit()
        print("Data inserted successfully, avoiding redundant entries.")

    except Error as e:
        print(f"Error: {e}")
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

# Insert data into MySQL database
insert_data_to_mysql(df)
