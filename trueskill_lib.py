from trueskill import Rating, rate_1vs1, TrueSkill

#defaults...if you see adjusted numbers, it means we wanted to override them
#mu = 25  default skill level...different number means that players cluster at a skill level NOT halfway between the worst and best player
#sigma = 8.333333333333333  default uncertainty of that skill level.  higher number implies more even skill distribution, lower implies players cluster at mu
#beta = 4.16666666666667  higher = game is more luck based...beta difference between players = 80% chance to win
#tau = 0.083333333333333  higher = more expected actual player skill change over time
env = TrueSkill(draw_probability = 0.0, backend = 'mpmath', tau = .41666666667)
env.make_as_global()

#factor for reducing floor
floor_factor = 2.0

with open("matches.txt", "r") as file:
    txt = file.read().replace('\n', ' ').lower()

listItems = txt.split()

#games are in reverse order
listItems.reverse()

players = {}

for i in range(0, len(listItems)):

    #skip DEF
    if i % 3 == 1:
        continue

    name = listItems[i]

    if not name in players:
        players[name] = Rating()

    if i % 3 == 2:
        winner = players[listItems[i]]
        loser = players[listItems[i - 2]]

        newWinner, newLoser = rate_1vs1(winner, loser)

        players[listItems[i]] = newWinner
        players[listItems[i - 2]] = newLoser


finals = []

for key in players.keys():

    player = {}
    player['name'] = key
    player['mu'] = players[key].mu
    player['sigma'] = players[key].sigma
    player['floor'] = max(players[key].mu - (players[key].sigma * floor_factor), 0)

    finals.append(player)


finals = sorted(finals, key=lambda player: -player['floor'])

for player in finals:
    print player['name'] + ': ' + str(player['floor']) + ' (' + str(player['mu']) + ', ' + str(player['sigma']) + ')'
