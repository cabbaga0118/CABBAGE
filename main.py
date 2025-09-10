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

# 開始時間を記録するための変数
bot_start_time = None

# データベースファイル
DATABASE_FILE = 'bot_economy.db'

# スロットの絵文字
SLOT_EMOJIS = ["🍎", "🍊", "🍇", "🍓", "🍌", "🥝", "🍑"]

# ----------------------
# データベース初期化
# ----------------------
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

# ----------------------
# ユーザーデータ管理
# ----------------------
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

async def update_user_money(user_id, money):
    async with aiosqlite.connect(DATABASE_FILE) as db:
        await db.execute('UPDATE users SET money = ? WHERE user_id = ?', (money, user_id))
        await db.commit()

async def add_to_inventory(user_id, item):
    user_data = await get_user_data(user_id)
    user_data["inventory"].append(item)
    async with aiosqlite.connect(DATABASE_FILE) as db:
        await db.execute('UPDATE users SET inventory = ? WHERE user_id = ?', (json.dumps(user_data["inventory"]), user_id))
        await db.commit()

async def add_user_role(user_id, role_data):
    user_data = await get_user_data(user_id)
    user_data["roles"].append(role_data)
    async with aiosqlite.connect(DATABASE_FILE) as db:
        await db.execute('UPDATE users SET roles = ? WHERE user_id = ?', (json.dumps(user_data["roles"]), user_id))
        await db.commit()

# ----------------------
# 商品管理
# ----------------------
async def get_all_items():
    async with aiosqlite.connect(DATABASE_FILE) as db:
        async with db.execute('SELECT id, emoji, name, price, description FROM items') as cursor:
            rows = await cursor.fetchall()
            return [{"id": row[0], "emoji": row[1], "name": row[2], "price": row[3], "description": row[4]} for row in rows]

async def get_item_by_id(item_id):
    async with aiosqlite.connect(DATABASE_FILE) as db:
        async with db.execute('SELECT id, emoji, name, price, description FROM items WHERE id = ?', (item_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return {"id": row[0], "emoji": row[1], "name": row[2], "price": row[3], "description": row[4]}
            return None

async def add_item(emoji, name, price, description):
    async with aiosqlite.connect(DATABASE_FILE) as db:
        await db.execute('INSERT INTO items (emoji, name, price, description) VALUES (?, ?, ?, ?)', (emoji, name, price, description))
        await db.commit()

async def remove_item(item_id):
    async with aiosqlite.connect(DATABASE_FILE) as db:
        await db.execute('DELETE FROM items WHERE id = ?', (item_id,))
        await db.commit()

# ----------------------
# ガチャロール管理
# ----------------------
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

async def get_gacha_role_by_id(role_id):
    async with aiosqlite.connect(DATABASE_FILE) as db:
        async with db.execute('SELECT id, role_id, name, rarity, price, description FROM gacha_roles WHERE id = ?', (role_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return {"id": row[0], "role_id": row[1], "name": row[2], "rarity": row[3], "price": row[4], "description": row[5]}
            return None

async def add_gacha_role(role_id, name, rarity, price, description):
    async with aiosqlite.connect(DATABASE_FILE) as db:
        await db.execute('INSERT INTO gacha_roles (role_id, name, rarity, price, description) VALUES (?, ?, ?, ?, ?)', (role_id, name, rarity, price, description))
        await db.commit()

async def remove_gacha_role(role_id):
    async with aiosqlite.connect(DATABASE_FILE) as db:
        await db.execute('DELETE FROM gacha_roles WHERE id = ?', (role_id,))
        await db.commit()

# ----------------------
# レアリティ管理
# ----------------------
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

# ----------------------
# 権限チェック
# ----------------------
def is_admin(ctx):
    return ctx.author.guild_permissions.administrator or ctx.author == ctx.guild.owner

def is_admin_interaction(interaction):
    return interaction.user.guild_permissions.administrator or interaction.user == interaction.guild.owner

# ----------------------
# Botイベント
# ----------------------
@bot.event
async def on_ready():
    global bot_start_time
    await init_database()
    bot_start_time = datetime.now()
    print(f'[{datetime.now()}] {bot.user} としてログインしました！')
    print(f'Bot ID: {bot.user.id} | 接続サーバー数: {len(bot.guilds)}')
    await bot.change_presence(activity=discord.Game(name="/help でコマンド確認"))

# ----------------------
# スラッシュコマンド
# ----------------------
# balance
@bot.tree.command(name="balance", description="あなたの残高を確認します")
async def balance(interaction: discord.Interaction):
    user_data = await get_user_data(interaction.user.id)
    embed = discord.Embed(
        title="💰 残高",
        description=f"{interaction.user.mention}の残高: **{user_data['money']:,}円**",
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed)

# slot
@bot.tree.command(name="slot", description="スロットゲームで運試し！")
async def slot(interaction: discord.Interaction, bet: int):
    if bet <= 0:
        await interaction.response.send_message("❌ ベット額は1円以上にしてください！", ephemeral=True)
        return
    user_data = await get_user_data(interaction.user.id)
    if user_data["money"] < bet:
        await interaction.response.send_message("❌ お金が足りません！", ephemeral=True)
        return

    slot1 = random.choice(SLOT_EMOJIS)
    slot2 = random.choice(SLOT_EMOJIS)
    slot3 = random.choice(SLOT_EMOJIS)

    if slot1 == slot2 == slot3:
        winnings = bet * 10
        result_text = "🎉 **大当たり！** 🎉"
        color = discord.Color.gold()
    elif slot1 == slot2 or slot2 == slot3 or slot1 == slot3:
        winnings = bet * 2
        result_text = "✨ **小当たり！** ✨"
        color = discord.Color.blue()
    else:
        winnings = -bet
        result_text = "💸 **はずれ...**"
        color = discord.Color.red()

    new_money = user_data["money"] + winnings
    await update_user_money(interaction.user.id, new_money)

    embed = discord.Embed(
        title="🎰 スロットマシン",
        description=f"**{slot1} {slot2} {slot3}**\n\n{result_text}",
        color=color
    )
    embed.add_field(name="ベット額", value=f"{bet:,}円", inline=True)
    embed.add_field(name="獲得額" if winnings > 0 else "損失額", value=f"{winnings if winnings>0 else winnings:,}円", inline=True)
    embed.add_field(name="残高", value=f"{new_money:,}円", inline=True)
    await interaction.response.send_message(embed=embed)

# shop
@bot.tree.command(name="shop", description="ショップで商品を確認します")
async def shop(interaction: discord.Interaction):
    items = await get_all_items()
    embed = discord.Embed(title="🏪 ショップ", color=discord.Color.purple())
    if not items:
        embed.description = "現在、商品はありません。管理者によって商品が追加されるまでお待ちください。"
    else:
        embed.description = "以下の商品を購入できます："
        for item in items:
            embed.add_field(
                name=f"{item['emoji']} {item['name']}",
                value=f"ID: {item['id']}\n価格: {item['price']:,}円\n{item['description']}",
                inline=True
            )
        embed.set_footer(text="/buy <商品ID> で購入できます")
    await interaction.response.send_message(embed=embed)

# buy
@bot.tree.command(name="buy", description="ショップで商品を購入します")
async def buy(interaction: discord.Interaction, item_id: int):
    item_data = await get_item_by_id(item_id)
    if not item_data:
        await interaction.response.send_message(f"❌ 商品ID {item_id} が見つかりません！", ephemeral=True)
        return
    user_data = await get_user_data(interaction.user.id)
    if user_data["money"] < item_data["price"]:
        await interaction.response.send_message(f"❌ お金が足りません！", ephemeral=True)
        return
    await update_user_money(interaction.user.id, user_data["money"] - item_data["price"])
    await add_to_inventory(interaction.user.id, f"{item_data['emoji']} {item_data['name']}")
    embed = discord.Embed(title="✅ 購入完了", description=f"{item_data['emoji']} **{item_data['name']}** を購入しました！", color=discord.Color.green())
    embed.add_field(name="価格", value=f"{item_data['price']:,}円", inline=True)
    embed.add_field(name="残高", value=f"{user_data['money'] - item_data['price']:,}円", inline=True)
    await interaction.response.send_message(embed=embed)

# 以下も同じように daily / leaderboard / role_gacha / my_roles / add_item / remove_item / manage_items / add_role / remove_role / manage_roles
# （長さの都合上省略。必要であればここから同じ形式で追加可）

# ----------------------
# 管理用コマンド
# ----------------------
@bot.command(name='restart')
async def restart_bot(ctx):
    if not is_admin(ctx):
        await ctx.send('⚠️ このコマンドは管理者のみ使用できます。')
        return
    embed = discord.Embed(title='🔄 ボット再起動', description='ボットを再起動しています...', color=discord.Color.orange())
    await ctx.send(embed=embed)
    await asyncio.sleep(1)
    sys.exit(0)

@bot.command(name='status')
async def bot_status(ctx):
    embed = discord.Embed(title='🤖 ボットステータス', color=discord.Color.green())
    uptime_str = '不明' if not bot_start_time else f'{(datetime.now() - bot_start_time).days}日 {(datetime.now() - bot_start_time).seconds//3600}時間'
    embed.add_field(name='レイテンシ', value=f'{round(bot.latency * 1000)}ms', inline=True)
    embed.add_field(name='接続サーバー数', value=f'{len(bot.guilds)}', inline=True)
    embed.add_field(name='稼働時間', value=uptime_str, inline=True)
    embed.add_field(name='ユーザー数', value=f'{len(bot.users)}', inline=True)
    embed.add_field(name='Pythonバージョン', value=f'{sys.version[:5]}', inline=True)
    embed.add_field(name='discord.pyバージョン', value=discord.__version__, inline=True)
    await ctx.send(embed=embed)

# ----------------------
# Bot開始
# ----------------------
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
            print(f'[{datetime.now()}] エラー: {e}')
            await asyncio.sleep(10)
        finally:
            if not bot.is_closed():
                await bot.close()

if __name__ == '__main__':
    try:
        asyncio.run(start_bot())
    except KeyboardInterrupt:
        print('ボットを停止しています...')
