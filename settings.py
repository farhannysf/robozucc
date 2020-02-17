from os import environ
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

FB_EMAIL = environ['FB_EMAIL']
FB_PASSWORD = environ['FB_PASSWORD']
FB_UID = environ['FB_UID']
HAYSTACK_APIKEY = environ['HAYSTACK_APIKEY']
MSVISION_APIKEY = environ['MSVISION_APIKEY']
CLEVERBOT_APIKEY = environ['CLEVERBOT_APIKEY']