"""
This module is responsible for handling all functions required to maintain the valid domain list for chatter.
"""
import logging
import csv

import chatter.dbutil as db

clog = logging.getLogger(__name__)


def update_domains(csv_file):
    domain_records = []
    domain_reader = csv.DictReader(csv_file, fieldnames=['domain_set', 'domain', 'subset'])
    for row in domain_reader:
        ds = row['domain_set'].strip()
        d = row['domain'].strip()
        s = row['subset'].strip()
        if ds and d:
            domain_records.append((ds, d, s if s else 'None'))
        else:
            print(f'Skipping record either domain set or domain is missing: "{ds},{d},{s}"')
    db.add_domains(domain_records)
    print(f'Succesfully upserted {len(domain_records)} domain records')


def reset_domains(csv_file):
    db.remove_all_domains()
    update_domains(csv_file)
