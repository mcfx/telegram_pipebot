import threading, traceback

import telebot
from telebot import apihelper
from telebot import types

from pyrogram import Client, Filters

import config

bot = telebot.AsyncTeleBot(config.bot_token)
print('bot init ok')

app = Client(config.profile_name, config.api_id, config.api_hash)
app.start()
print('client init ok')

bot_conds = {}
bot_replys = {}

banned_system_bots = ['spambot']

def is_bot(username):
	if username.lower() in banned_system_bots:
		return False
	if username[-3:].lower() != 'bot':
		return False
	u = app.get_users(username)
	return u.is_bot

@app.on_message(Filters.text & Filters.private)
def process_message(client, message):
	username = message.from_user.username
	if username in bot_conds:
		co = bot_conds[username]
		co.acquire()
		bot_replys[username] = message.text
		co.notify()
		co.release()

def get_single_reply(username, command):
	bot_conds[username].acquire()
	app.send_message(username, command)
	if not bot_conds[username].wait(3):
		bot_conds[username].release()
		return False
	res = bot_replys[username]
	bot_conds[username].release()
	return res

def get_reply(username, command):
	if not is_bot(username): return False
	if username not in bot_conds:
		bot_conds[username] = threading.Condition()
		bot_replys[username] = ''
		get_single_reply(username, '/start')
	return get_single_reply(username, command)

help_text = '''This is a bot to connect other bots as pipes.

Basic usage: Botn Bot(n-1) ... Bot2 Bot1 message
Example: @pipe2bot @kongebot @bullshitsaysbot test
You can also use /pipe command.

In addition, you can add parameters to each bot call.
There are currently 3 parameters:

[x]@bot - The x-th result of the inline query will be used. If x is not given, the first(0-th) result will be used.
[pm]@bot - I will pm the bot and send the message. The first reply is used as the result.
/command@bot - I will PM the bot and send the command. The first reply is used as the result.

Examples:
@pipe2bot @kongebot [1]@xiaobbot /ranwen@ranwen_quote_bot
@pipe2bot @kongebot [pm]@bullshitsaysbot /ranwen@ranwen_quote_bot'''

@bot.message_handler(commands=['start', 'help'])
def send_help(message):
	bot.reply_to(message, help_text)

def get_piped_text(s):
	funcs = []
	while s[0] == '@' or s[0] == '/' or s[0] == '[':
		p = s.find(' ')
		if p == -1:
			p = len(s)
		assert p != 1
		funcs.append(s[:p])
		if p == len(s):
			s = ''
			break
		s = s[p + 1:]
	print(funcs, s)
	res = 'message'
	for i in reversed(funcs):
		print(i)
		res = '%s(%s)' % (i, res)
		if i[0] == '@':
			s = app.get_inline_bot_results(i[1:], s)
			s = s['results'][0]['send_message']['message']
		elif i[0] == '/':
			assert '@' in i
			a, b = i.split('@', 1)
			s = get_reply(b, a + ' ' + s)
			assert s
		elif i[0] == '[':
			assert ']' in i
			a, b = i[1:].split(']', 1)
			assert b[0] == '@'
			if a.lower() == 'pm':
				s = get_reply(b[1:], s)
				assert s
			else:
				a = int(a)
				s = app.get_inline_bot_results(b[1:], s)
				s = s['results'][a]['send_message']['message']
	print(s)
	return res, s

@bot.message_handler(commands=['pipe'])
def send_pipe(message):
	try:
		msg = message.text.split(' ', 1)[1]
		bot.reply_to(message, get_piped_text(msg)[1])
	except Exception as e:
		#print(e)
		traceback.print_exc()

@bot.inline_handler(lambda query: query.query != "")
def query_text(inline_query):
	qtext = inline_query.query.strip()
	if qtext == "":
		return
	try:
		res, s = get_piped_text(qtext)
		r = types.InlineQueryResultArticle('1', res, types.InputTextMessageContent(s))
		bot.answer_inline_query(inline_query.id, [r], cache_time=1)
	except Exception as e:
		#print(e)
		traceback.print_exc()

bot.polling(True)
