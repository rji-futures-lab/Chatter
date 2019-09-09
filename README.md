# Chatter

Twitter monitoring, aggregation and trending for local news.

## Bootstrapping a local dev instance

Install dependencies:

```sh
install.sh
```

Create database:

```sh
createdb {your database name}
```

And set it up:

```sh
psql --dbname={your database name} --file=database/schema.sql
```

Create a copy of the config file for your local development instance settings:

```sh
cp chatter/config/config.yaml chatter/config/local_config.yaml
```

Open `chatter/config/local_config.yaml` and fill in all the necessary configurations.

You'll need to credentials for Twitter's API. If you haven't already [apply](https://developer.twitter.com/en/apply-for-access) for a Twitter developer account, then create an app on that account called Chatter.

You'll also need an API token for OpenCalais. To get one, [register](https://login.thomsonreuters.com/iamui/UI/createUser?app_id=Bold&realm=Bold&lang=en) for Open PermID/Open Calais. Then log into your account to display your API token.

We can test our new instance by checking to see what our current Twitter rate limits are:

```sh
chatter twitterrl -co local_config.yaml
```

The output should look something like this:

```sh
2019-09-09 11:50:31,130: Successfully loaded Chatter configuration from /Users/gordo/Devel/Chatter/chatter/config
('/lists/list', {'limit': 15, 'remaining': 15, 'reset': 1568048731})
('/lists/memberships', {'limit': 75, 'remaining': 75, 'reset': 1568048731})
('/lists/subscribers/show', {'limit': 15, 'remaining': 15, 'reset': 1568048731})
('/lists/members', {'limit': 75, 'remaining': 75, 'reset': 1568048731})
('/lists/subscriptions', {'limit': 15, 'remaining': 15, 'reset': 1568048731})
('/lists/show', {'limit': 75, 'remaining': 75, 'reset': 1568048731})
('/lists/ownerships', {'limit': 15, 'remaining': 15, 'reset': 1568048731})
('/lists/subscribers', {'limit': 15, 'remaining': 15, 'reset': 1568048731})
('/lists/members/show', {'limit': 15, 'remaining': 15, 'reset': 1568048731})
('/lists/statuses', {'limit': 900, 'remaining': 900, 'reset': 1568048731})
('/search/tweets', {'limit': 450, 'remaining': 450, 'reset': 1568048731})
```

