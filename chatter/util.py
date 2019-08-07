"""
This module is a catch all for utility functions that may be needed throughout chatter
"""
import logging
import time
import hashlib
from urllib.parse import urlparse, parse_qsl, urlencode

import chatter.config as config

clog = logging.getLogger(__name__)

CLEANSE_PREFIXES = ('utm_', 'fbclid', 'gclid', 'trk_')


def cleanse_parse_result(p_url):
    """Given a urlib.parse.ParseResult return a urllib.parse.ParseResult cleansed of tracking query parms."""
    qp_list = parse_qsl(p_url.query)
    cleansed_qp_list = []
    clog.debug(qp_list)
    for qp in qp_list:
        if not qp[0].startswith(CLEANSE_PREFIXES):
            cleansed_qp_list.append(qp)
    return p_url._replace(query=urlencode(cleansed_qp_list))


def get_domain_ignore(url):
    """Given a url return the urllib.parse.ParseResult, and a boolean set to True if this domain should be ignored."""
    p_url = urlparse(url)
    should_ignore = False
    if p_url.netloc in config.domains_to_ignore:
        should_ignore = True
    return p_url, should_ignore


def get_hashed_string(s):
    """Given a string s return a sha1 hashed version"""
    return hashlib.sha1(s.encode('utf-8')).hexdigest()


def should_continue(message, num_tries, max_tries, sleep_time):
    """Utility method for retry functions"""
    if num_tries < max_tries:
        clog.info('%s  Will try %d more time(s) before giving up.', message, max_tries - num_tries)
        time.sleep(sleep_time)
        return True
    else:
        return False


def get_int_default_or_max(val, default_val, max_val=None):
    """Given a string try to turn it into an int and enforce a max and default if the string is not a int value"""
    try:
        i = int(val)
        if max_val and i > max_val:
            i = max_val
    except:
        i = default_val
    return i


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    url = 'https://www.westernjournal.com/nancy-pelosi-speaks-private-meeting-ocasio-cortez-walks-right-trumps-trap/?utm_source=Twitter&utm_medium=PostBottomSharingButtons&utm_campaign=websitesharingbuttons'
    p_url = urlparse(url)
    p_url = cleanse_parse_result(p_url)
    clog.debug(p_url.geturl())
