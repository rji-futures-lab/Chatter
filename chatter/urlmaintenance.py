"""
This module provides all functionality related to maintaining the url information for chatter.
"""
import logging
import requests
import time
from collections import Counter
from bs4 import BeautifulSoup

import chatter.dbutil as db
import chatter.config as config
from chatter.classifier_calais import ClassifierCalais
from chatter.util import get_domain_ignore, get_hashed_string, cleanse_parse_result

clog = logging.getLogger(__name__)

CLASSIFY_SLEEP_TIME = .75
URL_MAINTENANCE_SLEEP_TIME = 15


class UrlMetadataDataset:

    def __init__(self):
        self.reset()
        self.request_fails = Counter()
        self.classifier = ClassifierCalais()

    def reset(self):
        self.url_info = []
        self.url_topics = []
        self.real_url_updates = []
        self.url_hashes_to_delete = []

    def process_url(self, t_url, valid_domains):
        url = t_url['url']
        url_hash = t_url['url_hash']
        # Set the real url info to the current info, for cases when we don't need to do a tiny url lookup to
        # determine if the domain is a legit domain
        real_url = url
        real_url_hash = url_hash
        domain = t_url['domain']
        if (domain in valid_domains) or (len(url) < config.max_tiny_url_length):
            try:
                # Requests not only gets the content but follows any redirects (tiny url resolutions) for us so we
                # get the real url in the end
                r = requests.get(url, timeout=4)
                parse_results, ignore_domain = get_domain_ignore(r.url)
                domain = parse_results.netloc
                # This could happen if the ignore domains has changed since url capture, or more likely
                # when a tiny url gets expanded the real domain is discovered and is not valid
                if ignore_domain:
                    # We delete these as they are known to be not desired
                    clog.debug('This is a domain to ignore: %s', r.url)
                    self.url_hashes_to_delete.append((url_hash,))
                elif r.status_code == 404:
                    clog.debug('This URL responds with a 404 status: %s', r.url)
                else:
                    # Now that we know we have the true full URL strip the known tracking info so we don't duplicate
                    # url info
                    parse_results = cleanse_parse_result(parse_results)
                    real_url = parse_results.geturl()
                    real_url_hash = get_hashed_string(real_url)
                    if domain in valid_domains:
                        clog.info('Valid domain: %s', real_url)
                        desc, title = get_url_metadata(r)
                        # Do the get topics first so if it fails we don't end up with 2 entries in the url_info list
                        self.get_topics(real_url_hash, title, desc)
                        self.url_info.append((real_url_hash, title, desc))
            except Exception as e:
                clog.debug(e)
                self.request_fails.update([url_hash])
                clog.info('Fail number %s for url %s', self.request_fails[url_hash], real_url)
                # If we are going to allow more tries for this url, then return now
                if self.request_fails[url_hash] < config.url_maintenance_request_retries:
                    clog.error(e)
                    return
        else:
            clog.debug('Not a valid domain: %s', real_url)
        # If this is a url with a previous failed request attempt remove the failed attempt tracking for the url
        # now that we had a successful call go through
        if url_hash in self.request_fails:
            del self.request_fails[url_hash]
        self.real_url_updates.append((real_url, real_url_hash, domain, url_hash))

    def get_topics(self, real_url_hash, title, desc):
        topics = self.classifier.classify(title, desc)
        if len(topics) == 0:
            self.url_topics.append((real_url_hash, 'None', 1))
        else:
            for topic in topics:
                self.url_topics.append((real_url_hash, topic['topic'], topic['score']))

    def save(self):
        db.delete_urls_for_tweet(self.url_hashes_to_delete)
        db.update_urls_for_tweet(self.real_url_updates)
        db.add_url_info(self.url_info)
        db.add_url_topics(self.url_topics)


def get_url_metadata(r):
    tree = BeautifulSoup(r.content, "lxml")
    title = tree.title.string
    clog.debug("Page Title: %s", title)
    description = tree.find('meta', attrs={'name': 'description'})
    if description:
        description = description['content']
    else:
        description = None
    clog.debug("Page Description: %s", description)
    return description, title


def print_request_headers(r):
    for hkey, hvalue in r.headers.items():
        clog.error(f'{hkey}:{hvalue}')


def maintain_urls():
    # Need to occasionally refresh this so we pick up any changes, right now it requires restarting the process
    valid_domains = set(db.get_unique_domains())
    umd = UrlMetadataDataset()
    while True:
        t_urls = db.get_urls_needing_metadata()
        for t_url in t_urls:
            umd.process_url(t_url, valid_domains)
        umd.save()
        umd.reset()
        clog.info('Processed %s urls', len(t_urls))
        if len(t_urls) < 50:
            time.sleep(URL_MAINTENANCE_SLEEP_TIME)


def classify_urls():
    umd = UrlMetadataDataset()
    while True:
        urls_to_classify = db.get_urls_to_classify(5)
        for url in urls_to_classify:
            umd.get_topics(url['real_url_hash'], url['title'], url['description'])
        clog.info(umd.url_topics)
        umd.save()
        umd.reset()
        time.sleep(CLASSIFY_SLEEP_TIME)
