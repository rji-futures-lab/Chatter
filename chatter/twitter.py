from TwitterAPI import TwitterAPI, TwitterConnectionError, TwitterRequestError, TwitterPager
from dateutil import parser as date_parser
import time
import logging

import chatter.dbutil as db
from chatter.custom_twitter_pager import CustomTwitterPager
import chatter.config as config
from chatter.util import get_domain_ignore
from chatter.util import get_hashed_string
from chatter.util import should_continue

clog = logging.getLogger(__name__)

# Constants for the rate limit headers
HEADER_RATE_LIMIT = 'x-rate-limit-limit'
HEADER_LIMIT_REMAINING = 'x-rate-limit-remaining'
HEADER_LIMIT_RESET = 'x-rate-limit-reset'
# Constants for all the twitter resources utilized
R_LISTS_OWNERSHIPS = 'lists/ownerships'
R_LISTS_CREATE = 'lists/create'
R_LISTS_MEMBERS_CREATE_ALL = 'lists/members/create_all'
R_USERS_LOOKUP = 'users/lookup'
GEO_PAUSE = 2.2
GEO_COUNT = 100
LIST_PAUSE = 1.0
LIST_COUNT = 200
MAX_CAPTURE_SLEEP_TIME = 30
MAX_REQUEST_TRIES = 3
REQUEST_RETRY_SLEEP_TIME = 3

_app_api = None
_user_api = None


class TweetCaptureDataset:

    def __init__(self):
        self.reset()

    def reset(self):
        self.tweets = []
        self.urls = []
        self.mentions = []
        self.hashtags = []
        self.userids = set()

    def _add_url(self, tweet_id, url):
        parsed_result, ignore_domain = get_domain_ignore(url)
        if ignore_domain:
            return False
        else:
            self.urls.append((tweet_id, get_hashed_string(url), url, parsed_result.netloc))
            return True

    def add_tweet(self, tweet):
        has_url = False
        tweet_id = tweet['id']
        # Capture any urls of interest in the tweet, and flag if we do have a URL of interest
        for url in tweet['entities']['urls']:
            url = url['expanded_url']
            if self._add_url(tweet_id=tweet_id, url=url):
                has_url = True
        # Capture any media links of interest in the tweet, and flag if we do have a media link of interest
        if 'extended_entities' in tweet:
            for media in tweet['extended_entities']['media']:
                url = media['expanded_url']
                if self._add_url(tweet_id=tweet_id, url=url):
                    has_url = True
        if has_url:
            retweeted_id = None
            if 'retweeted_status' in tweet:
                retweeted_id = tweet['retweeted_status']['id_str']
            self.tweets.append((tweet_id, tweet['text'], tweet['user']['id'],
                                str(date_parser.parse(tweet['created_at'])), retweeted_id))
            self.userids.add(tweet['user']['id'])
            self.hashtags.extend([(tweet_id, x['text']) for x in tweet['entities']['hashtags']])

    def save(self):
        if len(self.tweets) > 0:
            clog.info("Adding %s new tweets", len(self.tweets))
            db.add_tweets(self.tweets)
            # We don't need to do a len check for url's as the current addTweet rules do not capture the tweet unless
            # there are valid urls in the tweet
            db.add_urls_for_tweet(self.urls)
            db.add_hashtags_for_tweets(self.hashtags)
            db.add_userids_for_tweets([(userid,) for userid in self.userids])
            self.reset()
            return True
        else:
            return False


class ListInfo:
    def __init__(self):
        self.pointer = 0
        self.update_from_db()

    def update_from_db(self):
        lists = db.get_listids_to_count()
        self.lists = [x['list_id'] for x in lists]
        self.last_updated = time.time()

    def get_next_list(self):
        out = self.lists[self.pointer]
        self.pointer += 1
        if self.pointer >= len(self.lists):
            self.pointer = 0
            if time.time() > (self.last_updated + 60*60):
                self.update_from_db()
        return out


def _get_api(app_auth=True):
    global _app_api
    global _user_api
    if app_auth:
        if _app_api is None:
            _app_api = TwitterAPI(consumer_key=config.twitter_consumer_key,
                                  consumer_secret=config.twitter_consumer_secret, auth_type='oAuth2')
        return _app_api
    else:
        if _user_api is None:
            _user_api = TwitterAPI(consumer_key=config.twitter_consumer_key,
                                   consumer_secret=config.twitter_consumer_secret,
                                   access_token_key=config.twitter_access_token_key,
                                   access_token_secret=config.twitter_access_token_secret)
        return _user_api


def _api_request(resource, params=None, method_override=None, app_auth=True):
    num_tries = 0
    # Sometimes Twitter just flakes out so give it a few tries before saying things are down
    while num_tries < MAX_REQUEST_TRIES:
        num_tries += 1
        try:
            r = _get_api(app_auth).request(resource=resource, params=params, method_override=method_override)
            rl_for_request(resource=resource, request=r)
            return r
        except TwitterRequestError as tre:
            if tre.status_code < 500:
                # something needs to be fixed before re-connecting
                raise
            else:
                if should_continue(message='Error on Twitter request.', num_tries=num_tries,
                                   max_tries=MAX_REQUEST_TRIES, sleep_time=REQUEST_RETRY_SLEEP_TIME):
                    pass
                else:
                    raise
        except TwitterConnectionError as tce:
            if should_continue(message='Unable to connect to twitter.', num_tries=num_tries,
                               max_tries=MAX_REQUEST_TRIES, sleep_time=REQUEST_RETRY_SLEEP_TIME):
                pass
            else:
                raise


def api_test():
    r = _api_request(resource='lists/statuses',
                     params={'slug': 'tminer1', 'owner_screen_name': '4Miner2', 'since_id': 8465691000})
    clog.debug(r.get_quota())
    json = r.json()
    clog.debug(json)
    tweets = [(tweet['id'], tweet['text'], tweet['created_at'], tweet['user']['id'],
               tweet.get('retweeted_tweet_id', None)) for tweet in r.get_iterator()]
    clog.debug(tweets)


def rl_for_request(request, resource=''):
    limits = None
    if HEADER_LIMIT_REMAINING in request.headers:
        limits = {'limit': request.headers[HEADER_RATE_LIMIT], 'remaining': request.headers[HEADER_LIMIT_REMAINING],
                  'reset': request.headers[HEADER_LIMIT_RESET]}
        clog.debug('%s - %s', resource, limits)
    else:
        clog.debug('No rate limit info in header for resource %s', resource)
    return limits


def get_rate_limit_status(user_limits=False):
    r = _api_request(resource='application/rate_limit_status', params={'resources': 'search,lists'},
                     app_auth=(not user_limits))
    json = r.json()
    for resource in json['resources']:
        for item in json['resources'][resource].items():
            print(item)


def get_lists():
    r = _api_request(resource=R_LISTS_OWNERSHIPS, app_auth=False)
    return r


def list_exists(list_name):
    r = get_lists()
    rjson = r.json()
    for item in rjson['lists']:
        if item['slug'] == list_name:
            return True
    return False


def get_info_for_users(userids):
    params = {'user_id': userids}
    r = _api_request(resource=R_USERS_LOOKUP, params=params, app_auth=False)
    rjson = r.json()
    return rjson


def add_list(list_name):
    params = {'name': list_name, 'mode': 'private',
              'description': f'List {list_name} used by the Chatter app.  Do not delete.'}
    _api_request(resource=R_LISTS_CREATE, params=params, app_auth=False)


def add_users_to_list(list_name, users):
    params = {'slug': list_name, 'owner_screen_name': config.twitter_screen_name, 'user_id': users}
    _api_request(resource=R_LISTS_MEMBERS_CREATE_ALL, params=params, app_auth=False)


def capture_geo(long, lat, radius, since_id):
    sleep_time = GEO_PAUSE
    params = {'geocode': f'{lat},{long},{radius}mi', 'result_type': 'recent', 'count': GEO_COUNT, 'since_id': since_id}
    while True:
        try:
            pager = CustomTwitterPager(_get_api(), 'search/tweets', params=params)
            tcd = TweetCaptureDataset()
            had_tweet = False
            for tweet in pager.get_iterator(wait=GEO_PAUSE, new_tweets=True, max_iterations=3):
                had_tweet = True
                if tweet['id'] > since_id:
                    params['since_id'] = tweet['id']
                tcd.add_tweet(tweet)
            if had_tweet:
                if not tcd.save():
                    clog.info('No new relevant Geo tweets')
                sleep_time = GEO_PAUSE
            else:  # If we did not have any tweets begin the backoff of calling the API
                sleep_time += GEO_PAUSE
                if sleep_time > MAX_CAPTURE_SLEEP_TIME:
                    sleep_time = MAX_CAPTURE_SLEEP_TIME
                clog.info('No new tweets for geo setting sleep time to: %f', sleep_time)
        except Exception as e:
            clog.exception("Error while trying to capture tweets for geo location")
            if config.exit_on_error:
                return
        time.sleep(sleep_time)


def capture_list(list_name, latest_tweet_id=0):
    params = {'slug': list_name, 'owner_screen_name': config.twitter_screen_name, 'count': LIST_COUNT}
    max_iterations = 0
    # If we don't have a maximum tweet id then we only want to process the current LIST_COUNT of tweets
    if latest_tweet_id == 0:
        max_iterations = 1
    pager = CustomTwitterPager(_get_api(app_auth=False), 'lists/statuses', params=params)
    tcd = TweetCaptureDataset()
    max_tweet_id = latest_tweet_id
    for tweet in pager.get_iterator(wait=1, new_tweets=False, max_iterations=max_iterations):
        tweet_id = tweet['id']
        if tweet_id and (tweet_id > latest_tweet_id):
            tcd.add_tweet(tweet)
            if tweet_id > max_tweet_id:
                max_tweet_id = tweet_id
        else:
            break
    if not tcd.save():
        clog.info('No new relevant tweets for list: %s', list_name)
    return max_tweet_id


def capture_user_lists():
    list_info = ListInfo()
    latest_tweet_by_list = {}
    while True:
        try:
            list_id = list_info.get_next_list()
            latest_tweet_by_list[list_id] = capture_list(list_id, latest_tweet_by_list.get(list_id, 0))
        except Exception as e:
            clog.exception("Error while trying to capture tweets for lists")
            if config.exit_on_error:
                return


# This is a sample for how to use the streaming api, but it is more limiting in the results so we are not using now
def stream():
    while True:
        try:
            params = {'locations': '-92.508292, 38.719794, -92.083895, 39.133516 '}
            iterator = _api_request(resource='statuses/filter', params=params).get_iterator()
            for item in iterator:
                if 'text' in item:
                    clog.info(item['text'])
                elif 'disconnect' in item:
                    event = item['disconnect']
                    if event['code'] in [2, 5, 6, 7]:
                        # something needs to be fixed before re-connecting
                        raise Exception(event['reason'])
                    else:
                        # temporary interruption, re-try request
                        break
        except TwitterRequestError as e:
            if e.status_code < 500:
                # something needs to be fixed before re-connecting
                raise
            else:
                # temporary interruption, re-try request
                pass
        except TwitterConnectionError:
            # temporary interruption, re-try request
            pass
