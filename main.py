
import os
import discord
from discord.ext import commands
import sqlite3
import datetime
from aiohttp import web
from threading import Thread

# --- Setup Discord Bot ---
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="r!", intents=intents)
TOKEN = os.environ["TOKEN"]  # Set this environment variable in your hosting dashboard

# --- Database Setup ---
DATABASE = "ryo.db"
VOTE_URL = "https://example.com"  # Replace with your actual Top.gg vote link

conn = sqlite3.connect(DATABASE)
c = conn.cursor()
c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        balance INTEGER DEFAULT 0,
        last_daily TEXT,
        last_vote TEXT
    )
""")
conn.commit()

# --- Helper Functions ---
def get_balance(user_id):
    c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    return row[0] if row else 0

def update_balance(user_id, amount):
    if get_balance(user_id) == 0:
        c.execute("INSERT OR IGNORE INTO users (user_id, balance) VALUES (?, ?)", (user_id, 0))
    c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()

def set_last_vote(user_id, timestamp):
    c.execute("INSERT OR IGNORE INTO users (user_id, last_vote) VALUES (?, ?)", (user_id, timestamp))
    c.execute("UPDATE users SET last_vote = ? WHERE user_id = ?", (timestamp, user_id))
    conn.commit()

def get_last_vote(user_id):
    c.execute("SELECT last_vote FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    return datetime.datetime.fromisoformat(row[0]) if row and row[0] else None

# --- Commands ---
@bot.event
async def on_ready():
    print(f"Bot is ready as {bot.user}")

@bot.command()
async def ryobal(ctx):
    balance = get_balance(ctx.author.id)
    await ctx.send(f"💰 **{ctx.author.name}**, you have **{balance} Ryo**.")

@bot.command()
async def ryovote(ctx):
    last_vote = get_last_vote(ctx.author.id)
    now = datetime.datetime.utcnow()
    cooldown = datetime.timedelta(hours=12)
    time_left = "Ready to vote!"

    if last_vote and (now - last_vote) < cooldown:
        remaining = cooldown - (now - last_vote)
        time_left = f"{remaining.seconds // 3600}h {(remaining.seconds // 60) % 60}m"

    embed = discord.Embed(
        title="Ryo Economy - Vote",
        description=f"[Claim a free Vote Pack which contains 2000 Ryo.]({VOTE_URL})\n\n"
                    f"[TopGG Vote: {time_left}]({VOTE_URL})",
        color=discord.Color.blue()
    )
    await ctx.send(embed=embed)

@bot.event
async def on_message(message):
    await bot.process_commands(message)

# --- Webhook Handler for Top.gg Votes ---
app = web.Application()

async def handle_vote(request):
    data = await request.json()
    user_id = int(data["user"])
    user = await bot.fetch_user(user_id)

    old_bal = get_balance(user_id)
    update_balance(user_id, 2000)
    new_bal = old_bal + 2000
    set_last_vote(user_id, datetime.datetime.utcnow().isoformat())

    try:
        await user.send(
            "**Thank You For Voting On Top.GG!**\n\n"
            f"Purse:\n{old_bal} + 2000 Ryo\n"
            f"Total: {new_bal}"
        )
    except:
        print(f"Couldn't DM {user}")

    return web.Response(text="OK")

app.router.add_post("/vote", handle_vote)

# --- Run aiohttp Server in Background ---
def run_web():
    web.run_app(app, port=8080)

Thread(target=run_web).start()

# --- Run Bot ---
bot.run(TOKEN)
