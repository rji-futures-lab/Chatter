"""
All global configurations that we want set on application startup are contained within this module.  Some
configurations can/must be set in the config.yaml file and others are only here for now.  As it is determined
more parts of the application should be tunable at install additional configuration settings should be added here.
"""
import json
import re

# All settings that come from the configuration file(s) have globals defined here
# DB configuration settings
db_name = None
db_user = None
db_password = None
db_min_conn = None
db_max_conn = None
db_host = None
db_port = None

# Twitter account access settings
twitter_screen_name = None
twitter_consumer_key = None
twitter_consumer_secret = None
twitter_access_token_key = None
twitter_access_token_secret = None


# Calais settings
calais_api_token = None
# The url to the calais classifier
calais_tag_url = 'https://api.thomsonreuters.com/permid/calais'
# The default language for calais
calais_classify_language = 'English'

# Chatter configs that can be over ridden in yaml file
# Specify domains that should be ignored during tweet capture
domains_to_ignore = {
    'twitter.com', 'www.youtube.com' 'www.facebook.com', 'youtu.be',
    'www.instagram.com'
}

commands = {}

# Chatter configs that can only be set in the code here
# Specify how many times to retry a failed url call during url maintenance
url_maintenance_request_retries = 3
# Length of url to qualify as a tiny url requiring request redirection to determine the real url
max_tiny_url_length = 30
# Set whether all fatal exceptions should cause the progam to stop
exit_on_error = True

_cluster_stop_list = None
def get_cluster_stop_list():
    global _cluster_stop_list
    if _cluster_stop_list is None:
        with open('stoplist.json') as fh:
            __cluster_stop_list = json.load(fh)
    return __cluster_stop_list


_word_split = None
def get_word_split():
    global _word_split
    if _word_split is None:
        _word_split = re.compile("[^a-zA-Z0-9_']")
    return _word_split
