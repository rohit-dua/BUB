import json

__json_data = open('../../settings.json')
__settings = json.load(__json_data)  
    
redis_key1 = __settings['redis']['key_1']
redis_key2 = __settings['redis']['key_2']
redis_key3 = __settings['redis']['key_3']

"S3 IA API keys"
S3_access_key = __settings['ia']['S3_access_key']
S3_secret_key = __settings['ia']['S3_secret_key']

"Lock Keys"
lock_key1 = __settings['lock']['key_1']

"Library API keys"
google_books_key1 = __settings['google_books']['key_1']

"Local Redis server credentials"
redis_host = __settings['redis']['host']
redis_port = int(__settings['redis']['port'])

"MySQL credentials"
db_host = __settings['db']['host']
db_username = __settings['db']['username']
db_password = __settings['db']['password']
db_database = __settings['db']['database']
       


