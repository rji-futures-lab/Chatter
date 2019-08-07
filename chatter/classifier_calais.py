"""
This is an implementation of content classification using the Calais service.  Any interactions with Calais should
be contained within this module.  By keeping the classification functionality in a self contained module/class it
would be easy to enhance Chatter to support a plugin model for content classification using a custom classifier.
"""
import logging

import requests

import chatter.config as config

clog = logging.getLogger(__name__)


class ClassifierCalais:
    def __init__(self):
        self.headers = {'Content-Type': 'text/raw',
                        'x-ag-access-token': config.calais_api_token,
                        'outputFormat': 'application/json',
                        'omitOutputtingOriginalText': 'true',
                        'x-calais-language': config.calais_classify_language
                        }

    def classify(self, title, content):
        title = title or ''
        content = content or ''
        # If there is no legit content to classify don't make the call
        if len(title) < 5 and len(content) < 10:
            return None
        if len(title) > 5:
            title = title.strip().replace("\r", " ").replace("\n", " ")
            self.headers['x-calais-DocumentTitle'] = title.encode('utf-8')
            if len(content) < 5:
                content = title
        topics = []
        num_attempts = 0
        # The Free Calais service is very flaky so we will give it a few tries
        while num_attempts < config.url_maintenance_request_retries:
            num_attempts += 1
            try:
                r = requests.post(config.calais_tag_url, headers=self.headers, data=content.encode('utf-8'), timeout=5)
                # We had a successful call so don't try any more
                num_attempts = config.url_maintenance_request_retries
                if r.ok:
                    r_json = r.json()
                    for k, v in r_json.items():
                        if '/cat/' in k:
                            topic = r_json[k]
                            topics.append({'topic': topic['name'], 'score': topic['score']})
                else:
                    # Any errors that come into the log from this should be evaluated
                    # and either fixed or added as an option here to allow retries to
                    # occur
                    clog.error('Calais request status code: %s Message: %s', r.status_code, r.text)
            except Exception as e:
                clog.error(e)
        return topics
