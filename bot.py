import os
import discord
import random
from dotenv import load_dotenv
from statistics import mode, StatisticsError
from discord.ext import commands

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

bot = commands.Bot(command_prefix = "-")

list_of_players = []
role_settings = {
	"weerwolf": 0,
	"ziener": 1,
	"jager": 0,
	"cupido": 0,
	"heks": 0,
	"dief": 0
}
starting = False

@bot.event
async def on_ready():
	print(f'{bot.user} has connected!')

@bot.event
async def on_command_error(ctx, error):
	if isinstance(error, commands.CommandNotFound):
		await ctx.send("Dat is geen geldig command.")

class Player(discord.Member):
	def __init__(self, user, num, role, vote):
		self.num = num
		self.role = role
		self.user = user
		self.vote = vote
	def __eq__(self, other):
		return self.user == other.user and self.num == other.num

@bot.command(name="setroles")
async def setroles(ctx, role, num:int):
	if role in role_settings:
		role_settings[role] = num
		nice_string= "Het deck ziet er nu zo uit:"
		for x in role_settings:
			nice_string = nice_string + "\n" + x + ": " + str(role_settings[x])
		await ctx.send(nice_string)
	else:
		raise commands.CommandError

@setroles.error
async def setroles_error(ctx, error):
	if isinstance(error, commands.CommandError):
		await ctx.send("De syntax voor dit command is -setroles [rol] [aantal]. Gebruik -deck voor een lijst met rollen.")
	else:
		raise error

@bot.command(name="players")
async def players(ctx):
	if starting == False:
		await ctx.send("Dit command werkt alleen tijdens het opstarten van een spel.")
	nice_string = "Spelers: "
	for x in list_of_players:
		nice_string = nice_string + x.name + ", "
	await ctx.send(nice_string)


@bot.command(name="deck")
async def deck(ctx):
	nice_string= "Het deck ziet er zo uit:"
	for x in role_settings:
		nice_string = nice_string + "\n" + x + ": " + str(role_settings[x])
	await ctx.send(nice_string)

@bot.command(name="play")
async def play(ctx):
	global starting
	if starting == True:
		return
	await ctx.send("Dit is een test. Alle spelers moeten -join typen in een tekstkanaal.")
	await ctx.send("Er zitten " + str(role_settings["weerwolf"]) + " weerwolven in het spel. Gebruik -setroles om dit te veranderen.")
	starting = True

@bot.command(name="join")
async def join(ctx):
	if starting == True:
		list_of_players.append(ctx.author)
		await ctx.send("Je bent gejoind!")
	else:
		await ctx.send("Er is nog geen spel bezig, of het spel is al begonnen.")

@bot.command(name="send")
async def send(ctx, message):
	global playing
	if playing == True:
		for x in find_players_with_role(players_alive, "weerwolf"):
			if ctx.author.id != x.user.id:
				await x.user.send(ctx.author.name + ": " + message)

@bot.command(name="start")
async def start(ctx):
	global starting
	if starting == False:
		await ctx.send("Gebruik eerst -play om een game te starten.")
		return
	starting = False
	await ctx.send("We gaan beginnen!")
	roles_with_freq = dict(role_settings)
	burger_amt = len(list_of_players)
	for x in role_settings:
		burger_amt = burger_amt - role_settings[x]
	if burger_amt < 0:
		await ctx.send("Er zijn niet genoeg spelers!")
		return
	roles_with_freq["burger"] = burger_amt
	#De rollen worden verdeeld
	available_nums = []
	players = []
	for i in range(1, len(list_of_players) + 1):
		available_nums.append(i)
	for x in roles_with_freq:
		chosen_players = random.sample(list_of_players, roles_with_freq[x])
		for player in chosen_players:
			list_of_players.remove(player)
			chosen_num = random.choice(available_nums)
			available_nums.remove(chosen_num)
			added_player = Player(player, chosen_num, x, 0)
			players.append(added_player)
	players.sort(key = get_num)
	#Iedere speler krijgt een dm met zijn/haar rol
	await ctx.send("De rollen zijn verdeeld.")
	for x in players:
		await x.user.send("Je bent een " + x.role + "!")
	await ctx.send(make_list_of_players(players))
	#Het spel begint
	await play_weerwolven(players, ctx.channel)

async def play_weerwolven(roles, channel):
	global playing
	playing = True
	nights_amt = 0
	players_alive = list(roles)
	while playing == True:
		nights_amt = nights_amt + 1
		await channel.send("Het is nacht " + str(nights_amt) + " in Wakkerdam. Iedereen gaat slapen. Tip: mute je microfoon.")
		dead_this_night = []
		#Code voor de ziener
		#
		if checkrole(players_alive, 'ziener') == True:
			for x in find_players_with_role(players_alive, "ziener"):
				await channel.send("De ziener wordt wakker.")
				if nights_amt == 1:
					await x.user.send("De ziener kan elke nacht de rol van een speler zien.\n" + make_list_of_players(players_alive))
				valid_voter = [x.user]
				response = await bot.wait_for('message', check = VoteCheck(valid_voter))
				await x.user.send(find_player_by_num(players_alive, int(response.content)).role)
				await channel.send("De ziener gaat weer slapen.")
		#De weerwolven
		#
		if checkrole(players_alive, 'weerwolf') == True:
			await channel.send("De weerwolven worden wakker.")
			werewolves = []
			for x in find_players_with_role(players_alive, "weerwolf"):
				await x.user.send("De weerwolven kunnen nu iemand doden. \n" + make_list_of_players(players_alive))
				werewolves.append(x.user)
			for x in find_players_with_role(players_alive, "weerwolf"):
				await x.user.send("De weerwolven zijn: \n" + make_list_of_players(find_players_with_role(players_alive, "weerwolf")) + "\nChat door -send te sturen gevolgd door je bericht! Stem door alleen het nummer van je doelwit in te typen.")
			dead = await killing(players_alive, werewolves)
			for x in find_players_with_role(players_alive, "weerwolf"):
				x.vote = 0
			dead_this_night.append(dead)
			await channel.send("De weerwolven gaan weer slapen")
		#De heks
		#
		if checkrole(players_alive, 'heks') == True:
			await channel.send("De heks wordt wakker (werkt nog niet tot na de rework!)")

		#De dag
		#
		await channel.send("Het is dag in Wakkerdam. Iedereen wordt wakker, behalve: \n" + make_list_of_players(dead_this_night))
		players_alive = await kill(players_alive, dead_this_night, channel)
		await channel.send("De volgende spelers zijn nog in leven. Overleg in de voicechat en DM je stem naar de bot. Wanneer iedereen heeft gestemd wordt degene met de meeste stemmen opgehangen. Let op: bij gelijkspel wordt niemand gelyncht! \n" + make_list_of_players(players_alive))
		result = await town_vote(players_alive)
		dead = find_player_by_num(players_alive, result)
		results = ""
		for x in players_alive:
			results = results + x.user.name + ": " + str(x.vote) + "\n"
		await channel.send("Resultaten van de stemming: \n" + results)
		if dead is None:
			await channel.send("Het was gelijkspel, daarom is niemand gelyncht.")
		else:
			await channel.send("Het dorp heeft besloten " + dead.user.name + " te lynchen.")
			dead_list = [dead]
			players_alive = await kill(players_alive, dead_list , channel)
			await channel.send("De nog levende spelers zijn: \n" + make_list_of_players(players_alive))
			dead = None
		#De win condition!
		playing = check_win(players_alive)
	if find_players_with_role(players_alive, "weerwolf") == []:
		await channel.send("Het dorp heeft gewonnen!")
	else:
		await channel.send("De weerwolven hebben gewonnen!")
	players_alive = []

def get_num(p):
	return p.num

def find_players_with_role(roles, r):
	results = []
	for x in roles:
		if x.role == r:
			results.append(x)
	return results

def find_player_by_num(roles, num):
	for x in roles:
		if x.num == num:
			return x

def make_list_of_players(roles):
	nice_string = ""
	for x in roles:
		nice_string = nice_string + str(x.num) + ": " + x.user.name + "\n"
	return nice_string

def most_common(l):
	try:
		return mode(l)
	except StatisticsError as e:
		if 'no unique mode' in e.args[0]:
			return None
		else:
			raise

async def killing(roles, killers):
	killing = True
	while killing == True:
		msg = await bot.wait_for("message", check = VoteCheck(killers))
		vote = int(msg.content)
		if find_player_by_num(roles, vote) is not None:
			for x in find_players_with_role(roles, "weerwolf"):
				if msg.author.id == x.user.id:
					x.vote = vote
					break
			werewolf_votes = []
			for x in find_players_with_role(roles, "weerwolf"):
				if msg.author.id != x.user.id:
					await x.user.send(msg.author.name + " heeft zijn/haar stem veranderd naar " + str(vote))
				else:
					await x.user.send("Je stem is veranderd")
				werewolf_votes.append(x.vote)
			if werewolf_votes.count(werewolf_votes[0]) == len(werewolf_votes):
				target = find_player_by_num(roles, werewolf_votes[0])
				for x in find_players_with_role(roles, "weerwolf"):
					await x.user.send(target.user.name + " is het doelwit van de weerwolven vannacht.")
				return target
		else:
			msg.author.send("Dat is geen geldige stem.")

async def town_vote(roles):
	voters = []
	for x in roles:
		voters.append(x.user)
	voting = True
	while voting == True:
		msg = await bot.wait_for("message", check = VoteCheck(voters))
		vote = int(msg.content)
		if find_player_by_num(roles, vote) is not None:
			for x in roles:
				if msg.author.id == x.user.id:
					x.vote = vote
					#Hier moet eigenlijk een break!
			votes = []
			for x in roles:
				if msg.author.id == x.user.id:
					await x.user.send("Je stem is veranderd")
				votes.append(x.vote)
			if votes.count(0) == 0:
				return most_common(votes)
		else:
			await msg.author.send("Dat is geen geldige stem.")

async def kill(alive_players, dead_players, channel):
	new = list(alive_players)
	for x in dead_players:
		new.remove(x)
	for x in dead_players:
		if x.role == "jager":
			await channel.send(x.user.name + " was de jager! Diegene mag nu een speler naar keuze doden.")
			await x.user.send("De volgende spelers zijn nog in leven. Stuur een bericht met het nummer van de speler die je wil doodschieten. \n" + make_list_of_players(new))
			valid_voter = [x.user]
			vote = await bot.wait_for("message", check=VoteCheck(valid_voter))
			target = find_player_by_num(alive_players, int(vote.content))
			if target is not None:
				list_target = [target]
				await channel.send("De jager heeft besloten " + target.user.name + " dood te schieten.")
				new = await kill(new, list_target, channel)
			else:
				x.user.send("Dat is geen geldige stem.")
		else:
			await channel.send(x.user.name + " was een " + x.role + "!")
	return new

def VoteCheck(allowed_users):
	def inner_check(m):
		if m.author not in allowed_users:
			return False
		try: 
			int(m.content) 
			return True 
		except ValueError: 
			return False
	return inner_check


def check_win(roles):
	c = find_players_with_role(roles, "weerwolf")
	if c == [] or len(c) == len(roles):
		return False
	else:
		return True

def checkrole(alive_players, role):
	if find_players_with_role(alive_players, role) is not None:
		return True
	else:
		return False


bot.run(TOKEN)