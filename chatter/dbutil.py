"""
All interaction with the Chatter database is handled by this module.  Any and all calls to the database should be
contained within this module.
"""
import psycopg2
import psycopg2.extras
from psycopg2 import pool
from contextlib import contextmanager
import logging

import chatter.config as config

clog = logging.getLogger(__name__)

_conn_pool = None


@contextmanager
def get_db_connection():
    global _conn_pool
    if _conn_pool is None:
        _conn_pool = pool.SimpleConnectionPool(
            host=config.db_host,
            port=config.db_port,
            minconn=config.db_min_conn,
            maxconn=config.db_max_conn,
            dbname=config.db_name,
            user=config.db_user,
            password=config.db_password
        )
    try:
        conn = _conn_pool.getconn()
        yield conn
    finally:
        _conn_pool.putconn(conn)


@contextmanager
def get_db_cursor(commit=True):
    with get_db_connection() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            yield cur
            if commit:
                conn.commit()
        finally:
            cur.close()


def execute_many(sql, data):
    with get_db_cursor() as cur:
        try:
            cur.executemany(sql, data)
        except psycopg2.Error as error:
            clog.exception(f'Error executing sql ({sql}) with data ({data})')
        finally:
            clog.debug(cur.query)


@contextmanager
def execute_query(sql, data=None):
    with get_db_cursor() as cur:
        try:
            cur.execute(sql, data)
            yield cur
        except psycopg2.Error as error:
            clog.exception(f'Error executing sql: {sql}')
        finally:
            clog.debug(cur.query)


def add_tweets(tweets):
    if len(tweets) > 0:
        sql = "INSERT INTO tweets(tweet_id, text, user_id, created_at, retweeted_tweet_id) VALUES(%s, %s, %s, %s, %s) ON CONFLICT ON CONSTRAINT tweets_pkey DO NOTHING"
        execute_many(sql, tweets)


def add_urls_for_tweet(urls):
    if len(urls) > 0:
        sql = "INSERT INTO tweeted_urls(tweet_id, url_hash, url, domain) VALUES(%s, %s, %s, %s) ON CONFLICT ON CONSTRAINT tweeted_urls_pkey DO NOTHING"
        execute_many(sql, urls)


def update_urls_for_tweet(url_metadata):
    if len(url_metadata) > 0:
        sql = "UPDATE tweeted_urls SET real_url=%s, real_url_hash=%s, domain=%s WHERE url_hash=%s"
        execute_many(sql, url_metadata)


def delete_urls_for_tweet(url_hashes):
    if len(url_hashes) > 0:
        sql = "DELETE FROM tweeted_urls WHERE url_hash=%s"
        execute_many(sql, url_hashes)


def add_hashtags_for_tweets(hashtags):
    if len(hashtags) > 0:
        sql = "INSERT INTO tweeted_hashtags(tweet_id, hashtag) VALUES(%s, %s) ON CONFLICT ON CONSTRAINT tweeted_hashtags_pkey DO NOTHING"
        execute_many(sql, hashtags)


def add_userids_for_tweets(userids):
    if len(userids) > 0:
        sql = "INSERT INTO users(user_id, date_added) VALUES(%s, NOW()) ON CONFLICT ON  CONSTRAINT users_pkey DO NOTHING"
        execute_many(sql, userids)


def get_userids_needing_list(users_per_fill=100):
    query = f"SELECT user_id FROM users WHERE list_id IS NULL AND suspended = False LIMIT {users_per_fill}"
    with execute_query(query) as cur:
        rows = cur.fetchall()
        return [row['user_id'] for row in rows]


def get_listids_to_count():
    query = "SELECT list_id, COUNT(*) as num FROM users WHERE list_id IS NOT NULL GROUP BY list_id ORDER BY list_id ASC"
    with execute_query(query) as cur:
        return cur.fetchall()


def set_user_list(listid_userid):
    if len(listid_userid) > 0:
        sql = "UPDATE users SET list_id = %s WHERE user_id = %s"
        execute_many(sql, listid_userid)


def get_userids_to_update(max_ids=100):
    query = f"SELECT user_id FROM users ORDER BY last_updated ASC NULLS FIRST LIMIT {max_ids}"
    with execute_query(query) as cur:
        return cur.fetchall()


def update_user_data(users):
    if len(users) > 0:
        sql = "UPDATE users SET screen_name = %s, friends_count = %s, followers_count = %s, name = %s, profile_image_url = %s, location = %s, suspended = False, last_updated = NOW() WHERE user_id = %s"
        execute_many(sql=sql, data=users)


def suspend_users(users):
    if len(users) > 0:
        sql = "UPDATE users SET suspended = True, last_updated = NOW() WHERE user_id = %s"
        execute_many(sql=sql, data=users)


def get_urls_needing_metadata(urls_per_fill=100):
    query = f"SELECT url_hash, url, domain FROM tweeted_urls WHERE real_url_hash IS NULL GROUP BY url_hash, url, domain LIMIT {urls_per_fill}"
    with execute_query(query) as cur:
        return cur.fetchall()
        #return [{'url_hash':row[0], 'url':row[1], 'domain':row[2]} for row in rows]


def add_domains(domains):
    if len(domains) > 0:
        sql = "INSERT INTO domains(domain_set, domain, subset) VALUES(%s, %s, %s) ON CONFLICT ON CONSTRAINT domains_pkey DO NOTHING"
        execute_many(sql, domains)


def remove_all_domains():
    sql = 'TRUNCATE TABLE domains'
    with get_db_cursor() as cur:
        cur.execute(sql)


def get_unique_domains():
    query = f"SELECT domain FROM domains GROUP BY domain"
    with execute_query(query) as cur:
        rows = cur.fetchall()
        return [row['domain'] for row in rows]


def add_url_info(url_info):
    if len(url_info) > 0:
        sql = "INSERT INTO url_info(real_url_hash, title, description) VALUES(%s, %s, %s) ON CONFLICT ON CONSTRAINT url_info_pkey DO NOTHING"
        execute_many(sql, url_info)


def get_urls_to_classify(urls_per_fill=100):
    query = ' '.join(("SELECT ui.real_url_hash, ui.title, ui.description FROM URL_INFO ui",
                     "LEFT OUTER JOIN url_topics ut ON ui.real_url_hash=ut.real_url_hash",
                     "WHERE ut.real_url_hash IS null LIMIT", str(urls_per_fill)))
    with execute_query(query) as cur:
        return cur.fetchall()
        #return [{'real_url_hash': row[0], 'title': row[1], 'description': row[2]} for row in rows]


def add_url_topics(url_topics):
    if len(url_topics) > 0:
        sql  = "INSERT INTO url_topics(real_url_hash, topic, score) VALUES(%s, %s, %s) ON CONFLICT ON CONSTRAINT url_topics_pkey DO NOTHING"
        execute_many(sql, url_topics)


def get_grouped_recently_tweeted_urls(max_age, days_ago, hours_ago):
    query = ' '.join(("select real_url as url, count(distinct t.user_id) as total_tweets, MIN(created_at) as first_tweeted,",
                      "(EXTRACT(epoch from (AGE(NOW() - interval '%s day %s hour', min(created_at))))/3600)::real as age,"
                      "real_url_hash as hash, domain, title, description,"
                      "array(select array[topic, score::character varying] from url_topics ut where ut.real_url_hash = tu.real_url_hash order by score desc) as topics",
                      "from tweeted_urls tu inner join tweets t using(tweet_id) inner join url_info using(real_url_hash)",
                      "where created_at < now() - interval '%s day %s hour'",
                      "group by real_url, real_url_hash, domain, title, description",
                      "having AGE(NOW() - interval '%s day %s hour', min(created_at)) < interval '%s hour'",
                      "order by total_tweets desc, age asc"))
    # Psycopg needs these to be strings for them to get encoded right for the query
    days_ago = int(days_ago)
    max_age = int(max_age)
    hours_ago = int(hours_ago)
    with execute_query(query, (days_ago, hours_ago, days_ago, hours_ago, days_ago, hours_ago, max_age)) as cur:
        return cur.fetchall()
