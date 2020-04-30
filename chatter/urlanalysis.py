"""
This module contains support for analyzing the twitter URL data and generating a ranked list of interesting tweets
over a given time period.  Support for generating the hotlist as a JSON file via command line or via a rest service
is provided.  With the rest service a simple HTML format can be provided also for easy browser viewing.
"""
import logging
import gensim
import json
import time
import datetime
from flask import Flask, request, render_template, Response

import chatter.dbutil as db
import chatter.config as config
from chatter.util import get_int_default_or_max

clog = logging.getLogger(__name__)

DEFAULT_DAYS_AGO = 0
DEFAULT_HOURS_AGO = 0
DEFAULT_MAX_AGE = 12
MAX_AGE_FOR_SERVICE = 24
DEFAULT_CLUSTER = False
DEFAULT_JSON = False
# The default maximum results that will be returned for a request
DEFAULT_MAX_RESULTS = 50
# The true max results we will ever return for the service
MAX_RESULTS_FOR_SERVICE = 100


class HotListConfig:

    def __init__(self, args={}):
        self.days_ago = get_int_default_or_max(args.get('days_ago', DEFAULT_DAYS_AGO), DEFAULT_DAYS_AGO)
        self.hours_ago = get_int_default_or_max(args.get('hours_ago', DEFAULT_HOURS_AGO), DEFAULT_HOURS_AGO)
        self.age = get_int_default_or_max(args.get('age', DEFAULT_MAX_AGE), DEFAULT_MAX_AGE, MAX_AGE_FOR_SERVICE)
        self.max_results = get_int_default_or_max(args.get('max_results', DEFAULT_MAX_RESULTS), DEFAULT_MAX_RESULTS,
                                                  MAX_RESULTS_FOR_SERVICE)
        self.cluster = args.get('cluster', DEFAULT_CLUSTER)
        self.json = args.get('json', DEFAULT_JSON)


def get_cluster_links(links):
    docs = [' '.join([x for x in [link.get('title', None), link.get('description', None)] if x is not None])
            for link in links]

    word_split = config.get_word_split()
    stoplist = config.get_cluster_stop_list()
    texts = [[word for word in word_split.split(document.lower()) if word not in stoplist and len(word) > 1]
             for document in docs]
    all_tokens = sum(texts, [])
    tokens_once = set(word for word in set(all_tokens) if all_tokens.count(word) == 1)
    texts = [[word for word in text if word not in tokens_once] for text in texts]

    dictionary = gensim.corpora.Dictionary(texts)
    lsi = gensim.models.LsiModel(corpus=[dictionary.doc2bow(text) for text in texts], id2word=dictionary, num_topics=50)

    index = gensim.similarities.MatrixSimilarity(lsi[[dictionary.doc2bow(text) for text in texts]])

    ids = set(range(len(texts)))
    clusters = []
    while len(ids) > 0:
        text_id = min(ids)
        text = texts[text_id]
        cluster_ids = [x[0] for x in enumerate(index[lsi[dictionary.doc2bow(text)]]) if x[1] > .8 or x[0] == text_id]
        cluster_links = [links[x] for x in cluster_ids if x in ids]
        cluster_links.sort(key=lambda x: x['hotness'], reverse=True)
        if len(cluster_links) > 0:
            clusters.append(cluster_links)
        ids.difference_update(cluster_ids)
    return clusters


def calculate_hotness(age_in_hours, num_tweets):
    # This may never end up really happening, but it is allowed with current command line options
    if age_in_hours > 24.0:
        frac_age = 1.0
    else:
        frac_age = float(age_in_hours/24.0)
    if age_in_hours < 4:
        multiplier = 1.20-frac_age
    elif age_in_hours < 12:
        multiplier = 1.05-frac_age
    else:
        multiplier = 1.05-frac_age
    return round((multiplier * num_tweets), 8)


def calc_popularity_hotness(tweets, age, opts):
    popularity_factor = float((tweets-2)*int(opts.popularity_weight))
    age_factor = float(age * age)
    if opts.ignore_age:
        hotness = popularity_factor
    else:
        hotness = popularity_factor / age_factor
    return hotness


def cluster_hotness(cluster):
    age = max([link['age'] for link in cluster])
    tweets = sum([link['total_tweets'] for link in cluster])
    return calculate_hotness(age, tweets)


def gen_hot_list(hlc):
    start_time = time.time()
    links = db.get_grouped_recently_tweeted_urls(max_age=hlc.age, days_ago=hlc.days_ago, hours_ago=hlc.hours_ago)
    hot_list = {'generated_at': datetime.datetime.utcnow().isoformat() + "Z"}
    if len(links) > 0:
        for link in links:
            link['hotness'] = calculate_hotness(link['age'], link['total_tweets'])
            link['first_tweeted'] = link['first_tweeted'].isoformat() + 'Z'
        if hlc.cluster:
            clusters = get_cluster_links(links)
            clusters.sort(key=cluster_hotness, reverse=True)
            hot_list['clusters'] = clusters[:int(hlc.max_results)]
        else:
            links.sort(key=lambda x: x['hotness'], reverse=True)
            hot_list['articles'] = links[:int(hlc.max_results)]
    else:
        hot_list['message'] = "No links to process for specified parameters"

    clog.info('Time to generate hotlist: %s', time.time()-start_time)
    return hot_list


def dump_hot_list(hlc):
    hl = gen_hot_list(hlc)
    hl = json.dumps(hl, indent=1)
    print(hl)


def hot_list_request():
    hlc = HotListConfig(request.args)
    hl = gen_hot_list(hlc)
    if hlc.json:
        hl = json.dumps(hl, indent=1)
        r = Response(hl, mimetype='application/json', status=200)
        return r
    else:
        return render_template('hotlist.html', hotlist=hl)


def hot_list_service():
    app = Flask('chatter')
    app.add_url_rule(rule='/', endpoint='hotlist', view_func=hot_list_request)
    app.run(host="0.0.0.0",port=5000)
    #app.run(debug=True)
