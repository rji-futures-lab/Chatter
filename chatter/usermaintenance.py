"""
This module provides all functionality related to maintaining the user information for chatter.
"""
import logging
import time

import chatter.dbutil as db
import chatter.twitter as twitter

clog = logging.getLogger(__name__)

LIST_PREFIX = 'chatter'
LIST_SLEEP_TIME = 15
MAX_USERS_PER_LIST = 4999
MAX_USERS_PER_DAY = 1000
NUM_SECONDS_FOR_REST_PERIOD = 86400

USER_SLEEP_TIME = 5


def maintain_lists():
    total_users_added = 0
    start_time = time.time()
    while True:
        uids = db.get_userids_needing_list(100)
        if len(uids) == 0:
            clog.info("No users needing a list")
            time.sleep(LIST_SLEEP_TIME)
        else:
            list_counts = db.get_listids_to_count()
            clog.debug('List counts: %s', list_counts)
            slug = None
            next_list_num = 1
            list_user_count = 0
            for row in list_counts:
                if row['num'] < MAX_USERS_PER_LIST:
                    slug = row['list_id']
                    list_user_count = row['num']
                    break
                else:
                    next_list_num += 1
            # If there are no lists with room create a new list to add users to
            if slug is None:
                slug = f'{LIST_PREFIX}{next_list_num}'
                twitter.add_list(slug)

            remaining_count = (MAX_USERS_PER_LIST - list_user_count)
            uids = uids[:remaining_count]
            clog.info("Adding %d users to list %s", len(uids), slug)
            total_users_added += len(uids)
            uid_string = ",".join(map(str, uids))
            twitter.add_users_to_list(list_name=slug, users=uid_string)
            listid_userid = [(slug, uid) for uid in uids]
            db.set_user_list(listid_userid)

            # Twitter seems to only allow MAX_USERS_PER_DAY to be added to lists so deal with it
            seconds_since_reset = time.time() - start_time
            if total_users_added < MAX_USERS_PER_DAY:
                clog.debug('Normal sleep time')
                time.sleep(LIST_SLEEP_TIME)
            else:
                clog.debug('Day sleep time')
                time.sleep(NUM_SECONDS_FOR_REST_PERIOD - seconds_since_reset + 5)
                seconds_since_reset = time.time() - start_time
            # Every 24 hours reset the twitter limit tracking
            if seconds_since_reset > NUM_SECONDS_FOR_REST_PERIOD:
                clog.info("It's been %s seconds so we are reseting the tracking", seconds_since_reset)
                total_users_added = 0
                start_time = time.time()


def maintain_users():
    ids = db.get_userids_to_update()
    if len(ids) == 0:  # This will only happen in a new system that hasn't started tweet capture yet
        clog.error("No users to update, make sure you have ran a tweet capture job!")
        return
    while True:
        uids = [row['user_id'] for row in ids]
        uid_string = ",".join(map(str, uids))
        response = twitter.get_info_for_users(uid_string)
        clog.info("Refreshing %d users", len(response))
        info_dict = {x['id']: x for x in response}
        user_updates = []
        user_suspensions = []
        for uid in uids:
            if uid in info_dict:
                ui = info_dict[uid]
                info_tuple = (ui['screen_name'], ui['friends_count'], ui['followers_count'], ui['name'],
                              ui['profile_image_url'], ui['location'], uid)
                user_updates.append(info_tuple)
            else:
                user_suspensions.append((uid,))
        db.update_user_data(user_updates)
        db.suspend_users(user_suspensions)
        time.sleep(USER_SLEEP_TIME)
        # Get the next set of users ids to process
        ids = db.get_userids_to_update()
