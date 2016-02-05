# pong-master
A RESTful TrueSkill game tracker for WayBlazer pong

Hosted on Heroku.

# Local Development

## Running It
To test the thing locally:

```
export MONGO=mongodb://localhost:27017
export DATABASE=pongbot

python app.py
```

The `PORT` will be set to 5000 automatically in dev mode.

## Sending Commands

This service isnt truely RESTful due to how Slack slash commands work. 

- Everything is an http `POST` to the root of the service (`http://myserver.com/`).
- `Content-Type` should be `application/x-www-form-urlencoded`
- Post body should be form data in k/v format. Only one parameter is required, currently: `text`. Text is everything after the slash command in slack. For example:

User sends `/pong add kevin`

Body:
```
text=add kevin
```
