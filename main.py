import discord
import os
import sys
import asyncio
import aiosqlite
import random
import json
from discord.ext import commands
from datetime import datetime

# Botの設定
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix='!', intents=intents)

bot_start_time = None
DATABASE_FILE = 'bot_economy.db'
SLOT_EMOJIS = ["🍎", "🍊", "🍇", "🍓", "🍌", "🥝", "🍑"]

# データベース初期化
async def init_database():
    async with aiosqlite.connect(DATABASE_FILE) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                money INTEGER DEFAULT 1000,
                inventory TEXT DEFAULT "[]",
                roles TEXT DEFAULT "[]"
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                emoji TEXT NOT NULL,
                name TEXT NOT NULL,
                price INTEGER NOT NULL,
                description TEXT NOT NULL
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS gacha_roles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                rarity TEXT NOT NULL,
                price INTEGER NOT NULL,
                description TEXT NOT NULL
            )
        ''')
        await db.commit()

# ユーザーデータ取得
async def get_user_data(user_id):
    async with aiosqlite.connect(DATABASE_FILE) as db:
        async with db.execute('SELECT money, inventory, roles FROM users WHERE user_id = ?', (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return {"money": row[0], "inventory": json.loads(row[1]), "roles": json.loads(row[2] or "[]")}
            else:
                await db.execute('INSERT INTO users (user_id) VALUES (?)', (user_id,))
                await db.commit()
                return {"money": 1000, "inventory": [], "roles": []}

# ユーザーのお金更新
async def update_user_money(user_id, money):
    async with aiosqlite.connect(DATABASE_FILE) as db:
        await db.execute('UPDATE users SET money = ? WHERE user_id = ?', (money, user_id))
        await db.commit()

# インベントリ追加
async def add_to_inventory(user_id, item):
    user_data = await get_user_data(user_id)
    user_data["inventory"].append(item)
    async with aiosqlite.connect(DATABASE_FILE) as db:
        await db.execute('UPDATE users SET inventory = ? WHERE user_id = ?', 
                        (json.dumps(user_data["inventory"]), user_id))
        await db.commit()

# アイテム一覧取得
async def get_all_items():
    async with aiosqlite.connect(DATABASE_FILE) as db:
        async with db.execute('SELECT id, emoji, name, price, description FROM items') as cursor:
            rows = await cursor.fetchall()
            return [{"id": row[0], "emoji": row[1], "name": row[2], "price": row[3], "description": row[4]} for row in rows]

# アイテム追加・削除・ID取得
async def add_item(emoji, name, price, description):
    async with aiosqlite.connect(DATABASE_FILE) as db:
        await db.execute('INSERT INTO items (emoji, name, price, description) VALUES (?, ?, ?, ?)', 
                        (emoji, name, price, description))
        await db.commit()

async def remove_item(item_id):
    async with aiosqlite.connect(DATABASE_FILE) as db:
        await db.execute('DELETE FROM items WHERE id = ?', (item_id,))
        await db.commit()

async def get_item_by_id(item_id):
    async with aiosqlite.connect(DATABASE_FILE) as db:
        async with db.execute('SELECT id, emoji, name, price, description FROM items WHERE id = ?', (item_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return {"id": row[0], "emoji": row[1], "name": row[2], "price": row[3], "description": row[4]}
            return None

# ユーザーロール管理
async def add_user_role(user_id, role_data):
    user_data = await get_user_data(user_id)
    user_data["roles"].append(role_data)
    async with aiosqlite.connect(DATABASE_FILE) as db:
        await db.execute('UPDATE users SET roles = ? WHERE user_id = ?', 
                        (json.dumps(user_data["roles"]), user_id))
        await db.commit()

# ガチャロール管理
async def get_all_gacha_roles():
    async with aiosqlite.connect(DATABASE_FILE) as db:
        async with db.execute('SELECT id, role_id, name, rarity, price, description FROM gacha_roles') as cursor:
            rows = await cursor.fetchall()
            return [{"id": row[0], "role_id": row[1], "name": row[2], "rarity": row[3], "price": row[4], "description": row[5]} for row in rows]

async def get_roles_by_rarity(rarity):
    async with aiosqlite.connect(DATABASE_FILE) as db:
        async with db.execute('SELECT id, role_id, name, rarity, price, description FROM gacha_roles WHERE rarity = ?', (rarity,)) as cursor:
            rows = await cursor.fetchall()
            return [{"id": row[0], "role_id": row[1], "name": row[2], "rarity": row[3], "price": row[4], "description": row[5]} for row in rows]

async def add_gacha_role(role_id, name, rarity, price, description):
    async with aiosqlite.connect(DATABASE_FILE) as db:
        await db.execute('INSERT INTO gacha_roles (role_id, name, rarity, price, description) VALUES (?, ?, ?, ?, ?)', 
                        (role_id, name, rarity, price, description))
        await db.commit()

async def remove_gacha_role(gacha_role_id):
    async with aiosqlite.connect(DATABASE_FILE) as db:
        await db.execute('DELETE FROM gacha_roles WHERE id = ?', (gacha_role_id,))
        await db.commit()

async def get_gacha_role_by_id(gacha_role_id):
    async with aiosqlite.connect(DATABASE_FILE) as db:
        async with db.execute('SELECT id, role_id, name, rarity, price, description FROM gacha_roles WHERE id = ?', (gacha_role_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return {"id": row[0], "role_id": row[1], "name": row[2], "rarity": row[3], "price": row[4], "description": row[5]}
            return None

# レアリティ関連
def get_rarity_chances():
    return {
        "Common": 60,
        "Rare": 25,
        "Epic": 12,
        "Legendary": 3
    }

def get_rarity_emoji(rarity):
    return {
        "Common": "⚪",
        "Rare": "🔵", 
        "Epic": "🟣",
        "Legendary": "🟡"
    }.get(rarity, "⚪")

def is_admin_interaction(interaction):
    return interaction.user.guild_permissions.administrator or interaction.user == interaction.guild.owner

# Bot起動イベント
@bot.event
async def on_ready():
    global bot_start_time
    await init_database()
    bot_start_time = datetime.now()
    print(f'[{datetime.now()}] {bot.user} としてログインしました！')
    await bot.change_presence(activity=discord.Game(name="/help でコマンド確認"))

@bot.event
async def on_disconnect():
    print(f'[{datetime.now()}] ボットが切断されました。再接続を試行中...')

@bot.event
async def on_resumed():
    print(f'[{datetime.now()}] ボットが再接続されました！')

# Bot開始・再接続処理
async def start_bot():
    token = os.getenv('DISCORD_BOT_TOKEN')
    if not token:
        print('エラー: DISCORD_BOT_TOKENが設定されていません。')
        exit(1)
    
    while True:
        try:
            print(f'[{datetime.now()}] Discordボットを開始しています...')
            await bot.start(token)
        except discord.LoginFailure:
            print('エラー: 無効なボットトークンです。')
            break
        except discord.ConnectionClosed:
            print(f'[{datetime.now()}] 接続が閉じられました。5秒後に再接続します...')
            await asyncio.sleep(5)
        except Exception as e:
            print(f'[{datetime.now()}] エラーが発生しました: {e}')
            print('10秒後に再接続を試行します...')
            await asyncio.sleep(10)
            if not bot.is_closed():
                await bot.close()

if __name__ == '__main__':
    try:
        asyncio.run(start_bot())
    except KeyboardInterrupt:
        print('ボットを停止しています...')
    except Exception as e:
        print(f'予期しないエラー: {e}')
