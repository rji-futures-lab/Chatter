"""
Chatter command line entry point.  All handling of the command line options and settings as well as basic application
startup configuration are contained within this module.  As new commands become identified they should be plugged in
using the framework contained within this module.
"""
import anyconfig
import argparse
import os
import sys
import logging
import threading
import time
from pkg_resources import resource_filename, resource_string

import chatter.config as config
import chatter.twitter as twitter
import chatter.usermaintenance as userm
import chatter.domainmaintenance as dm
import chatter.urlmaintenance as urlm
import chatter.urlanalysis as urla

# Set the logger to the package name so this modules logging configuration
# applies to all modules in the package
clog = logging.getLogger('chatter')

DEFAULT_CONFIG = resource_string('chatter', 'config/config.yaml')
DEFAULT_CONFIG_LOCATION = resource_filename('chatter', 'config/config.yaml')
DEFAULT_CONFIG_DIRECTORY, DEFAULT_CONFIG_FILE = os.path.split(resource_filename('chatter', 'config/config.yaml'))


def load_config(config_dir=DEFAULT_CONFIG_DIRECTORY, config_override_file=None):
    try:
        config_files = [os.path.join(config_dir, DEFAULT_CONFIG_FILE)]
        if config_override_file is not None:
            config_files.append(os.path.join(config_dir, config_override_file))
        fconfig = anyconfig.load(config_files, ac_parser="yaml")
        db_settings = fconfig['db']
        # Set the DB configuration
        config.db_name = db_settings['name']
        config.db_user = db_settings['user']
        config.db_password = db_settings['password']
        config.db_min_conn = db_settings['min_conn']
        config.db_max_conn = db_settings['max_conn']
        config.db_port = db_settings['port']
        config.db_host = db_settings['host']
        # Set the Twitter configuration
        twitter_settings = fconfig['twitter']
        config.twitter_screen_name = twitter_settings['screen_name']
        config.twitter_consumer_key = twitter_settings['consumer_key']
        config.twitter_consumer_secret = twitter_settings['consumer_secret']
        config.twitter_access_token_key = twitter_settings['access_token_key']
        config.twitter_access_token_secret = twitter_settings['access_token_secret']
        # Set the Calais configuration information
        calais_settings = fconfig['calais']
        config.calais_api_token = calais_settings['api_token']
        # Set the chatter app configurations
        if fconfig.get('domains_to_ignore', None) is not None:
            config.domains_to_ignore = fconfig['domains_to_ignore']

        # Load threaded commands
        if fconfig.get('commands', None) is not None:
            config.commands = fconfig['commands']

    except Exception as e:
        print('Unable to load configuration file make sure your config.yaml exists and is accessible.')
        print(e)
        exit(1)


def process_base_args(args):
    clog.setLevel(getattr(logging, args.log_level))
    load_config(args.cfg_dir, args.cfg_fname)
    clog.info(f'Successfully loaded Chatter configuration from {args.cfg_dir}')


def get_config_parser():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('-cd', dest='cfg_dir', default=DEFAULT_CONFIG_DIRECTORY,
                        help='Specify the directory containing your config.yaml file')
    parser.add_argument('-co', dest='cfg_fname', help='Name of file in config-dir containing '
                                                      'configuration overrides for the base config.yaml file')
    parser.add_argument('-log', dest='log_level', default='INFO', help='Set log level',
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'])
    return parser


def get_cmd_parser(cmd):
    return argparse.ArgumentParser(description=CMD_TO_DESC[cmd][DESC_KEY],
                                   usage=CMD_TO_DESC[cmd][USAGE_KEY], parents=[get_config_parser()])


def get_command_usage(command='<command>', args=''):
    return '%(prog)s ' + command + ' ' + args + ' [<args>]'


CMD_GEO_CAPTURE = 'geocapture'
CMD_LIST_CAPTURE = 'listcapture'
CMD_TWITTER_RL = 'twitterrl'
CMD_DOMAINS = 'domains'
CMD_LIST_MAINT = 'listmaint'
CMD_USER_MAINT = 'usermaint'
CMD_URL_MAINT = 'urlmaint'
CMD_HOT_URLS = 'hoturls'
CMD_HOT_URL_SERVICE = 'hoturlservice'
CMD_THREADED = 'threaded'
DESC_KEY = 'desc'
USAGE_KEY = 'usage'
CMD_TO_DESC = {
    CMD_GEO_CAPTURE: {DESC_KEY: 'Capture tweets for a given geocode radius',
                      USAGE_KEY: get_command_usage(CMD_GEO_CAPTURE, 'lat long radius')},
    CMD_LIST_CAPTURE: {DESC_KEY: 'Capture tweets for twitter account lists',
                       USAGE_KEY: get_command_usage(CMD_LIST_CAPTURE, '')},
    CMD_LIST_MAINT: {DESC_KEY: 'Maintain the user account lists',
                     USAGE_KEY: get_command_usage(CMD_LIST_MAINT, '')},
    CMD_TWITTER_RL: {DESC_KEY: 'Get the Twitter rate limit statuses',
                     USAGE_KEY: get_command_usage(CMD_TWITTER_RL)},
    CMD_USER_MAINT: {DESC_KEY: 'Maintain user Twitter info',
                     USAGE_KEY: get_command_usage(CMD_USER_MAINT)},
    CMD_URL_MAINT: {DESC_KEY: 'Populate metadata for urls of interest',
                    USAGE_KEY: get_command_usage(CMD_URL_MAINT)},
    CMD_DOMAINS: {DESC_KEY: 'Manage the domains of interest',
                  USAGE_KEY: get_command_usage(CMD_DOMAINS, 'filename')},
    CMD_HOT_URLS: {DESC_KEY: 'Create list of hot urls',
                   USAGE_KEY: get_command_usage(CMD_HOT_URLS)},
    CMD_HOT_URL_SERVICE: {DESC_KEY: 'Start REST service for getting hot url lists',
                   USAGE_KEY: get_command_usage(CMD_HOT_URL_SERVICE)},
    CMD_THREADED: {DESC_KEY: 'Run multiple commands on a single instance',
                    USAGE_KEY: get_command_usage(CMD_THREADED)}
}


class Cli:

    def __init__(self):
        usage = f'''{get_command_usage()}

The following chatter commands are available:
    {CMD_GEO_CAPTURE}     {CMD_TO_DESC[CMD_GEO_CAPTURE][DESC_KEY]}
    {CMD_LIST_CAPTURE}    {CMD_TO_DESC[CMD_LIST_CAPTURE][DESC_KEY]}
    {CMD_LIST_MAINT}      {CMD_TO_DESC[CMD_LIST_MAINT][DESC_KEY]}
    {CMD_USER_MAINT}      {CMD_TO_DESC[CMD_USER_MAINT][DESC_KEY]}
    {CMD_URL_MAINT}       {CMD_TO_DESC[CMD_URL_MAINT][DESC_KEY]}
    {CMD_DOMAINS}        {CMD_TO_DESC[CMD_DOMAINS][DESC_KEY]}
    {CMD_TWITTER_RL}      {CMD_TO_DESC[CMD_TWITTER_RL][DESC_KEY]}
    {CMD_HOT_URLS}        {CMD_TO_DESC[CMD_HOT_URLS][DESC_KEY]}
    {CMD_HOT_URL_SERVICE}  {CMD_TO_DESC[CMD_HOT_URL_SERVICE][DESC_KEY]}
    {CMD_THREADED}         {CMD_TO_DESC[CMD_THREADED][DESC_KEY]}

'%(prog)s <command> -h' will get command specific help
    '''
        parser = argparse.ArgumentParser(usage=usage)
        parser.add_argument('command', help='The Chatter command to run')
        args = parser.parse_args(sys.argv[1:2])
        if not hasattr(self, args.command):
            parser.print_usage()
            clog.critical(f"error: '{args.command}'" + ' is not a valid chatter command.')
            exit(1)
        # Need to move this to after the cd and co commands are processed
        # load_config()
        getattr(self, args.command)(get_cmd_parser(args.command))

    # run multiple commands (saves on per-instance overhead)
    # in this case, the commands are loaded from the config
    def threaded(self,parser):
        args = parser.parse_args(sys.argv[2:])
        process_base_args(args)
        # for each command in the config
        for c in config.commands:
            print(c)
            # run the command on a thread with the provided args
            if c['cmd'] == 'geocapture':
                x = threading.Thread(target=twitter.capture_geo,args=(c['long'],c['lat'],c['radius'],0))
                x.start()
            elif c['cmd'] == 'listcapture':
                x = threading.Thread(target=twitter.capture_user_lists)
                x.start()
            elif c['cmd'] == 'listmaint':
                x = threading.Thread(target=userm.maintain_lists)
                x.start()
            elif c['cmd'] == 'usermaint':
                x = threading.Thread(target=userm.maintain_users)
                x.start()
            elif c['cmd'] == 'urlmaint':
                x = threading.Thread(target=urlm.maintain_urls)
                x.start()
            elif c['cmd'] == 'twitterrl':
                x = threading.Thread(target=twitter.get_rate_limit_status,args=(c['user_limits']))
                x.start()
            elif c['cmd'] == 'hoturls':
                x = threading.Thread(target=urla.dump_hot_list,args=c)
                x.start()
            # elif c['cmd'] == 'hoturlservice':
            #     x = threading.Thread(target=urla.hot_list_service)
            #     x.start()
            else:
                print(f"command {c['cmd']} not supported for threading")
        urla.hot_list_service()
        # while True:
        #     time.sleep(600)

    def geocapture(self, parser):
        parser.add_argument('lat', type=float, help='The latitude for the tweet epicenter')
        parser.add_argument('long', type=float, help='The longitude for the tweet epicenter')
        parser.add_argument('radius', type=int, help='The radius from the epicenter for tweet capture')
        args = parser.parse_args(sys.argv[2:])
        process_base_args(args)
        twitter.capture_geo(args.long, args.lat, args.radius, 0)

    def listcapture(self, parser):
        args = parser.parse_args(sys.argv[2:])
        process_base_args(args)
        twitter.capture_user_lists()

    def listmaint(self, parser):
        args = parser.parse_args(sys.argv[2:])
        process_base_args(args)
        userm.maintain_lists()

    def usermaint(self, parser):
        args = parser.parse_args(sys.argv[2:])
        process_base_args(args)
        userm.maintain_users()

    def urlmaint(self, parser):
        args = parser.parse_args(sys.argv[2:])
        process_base_args(args)
        urlm.maintain_urls()

    def twitterrl(self, parser):
        parser.add_argument('-ul', dest='user_limits', action='store_true', default=False,
                            help='Flag to get user rate limits instead of app rate limits')
        args = parser.parse_args(sys.argv[2:])
        process_base_args(args)
        twitter.get_rate_limit_status(args.user_limits)

    def domains(self, parser):
        parser.add_argument('filename', type=argparse.FileType('r'),
                            help='Name of CSV file containing domain information')
        parser.add_argument('-r', dest='reset_domains', action='store_true', default=False,
                            help='Flag to remove existing domains before adding the new domains')
        args = parser.parse_args(sys.argv[2:])
        process_base_args(args)
        with args.filename as file:
            if(args.reset_domains):
                dm.reset_domains(file)
            else:
                dm.update_domains(file)

    def hoturls(self, parser):
        parser.add_argument('-a', dest='age', type=int, default=urla.DEFAULT_MAX_AGE,
                            help=f'Max age of url in hours (def {urla.DEFAULT_MAX_AGE}).')
        parser.add_argument('-da', dest='days_ago', type=int, default=urla.DEFAULT_DAYS_AGO,
                            help=f'Process urls starting x days ago (def {urla.DEFAULT_DAYS_AGO}).')
        parser.add_argument('-ha', dest='hours_ago', type=int, default=urla.DEFAULT_HOURS_AGO,
                            help=f'Process urls starting x hours ago (def {urla.DEFAULT_HOURS_AGO}).')
        parser.add_argument('-mr', dest='max_results', type=int, default=urla.DEFAULT_MAX_RESULTS,
                            help=f'Maximum number of urls/clusters to return (def {urla.DEFAULT_MAX_RESULTS}).')
        parser.add_argument('-c', dest='cluster', default=False, action='store_true',
                            help='Switch to turn on grouping similar urls')
        args = parser.parse_args(sys.argv[2:])
        process_base_args(args)
        urla.dump_hot_list(args)


    def hoturlservice(self, parser):
        args = parser.parse_args(sys.argv[2:])
        process_base_args(args)
        urla.hot_list_service()


def main():
    sh = logging.StreamHandler()
    #lf = logging.Formatter('%(asctime)s:%(levelname)s:%(name)s.%(funcName)s: %(message)s')
    lf = logging.Formatter('%(asctime)s: %(message)s')
    sh.setFormatter(lf)
    # Set our custom handler as the default for the root logger, if a 3rd party module does not play nice and already
    # sets a handler this may need to be modified to be a little smarter
    logging.getLogger().addHandler(sh)
    Cli()


if __name__ == '__main__':
    main()
