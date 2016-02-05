from flask import Flask, Response, request
from flask_restful import Resource, Api, reqparse
from bson import json_util, CodecOptions, SON
from pymongo import MongoClient, DESCENDING
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

        #Register a new user
        if subcommand == 'register':
            name = text[1]
            this_player = players.find_one({'name': name})
            if(this_player):
                return this_player['name']+ ' already exists.'
            else:
                rating = Rating()
                player = {'name': name, 'mu': rating.mu, 'sigma': rating.sigma, 'score': floor(rating.mu, rating.sigma)}
                players.insert_one(player)
                # return name + ' was created!'
                requests.request(args['response_url'], data=name + ' was created!')
        elif subcommand == 'delete':
            names = text[1:]
            deleted = []
            for name in names:
                result = players.delete_one({'name': name})
                if result > 0:
                    deleted.append(name)
            if(len(deleted) == 0):
                return "Couldn't find the player(s) you entered."
            deleted = ','.join(deleted)
            return "Kaboom. No more "+deleted+'.'
        elif subcommand == 'scores':
            return_scores = []
            scores = players.find().sort('score', DESCENDING)
            headers = ['Name','Score','Mu','Sigma']
            for score in scores:
                return_score = [
                    score['name'],
                    score['score'],
                    score['mu'],
                    score['sigma']
                ]
                return_scores.append(return_score)
            return Response('```\n'+tabulate(return_scores, headers=headers, tablefmt='fancy_grid')+'\n```\n', mimetype='text/plain')
        elif subcommand == 'games':
            return Response('```\n'+tabulate(games.find(), headers='keys', tablefmt='fancy_grid')+'\n```\n', mimetype='text/plain')
        elif subcommand == 'record':
            player1 = text[1]
            operator = text[2]
            player2 = text[3]

            if operator != '>' and operator != '<':
                return "Sorry, who won? Should be like 'player1' > 'player2'."
            elif operator == '>':
                winner_name = player1
                loser_name = player2
            else:
                winner_name = player2
                loser_name = player1

            if winner_name and loser_name:
                winner = players.find_one({'name': winner_name})
                loser = players.find_one({'name': loser_name})
                if winner and loser:
                    winner_rating = Rating(winner['mu'], winner['sigma'])
                    loser_rating = Rating(loser['mu'], loser['sigma'])
                    winner_rating, loser_rating = rate_1vs1(winner_rating, loser_rating)

                    new_winner = {'name': winner['name'],
                                    'mu': winner_rating.mu,
                                    'sigma': winner_rating.sigma,
                                    'score': floor(winner_rating.mu, winner_rating.sigma)
                                }
                    players.replace_one({'name': winner['name']}, new_winner)

                    new_loser = {'name': loser['name'],
                                    'mu': loser_rating.mu,
                                    'sigma': loser_rating.sigma,
                                    'score': floor(loser_rating.mu, loser_rating.sigma)
                                }
                    players.replace_one({'name': loser['name']}, new_loser)

                    game = {'winner': winner['name'],
                                'loser': loser['name'],
                                'date': datetime.datetime.utcnow()
                           }
                    games.insert_one(game)
                    return "Mmmmm. Games. Feed me more games!"
                else:
                    return "Couldn't find one or more players you put in..."
            else:
                return "Please pass in valid player names"

api.add_resource(Root, '/')

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
