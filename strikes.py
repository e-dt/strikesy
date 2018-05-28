import discord
from discord.ext import commands
import asyncio
import datetime
import redis
from math import floor

strikesdb = redis.StrictRedis(host = 'localhost', port = 6379, db = 0)
punishments = redis.StrictRedis(host = 'localhost', port = 6379, db = 1)

bot = commands.Bot(command_prefix='?')
ignorejail = None
####################################################
# #THIS CODE IS WHOLLY STOLEN FROM ROWBOAT. THANKS #
####################################################
UNITS = {
    's': lambda v: v,
    'm': lambda v: v * 60,
    'h': lambda v: v * 60 * 60,
    'd': lambda v: v * 60 * 60 * 24,
    'w': lambda v: v * 60 * 60 * 24 * 7,
}


def parse_duration(raw, source=None, negative=False, safe=False):
    if not raw:
        if safe:
            return None

    value = 0
    digits = ''

    for char in raw:
        if char.isdigit():
            digits += char
            continue

        if char not in UNITS or not digits:
            if safe:
                return None
            raise CommandError('Invalid duration')

        value += UNITS[char](int(digits))
        digits = ''

    if negative:
        value = value * -1

    return datetime.timedelta(seconds=value + 1)
#########################################
# NO LONGER STOLEN FROM ROWBOAT. THANKS #
#########################################
async def check_punishments(person):
    newperson = await get_member(person)
    if strikesdb.get(person) == b'3':
        await dayjail(newperson, 1)
    elif strikesdb.get(person) == b'4':
        await dayjail(newperson, 2)
    elif strikesdb.get(person) in b'5':
        await permjail(newperson)
    elif strikesdb.get(person) == b'6':
        await weekban(newperson)
    elif strikesdb.get(person) == b'7':
        await permban(newperson)


def add_punishment(ptype, person, timedelta):
    punishments.zadd(ptype, floor((datetime.datetime.utcnow() + timedelta).timestamp()), person.id)

async def get_member(person):
    try:
        return server.get_member(person)
    except:
        return discord.utils.get([i.user for i in server.bans()], id = person) 

async def dayjail(person, days):
    await reports.send(person.name+ " is jailed for " + str(days) + " day(s), due to gaining too many strikes.")
    global ignorejail
    ignorejail = person.id
    try:
        await person.remove_roles(jail)
    except:
        pass
    await person.add_roles(jail)
    add_punishment("unjail", person, datetime.timedelta(days = 1))

async def permjail(person):
    await reports.send(person.name+ " is jailed, due to gaining too many strikes. Write an essay to get out.")
    await person.add_roles(jail)
    
async def unjail(person):
    await reports.send(person.name+ " is unjailed!")
    await person.remove_roles(jail)

async def weekban(person):
    await reports.send(person.name+ " is banned for a week, due to gaining too many strikes.")
    await server.ban(person)
    add_punishment("unban", person, datetime.timedelta(weeks = 1))

async def unban(person):
    await reports.send(person.name+ " is unbanned!")
    await server.unban(person)

async def permban(person):
    await reports.send(person.name+ " is permanently banned, due to gaining too many strikes.")
    await server.ban(person)

async def strike_decay(person):
    await reports.send(person.name+ " has lost a strike due to strike decay!")
    if strikesdb.get(person.id) != b'0':
        strikesdb.decr(person.id)
        add_punishment("strike_decay", person, datetime.timedelta(weeks = 1))
    

def check_action(actionbytes):
    if actionbytes == b'unpunish':
        return unpunish
    elif actionbytes == b'unjail':
        return unjail
    elif actionbytes == b'strike_decay':
        return strike_decay
    elif actionbytes == b'unban':
        return unban

@bot.command(name = "strike")
async def command_strike(ctx, member: discord.Member):
    if authorised not in ctx.author.roles or ctx.author.top_role < member.top_role:
        return
    await ctx.send('striking...')
    await strike(member)
    
async def strike(member):
    if member.id == 449792608516964352:
        return
    strikesdb.incr(member.id)
    add_punishment("strike_decay", member, datetime.timedelta(weeks = 1))
    await check_punishments(member.id)
@bot.command(name = "unstrike")
async def unstrike(ctx, member: discord.Member):
    if authorised not in ctx.author.roles or ctx.author.top_role < member.top_role:
        return
    await ctx.send('destriking...')
    if strikesdb.get(member.id) != b'0':
        strikesdb.decr(member.id)

@bot.command(name = "strikes")
async def strikes(ctx, member: discord.Member=None):
    if member == None:
        member = ctx.author
    await ctx.send(strikesdb.get(member.id))
@bot.command(name = "jail")
async def jail(ctx, member: discord.Member, duration: str, reason = ""):
    global ignorejail
    if authorised not in ctx.author.roles or ctx.author.top_role < member.top_role:
        return
    await member.add_roles(jail)
    durat = parse_duration(duration)
    if durat != None:
        add_punishment("unjail", member, parse_duration(duration))
        ignorejail = member.id
        await reports.send(member.name + " is jailed for " + duration + " because: " + reason)
        await strike(member)

async def unpunish_loop():
    while 1:
        for i in punishments.keys():
            action = check_action(i)
            timey = floor(datetime.datetime.utcnow().timestamp())
            unpunish_set = punishments.zrangebyscore(i, min = 0, max = timey)
            punishments.zremrangebyscore(i, min = 0, max = timey)
            for i in unpunish_set:
                await action(await get_member(int(i)))
        await asyncio.sleep(1)
@bot.event
async def on_ready():
    print('We have logged in as {0.user}'.format(bot))
    global server
    global reports
    global jail
    #global solitary
    global authorised
    server = bot.get_guild(231084230808043522)
    #server = bot.get_guild(330518039961403393)
    reports = bot.get_channel(267150859605901314)
    #reports = bot.get_channel(450122812435202048)
    jail = discord.utils.get(server.roles, id=285615006442192896)
    #jail = discord.utils.get(server.roles, id =450377477949227018)
    #solitary = discord.utils.get(server.roles, id=394608676276535296)
    authorised = discord.utils.get(server.roles, id=431368741197053953)
    #authorised = discord.utils.get(server.roles, id = 450384394667163650)
    asyncio.ensure_future(unpunish_loop())

@bot.event
async def on_message(message):
    await bot.process_commands(message)

@bot.event
async def on_member_update(before, after):
    if jail in after.roles and jail not in before.roles:
        if ignorejail == after.id:
            return
        await reports.send(after.name+ " is striked for being jailed.")
        strikesdb.incr(after.id)
        add_punishment("strike_decay", after, datetime.timedelta(weeks = 1))
        await check_punishments(after.id)
@bot.event
async def on_command_error(ctx, error):
    await ctx.send("Something went wrong. Please try again, doing it the RIGHT way this time. The problem: " + str(error))


bot.run




