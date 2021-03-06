from flask import Flask, Response, request
from flask_restful import Resource, Api, reqparse
from bson import json_util, CodecOptions, SON
from pymongo import MongoClient, DESCENDING
from trueskill import Rating, rate_1vs1, TrueSkill
from tabulate import tabulate
import datetime, os, requests
import math

app = Flask(__name__)
api = Api(app)
parser = reqparse.RequestParser()
parser.add_argument('token')
parser.add_argument('text')
parser.add_argument('response_url')

#defaults...if you see adjusted numbers, it means we wanted to override them
#mu = 25  default skill level...different number means that players cluster at a skill level NOT halfway between the worst and best player
#sigma = 8.333333333333333  default uncertainty of that skill level.  higher number implies more even skill distribution, lower implies players cluster at mu
#beta = 4.16666666666667  higher = game is more luck based...beta difference between players = 80% chance to win
#tau = 0.083333333333333  higher = more expected actual player skill change over time
env = TrueSkill(draw_probability = 0.0, backend = 'mpmath', tau = .41666666667)
env.make_as_global()

def floor(mu, sigma):
    floor_factor = 2.0
    return mu - floor_factor * sigma

def win_chance(player1, player2):
    deltaMu = player1['mu'] - player2['mu']
    sumSigma = player1['sigma'] ** 2 + player2['sigma'] ** 2
    denominator = math.sqrt( 2 * env.beta ** 2 + sumSigma )
    return env.cdf(deltaMu / denominator)

class Root(Resource):
    def post(self):
        args = parser.parse_args()
        print(request.data)
        print(request.headers)
        print(args['text'])
        print(args['response_url'])
        text = args['text'].lower().split()
        subcommand = text[0]
        print("Subcommand: " + subcommand)

        #Register a new user
        if subcommand == 'add':
            names = text[1:]
            exists = []
            added = []
            for name in names:
                name = name.lower()
                this_player = players.find_one({'name': name})
                if(this_player):
                    exists.append(this_player['name'])
                else:
                    rating = Rating()
                    player = {'name': name, 'mu': rating.mu, 'sigma': rating.sigma, 'score': floor(rating.mu, rating.sigma)}
                    players.insert_one(player)
                    added.append(player['name'])
            return_text = ''
            if(len(added) > 0):
                return_text += 'Added ' + ','.join(added)
            if(len(exists) > 0):
                if len(return_text) > 0:
                    return_text += ' and '
                return_text += ','.join(exists) + " already exist."
            return return_text
        elif subcommand == 'rm':
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
        elif subcommand == 'players':
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
        elif subcommand == 'odds':
            name1 = text[1].lower()
            name2 = text[2].lower()

            if not name1 or not name2:
                return "Please enter 2 player names"

            player1 = players.find_one({'name': name1})
            player2 = players.find_one({'name': name2})

            if not player1 or not player2:
                return "Couldn't find both those names :("

            winChance = win_chance(player1, player2)

            return Response('```\n'+ name1 + "'s chance to beat " + name2 + ":  " + str(winChance) +'\n```\n', mimetype='text/plain')

        elif subcommand == 'record':
            player1 = text[1].lower()
            operator = text[2]
            player2 = text[3].lower()

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
                    return "Congrats, " + winner_name + "!"
                else:
                    return "Couldn't find one or more players you put in..."
            else:
                return "Please pass in valid player names"
        elif subcommand == 'help':
            helptext = '/pong add <player> - add a user\n\
/pong rm <player> - delete a user\n\
/pong record <player1> [> or <] <player2> - record a game\n\
/pong games - list all the games recorded\n\
/pong players - List the players and their scores\n\
/pong odds <player1> <player2> - shows chance that player 1 beats player 2'
            return Response('```\n'+helptext+'\n```\n', mimetype='text/plain')
        else:
            return "Sorry, couldn't understand that."

api.add_resource(Root, '/')

if __name__ == '__main__':
    opts = CodecOptions(document_class=SON)
    mongo = MongoClient(os.environ['MONGODB_URI'])
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
