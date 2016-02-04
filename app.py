from flask import Flask, Response, request
from flask_restful import Resource, Api, reqparse
from bson import json_util, CodecOptions, SON
from pymongo import MongoClient
from trueskill import Rating, rate_1vs1, TrueSkill
from tabulate import tabulate
import datetime, os, requests

app = Flask(__name__)
api = Api(app)
parser = reqparse.RequestParser()
parser.add_argument('token')
parser.add_argument('text')
parser.add_argument('response_url')


env = TrueSkill(draw_probability = 0.0, backend = 'mpmath', tau = .41666666667)
env.make_as_global()

def floor(mu, sigma):
    floor_factor = 2.0
    return mu - floor_factor * sigma

class Root(Resource):
    def post(self):
        args = parser.parse_args()
        print request.data
        print request.headers
        print args['text']
        print args['response_url']
        text = args['text'].lower().split()
        subcommand = text[0]
        print "Subcommand: " + subcommand
        callback_url = args['response_url']

        #Register a new user
        if subcommand == 'register':
            name = text[1]
            print "Name to register: " + name
            this_player = players.find_one({'name': name})
            if(this_player):
                requests.post(callback_url, data={'info': this_player['name']+' is already registered!'})
                # return Response(json_util.dumps(this_player), mimetype='application/json')
            else:
                rating = Rating()
                player = {'name': name, 'mu': rating.mu, 'sigma': rating.sigma, 'score': floor(rating.mu, rating.sigma)}
                players.insert_one(player)
                # requests.post(callback_url, data={'info': this_player['name']+' is already registered!'})
                return Response(json_util.dumps(player), mimetype='application/json')
    def get(self):
        return Response(json_util.dumps(players.find()), mimetype='application/json')
        # return Response(tabulate(players.find(), headers='keys'), mimetype='text/plain')

class Games(Resource):
    def post(self):
        args = parser.parse_args()
        winner_name = args['winner']
        loser_name = args['loser']
        if winner_name and loser_name:
            winner = players.find_one({'name': winner_name})
            loser = players.find_one({'name': loser_name})
            if winner and loser:
                winner_rating = Rating(winner['mu'], winner['sigma'])
                loser_rating = Rating(loser['mu'], loser['sigma'])
                winner_rating, loser_rating = rate_1vs1(winner_rating, loser_rating)

                new_winner = {'name': winner['name'], 'mu': winner_rating.mu, 'sigma': winner_rating.sigma, 'score': floor(winner_rating.mu, winner_rating.sigma)}
                players.replace_one({'name': winner['name']}, new_winner)
                new_loser = {'name': loser['name'], 'mu': loser_rating.mu, 'sigma': loser_rating.sigma, 'score': floor(loser_rating.mu, loser_rating.sigma)}
                players.replace_one({'name': loser['name']}, new_loser)

                game = {'winner': winner['name'], 'loser': loser['name'], 'date': datetime.datetime.utcnow()}
                games.insert_one(game)
                return Response(json_util.dumps(game), mimetype='application/json')
            else:
                return "Players Not Found", 400
        else:
            return "Please pass in player names", 400
    def get(self):
        return Response(json_util.dumps(players.find()), mimetype='application/json')


api.add_resource(Root, '/')
# api.add_resource(Games, '/games')

if __name__ == '__main__':
    opts = CodecOptions(document_class=SON)
    mongo = MongoClient(os.environ['MONGO'])
    db = mongo[os.environ['DATABASE']]
    games = db.games.with_options(codec_options=opts)
    players = db.players.with_options(codec_options=opts)
    isDebug = True
    port = 5000

    if 'ENV' in os.environ:
        isDebug = True if (os.environ['ENV'].lower() != 'prod') else False
    if 'PORT' in os.environ:
        port=int(os.environ['PORT'])
    app.run(host='0.0.0.0', port=port, debug=isDebug)
