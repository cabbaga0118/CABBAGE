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

# 商品データは現在データベースで管理されています

# スロットの絵文字
SLOT_EMOJIS = ["🍎", "🍊", "🍇", "🍓", "🍌", "🥝", "🍑"]

async def init_database():
    """データベースを初期化"""
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

async def get_user_data(user_id):
    """ユーザーデータを取得"""
    async with aiosqlite.connect(DATABASE_FILE) as db:
        async with db.execute('SELECT money, inventory, roles FROM users WHERE user_id = ?', (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return {"money": row[0], "inventory": json.loads(row[1]), "roles": json.loads(row[2] or "[]")}
            else:
                # 新規ユーザー
                await db.execute('INSERT INTO users (user_id) VALUES (?)', (user_id,))
                await db.commit()
                return {"money": 1000, "inventory": [], "roles": []}

async def update_user_money(user_id, money):
    """ユーザーのお金を更新"""
    async with aiosqlite.connect(DATABASE_FILE) as db:
        await db.execute('UPDATE users SET money = ? WHERE user_id = ?', (money, user_id))
        await db.commit()

async def add_to_inventory(user_id, item):
    """ユーザーのインベントリにアイテムを追加"""
    user_data = await get_user_data(user_id)
    user_data["inventory"].append(item)
    async with aiosqlite.connect(DATABASE_FILE) as db:
        await db.execute('UPDATE users SET inventory = ? WHERE user_id = ?', 
                        (json.dumps(user_data["inventory"]), user_id))
        await db.commit()

# 商品データベース関数
async def get_all_items():
    """すべての商品を取得"""
    async with aiosqlite.connect(DATABASE_FILE) as db:
        async with db.execute('SELECT id, emoji, name, price, description FROM items') as cursor:
            rows = await cursor.fetchall()
            return [{"id": row[0], "emoji": row[1], "name": row[2], "price": row[3], "description": row[4]} for row in rows]

async def add_item(emoji, name, price, description):
    """商品を追加"""
    async with aiosqlite.connect(DATABASE_FILE) as db:
        await db.execute('INSERT INTO items (emoji, name, price, description) VALUES (?, ?, ?, ?)', 
                        (emoji, name, price, description))
        await db.commit()

async def remove_item(item_id):
    """商品を削除"""
    async with aiosqlite.connect(DATABASE_FILE) as db:
        await db.execute('DELETE FROM items WHERE id = ?', (item_id,))
        await db.commit()

async def get_item_by_id(item_id):
    """IDで商品を取得"""
    async with aiosqlite.connect(DATABASE_FILE) as db:
        async with db.execute('SELECT id, emoji, name, price, description FROM items WHERE id = ?', (item_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return {"id": row[0], "emoji": row[1], "name": row[2], "price": row[3], "description": row[4]}
            return None

# ロールガチャ関数
async def add_user_role(user_id, role_data):
    """ユーザーにロールを追加"""
    user_data = await get_user_data(user_id)
    user_data["roles"].append(role_data)
    async with aiosqlite.connect(DATABASE_FILE) as db:
        await db.execute('UPDATE users SET roles = ? WHERE user_id = ?', 
                        (json.dumps(user_data["roles"]), user_id))
        await db.commit()

async def get_all_gacha_roles():
    """すべてのガチャロールを取得"""
    async with aiosqlite.connect(DATABASE_FILE) as db:
        async with db.execute('SELECT id, role_id, name, rarity, price, description FROM gacha_roles') as cursor:
            rows = await cursor.fetchall()
            return [{"id": row[0], "role_id": row[1], "name": row[2], "rarity": row[3], "price": row[4], "description": row[5]} for row in rows]

async def get_roles_by_rarity(rarity):
    """レアリティ別にロールを取得"""
    async with aiosqlite.connect(DATABASE_FILE) as db:
        async with db.execute('SELECT id, role_id, name, rarity, price, description FROM gacha_roles WHERE rarity = ?', (rarity,)) as cursor:
            rows = await cursor.fetchall()
            return [{"id": row[0], "role_id": row[1], "name": row[2], "rarity": row[3], "price": row[4], "description": row[5]} for row in rows]

async def add_gacha_role(role_id, name, rarity, price, description):
    """ガチャロールを追加"""
    async with aiosqlite.connect(DATABASE_FILE) as db:
        await db.execute('INSERT INTO gacha_roles (role_id, name, rarity, price, description) VALUES (?, ?, ?, ?, ?)', 
                        (role_id, name, rarity, price, description))
        await db.commit()

async def remove_gacha_role(gacha_role_id):
    """ガチャロールを削除"""
    async with aiosqlite.connect(DATABASE_FILE) as db:
        await db.execute('DELETE FROM gacha_roles WHERE id = ?', (gacha_role_id,))
        await db.commit()

async def get_gacha_role_by_id(gacha_role_id):
    """IDでガチャロールを取得"""
    async with aiosqlite.connect(DATABASE_FILE) as db:
        async with db.execute('SELECT id, role_id, name, rarity, price, description FROM gacha_roles WHERE id = ?', (gacha_role_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return {"id": row[0], "role_id": row[1], "name": row[2], "rarity": row[3], "price": row[4], "description": row[5]}
            return None

def get_rarity_chances():
    """レアリティの確率を返す"""
    return {
        "Common": 60,    # 60%
        "Rare": 25,      # 25%
        "Epic": 12,      # 12%
        "Legendary": 3   # 3%
    }

def get_rarity_emoji(rarity):
    """レアリティの絵文字を返す"""
    return {
        "Common": "⚪",
        "Rare": "🔵", 
        "Epic": "🟣",
        "Legendary": "🟡"
    }.get(rarity, "⚪")

def is_admin_interaction(interaction):
    """管理者権限をチェックする関数（インタラクション用）"""
    return interaction.user.guild_permissions.administrator or interaction.user == interaction.guild.owner

@bot.event
async def on_ready():
    global bot_start_time
    if bot.user:
        # データベースを初期化
        await init_database()
        
        # 開始時間を記録
        bot_start_time = datetime.now()
        print(f'[{datetime.now()}] {bot.user} としてログインしました！')
        print(f'Bot ID: {bot.user.id}')
        print(f'接続先サーバー数: {len(bot.guilds)}')
        
        # スラッシュコマンドを同期（グローバル）
        try:
            synced = await bot.tree.sync()
            print(f'グローバル同期されたスラッシュコマンド数: {len(synced)}')
        except Exception as e:
            print(f'グローバルスラッシュコマンド同期エラー: {e}')
        
        # 各ギルドでもコマンドを同期
        for guild in bot.guilds:
            try:
                synced_guild = await bot.tree.sync(guild=guild)
                print(f'ギルド {guild.name} で同期されたコマンド数: {len(synced_guild)}')
            except Exception as e:
                print(f'ギルド {guild.name} でのコマンド同期エラー: {e}')
        
        # ボットのステータスを設定
        await bot.change_presence(activity=discord.Game(name="/help でコマンド確認"))

@bot.event
async def on_disconnect():
    print(f'[{datetime.now()}] ボットが切断されました。再接続を試行中...')

@bot.event
async def on_resumed():
    print(f'[{datetime.now()}] ボットが再接続されました！')

# スラッシュコマンド: 残高確認
@bot.tree.command(name="balance", description="あなたの残高を確認します")
async def balance(interaction: discord.Interaction):
    user_data = await get_user_data(interaction.user.id)
    
    embed = discord.Embed(
        title="💰 残高",
        description=f"{interaction.user.mention}の残高: **{user_data['money']:,}円**",
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed)

# スラッシュコマンド: スロットゲーム
@bot.tree.command(name="slot", description="スロットゲームで運試し！")
async def slot(interaction: discord.Interaction, bet: int):
    if bet <= 0:
        await interaction.response.send_message("❌ ベット額は1円以上にしてください！", ephemeral=True)
        return
    
    user_data = await get_user_data(interaction.user.id)
    
    if user_data["money"] < bet:
        await interaction.response.send_message("❌ お金が足りません！", ephemeral=True)
        return
    
    # スロットを回す
    slot1 = random.choice(SLOT_EMOJIS)
    slot2 = random.choice(SLOT_EMOJIS)
    slot3 = random.choice(SLOT_EMOJIS)
    
    # 勝利判定
    if slot1 == slot2 == slot3:
        # 大当たり（同じ絵文字3つ）
        winnings = bet * 10
        result_text = "🎉 **大当たり！** 🎉"
        color = discord.Color.gold()
    elif slot1 == slot2 or slot2 == slot3 or slot1 == slot3:
        # 小当たり（2つ同じ）
        winnings = bet * 2
        result_text = "✨ **小当たり！** ✨"
        color = discord.Color.blue()
    else:
        # はずれ
        winnings = -bet
        result_text = "💸 **はずれ...**"
        color = discord.Color.red()
    
    # お金を更新
    new_money = user_data["money"] + winnings
    await update_user_money(interaction.user.id, new_money)
    
    embed = discord.Embed(
        title="🎰 スロットマシン",
        description=f"**{slot1} {slot2} {slot3}**\n\n{result_text}",
        color=color
    )
    embed.add_field(name="ベット額", value=f"{bet:,}円", inline=True)
    
    if winnings > 0:
        embed.add_field(name="獲得額", value=f"+{winnings:,}円", inline=True)
    else:
        embed.add_field(name="損失額", value=f"{winnings:,}円", inline=True)
    
    embed.add_field(name="残高", value=f"{new_money:,}円", inline=True)
    
    await interaction.response.send_message(embed=embed)

# スラッシュコマンド: ショップ
@bot.tree.command(name="shop", description="ショップで商品を確認します")
async def shop(interaction: discord.Interaction):
    items = await get_all_items()
    
    embed = discord.Embed(
        title="🏪 ショップ",
        color=discord.Color.purple()
    )
    
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

# スラッシュコマンド: 商品購入
@bot.tree.command(name="buy", description="ショップで商品を購入します")
async def buy(interaction: discord.Interaction, item_id: int):
    # IDで商品を検索
    item_data = await get_item_by_id(item_id)
    
    if not item_data:
        await interaction.response.send_message(
            f"❌ 商品ID {item_id} が見つかりません！/shop で利用可能な商品を確認してください。", 
            ephemeral=True
        )
        return
    
    user_data = await get_user_data(interaction.user.id)
    
    if user_data["money"] < item_data["price"]:
        await interaction.response.send_message(
            f"❌ お金が足りません！\n必要額: {item_data['price']:,}円\n現在の残高: {user_data['money']:,}円", 
            ephemeral=True
        )
        return
    
    # 購入処理
    new_money = user_data["money"] - item_data["price"]
    await update_user_money(interaction.user.id, new_money)
    await add_to_inventory(interaction.user.id, f"{item_data['emoji']} {item_data['name']}")
    
    embed = discord.Embed(
        title="✅ 購入完了",
        description=f"{item_data['emoji']} **{item_data['name']}** を購入しました！",
        color=discord.Color.green()
    )
    embed.add_field(name="価格", value=f"{item_data['price']:,}円", inline=True)
    embed.add_field(name="残高", value=f"{new_money:,}円", inline=True)
    
    await interaction.response.send_message(embed=embed)

# スラッシュコマンド: インベントリ
@bot.tree.command(name="inventory", description="あなたの所持品を確認します")
async def inventory(interaction: discord.Interaction):
    user_data = await get_user_data(interaction.user.id)
    
    embed = discord.Embed(
        title="🎒 インベントリ",
        color=discord.Color.blue()
    )
    
    if not user_data["inventory"]:
        embed.description = "まだ何も持っていません。ショップで商品を購入してみましょう！"
    else:
        # アイテムを数える
        item_counts = {}
        for item in user_data["inventory"]:
            item_counts[item] = item_counts.get(item, 0) + 1
        
        inventory_text = "\n".join([f"{item} x{count}" for item, count in item_counts.items()])
        embed.description = inventory_text
    
    embed.add_field(name="残高", value=f"{user_data['money']:,}円", inline=True)
    
    await interaction.response.send_message(embed=embed)

# スラッシュコマンド: デイリーボーナス
@bot.tree.command(name="daily", description="デイリーボーナスを受け取ります")
async def daily(interaction: discord.Interaction):
    user_data = await get_user_data(interaction.user.id)
    
    # デイリーボーナス（100-500円）
    bonus = random.randint(100, 500)
    new_money = user_data["money"] + bonus
    await update_user_money(interaction.user.id, new_money)
    
    embed = discord.Embed(
        title="🎁 デイリーボーナス",
        description=f"**{bonus:,}円** を受け取りました！",
        color=discord.Color.gold()
    )
    embed.add_field(name="新しい残高", value=f"{new_money:,}円", inline=True)
    
    await interaction.response.send_message(embed=embed)

# スラッシュコマンド: リーダーボード
@bot.tree.command(name="leaderboard", description="お金持ちランキングを表示します")
async def leaderboard(interaction: discord.Interaction):
    async with aiosqlite.connect(DATABASE_FILE) as db:
        async with db.execute('SELECT user_id, money FROM users ORDER BY money DESC LIMIT 10') as cursor:
            rows = await cursor.fetchall()
    
    embed = discord.Embed(
        title="💰 お金持ちランキング",
        color=discord.Color.gold()
    )
    
    if not rows:
        embed.description = "まだデータがありません。"
    else:
        ranking_text = ""
        for i, (user_id, money) in enumerate(rows, 1):
            try:
                user = await bot.fetch_user(user_id)
                username = user.display_name
            except:
                username = f"ユーザー#{user_id}"
            
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            ranking_text += f"{medal} {username}: {money:,}円\n"
        
        embed.description = ranking_text
    
    await interaction.response.send_message(embed=embed)

# スラッシュコマンド: ロールガチャ
@bot.tree.command(name="role_gacha", description="ロールガチャを引いてランダムなロールを獲得しよう！")
async def role_gacha(interaction: discord.Interaction, price: int = 1000):
    if price <= 0:
        await interaction.response.send_message("❌ ガチャ価格は1円以上にしてください！", ephemeral=True)
        return
    
    user_data = await get_user_data(interaction.user.id)
    
    if user_data["money"] < price:
        await interaction.response.send_message(
            f"❌ お金が足りません！\n必要額: {price:,}円\n現在の残高: {user_data['money']:,}円", 
            ephemeral=True
        )
        return
    
    # レアリティを決定
    rarity_chances = get_rarity_chances()
    rand = random.randint(1, 100)
    
    selected_rarity = None
    cumulative = 0
    for rarity, chance in rarity_chances.items():
        cumulative += chance
        if rand <= cumulative:
            selected_rarity = rarity
            break
    
    # 選択されたレアリティのロールを取得
    available_roles = await get_roles_by_rarity(selected_rarity)
    
    if not available_roles:
        await interaction.response.send_message(
            f"❌ {selected_rarity}レアリティのロールが存在しません。管理者にお問い合わせください。", 
            ephemeral=True
        )
        return
    
    # ランダムにロールを選択
    selected_role = random.choice(available_roles)
    
    # お金を減算
    new_money = user_data["money"] - price
    await update_user_money(interaction.user.id, new_money)
    
    # ユーザーにロールを追加
    role_data = {
        "id": selected_role["id"],
        "name": selected_role["name"],
        "rarity": selected_role["rarity"]
    }
    await add_user_role(interaction.user.id, role_data)
    
    # Discordサーバーでロールを付与
    try:
        if interaction.guild:
            guild_role = interaction.guild.get_role(selected_role["role_id"])
            member = interaction.guild.get_member(interaction.user.id)
            if guild_role and member:
                await member.add_roles(guild_role)
                role_granted = True
            else:
                role_granted = False
        else:
            role_granted = False
    except:
        role_granted = False
    
    embed = discord.Embed(
        title="🎲 ロールガチャ結果",
        color=discord.Color.gold() if selected_rarity == "Legendary" else 
              discord.Color.purple() if selected_rarity == "Epic" else
              discord.Color.blue() if selected_rarity == "Rare" else
              discord.Color.light_grey()
    )
    
    rarity_emoji = get_rarity_emoji(selected_rarity)
    embed.add_field(
        name="獲得ロール",
        value=f"{rarity_emoji} **{selected_role['name']}**\n{selected_role['description']}",
        inline=False
    )
    embed.add_field(name="レアリティ", value=f"{rarity_emoji} {selected_rarity}", inline=True)
    embed.add_field(name="消費額", value=f"{price:,}円", inline=True)
    embed.add_field(name="残高", value=f"{new_money:,}円", inline=True)
    
    if not role_granted:
        embed.add_field(
            name="⚠️ 注意", 
            value="ロールは記録されましたが、サーバーでの付与に失敗しました。", 
            inline=False
        )
    
    await interaction.response.send_message(embed=embed)

# スラッシュコマンド: ロール確認
@bot.tree.command(name="my_roles", description="あなたの所持ロールを確認します")
async def my_roles(interaction: discord.Interaction):
    user_data = await get_user_data(interaction.user.id)
    
    embed = discord.Embed(
        title="🎭 あなたの所持ロール",
        color=discord.Color.blue()
    )
    
    if not user_data["roles"]:
        embed.description = "まだロールを持っていません。/role_gacha でロールガチャを引いてみましょう！"
    else:
        # ロール数をカウント
        role_counts = {}
        for role in user_data["roles"]:
            key = f"{role['name']} ({role['rarity']})"
            role_counts[key] = role_counts.get(key, 0) + 1
        
        roles_text = ""
        for role_name, count in role_counts.items():
            roles_text += f"{role_name} x{count}\n"
        
        embed.description = roles_text
        embed.add_field(name="総ロール数", value=f"{len(user_data['roles'])}個", inline=True)
    
    embed.add_field(name="残高", value=f"{user_data['money']:,}円", inline=True)
    
    await interaction.response.send_message(embed=embed)

# 管理者専用スラッシュコマンド: 商品追加
@bot.tree.command(name="add_item", description="ショップに商品を追加します（管理者専用）")
async def add_item_command(interaction: discord.Interaction, emoji: str, name: str, price: int, description: str):
    if not is_admin_interaction(interaction):
        await interaction.response.send_message("❌ このコマンドは管理者のみ使用できます。", ephemeral=True)
        return
    
    if price <= 0:
        await interaction.response.send_message("❌ 価格は1円以上にしてください。", ephemeral=True)
        return
    
    try:
        await add_item(emoji, name, price, description)
        
        embed = discord.Embed(
            title="✅ 商品追加完了",
            description=f"新しい商品を追加しました！",
            color=discord.Color.green()
        )
        embed.add_field(name="商品", value=f"{emoji} {name}", inline=True)
        embed.add_field(name="価格", value=f"{price:,}円", inline=True)
        embed.add_field(name="説明", value=description, inline=False)
        
        await interaction.response.send_message(embed=embed)
        print(f'[{datetime.now()}] {interaction.user}が商品を追加: {emoji} {name} ({price}円)')
        
    except Exception as e:
        await interaction.response.send_message(f"❌ エラーが発生しました: {e}", ephemeral=True)

# 管理者専用スラッシュコマンド: 商品削除
@bot.tree.command(name="remove_item", description="ショップから商品を削除します（管理者専用）")
async def remove_item_command(interaction: discord.Interaction, item_id: int):
    if not is_admin_interaction(interaction):
        await interaction.response.send_message("❌ このコマンドは管理者のみ使用できます。", ephemeral=True)
        return
    
    # 商品の存在確認
    item_data = await get_item_by_id(item_id)
    if not item_data:
        await interaction.response.send_message(f"❌ 商品ID {item_id} が見つかりません。", ephemeral=True)
        return
    
    try:
        await remove_item(item_id)
        
        embed = discord.Embed(
            title="✅ 商品削除完了",
            description=f"商品を削除しました。",
            color=discord.Color.red()
        )
        embed.add_field(name="削除された商品", value=f"{item_data['emoji']} {item_data['name']}", inline=True)
        embed.add_field(name="価格", value=f"{item_data['price']:,}円", inline=True)
        
        await interaction.response.send_message(embed=embed)
        print(f'[{datetime.now()}] {interaction.user}が商品を削除: {item_data["name"]} (ID: {item_id})')
        
    except Exception as e:
        await interaction.response.send_message(f"❌ エラーが発生しました: {e}", ephemeral=True)

# 管理者専用スラッシュコマンド: 商品一覧管理
@bot.tree.command(name="manage_items", description="商品管理（一覧表示・管理者専用）")
async def manage_items(interaction: discord.Interaction):
    if not is_admin_interaction(interaction):
        await interaction.response.send_message("❌ このコマンドは管理者のみ使用できます。", ephemeral=True)
        return
    
    items = await get_all_items()
    
    embed = discord.Embed(
        title="🛠️ 商品管理",
        color=discord.Color.blue()
    )
    
    if not items:
        embed.description = "現在、登録されている商品はありません。"
    else:
        embed.description = f"登録されている商品数: {len(items)}"
        for item in items:
            embed.add_field(
                name=f"ID: {item['id']} | {item['emoji']} {item['name']}",
                value=f"価格: {item['price']:,}円\n{item['description']}",
                inline=False
            )
    
    embed.set_footer(text="/add_item で追加、/remove_item <ID> で削除")
    await interaction.response.send_message(embed=embed, ephemeral=True)

# 管理者専用スラッシュコマンド: ロール追加
@bot.tree.command(name="add_role", description="ガチャロールを追加します（管理者専用）")
async def add_role_command(interaction: discord.Interaction, role: discord.Role, rarity: str, price: int, description: str):
    if not is_admin_interaction(interaction):
        await interaction.response.send_message("❌ このコマンドは管理者のみ使用できます。", ephemeral=True)
        return
    
    if rarity not in ["Common", "Rare", "Epic", "Legendary"]:
        await interaction.response.send_message("❌ レアリティは Common, Rare, Epic, Legendary のいずれかを指定してください。", ephemeral=True)
        return
    
    if price <= 0:
        await interaction.response.send_message("❌ 価格は1円以上にしてください。", ephemeral=True)
        return
    
    try:
        await add_gacha_role(role.id, role.name, rarity, price, description)
        
        rarity_emoji = get_rarity_emoji(rarity)
        embed = discord.Embed(
            title="✅ ロール追加完了",
            description=f"新しいガチャロールを追加しました！",
            color=discord.Color.green()
        )
        embed.add_field(name="ロール", value=f"{role.mention}", inline=True)
        embed.add_field(name="レアリティ", value=f"{rarity_emoji} {rarity}", inline=True)
        embed.add_field(name="ガチャ価格", value=f"{price:,}円", inline=True)
        embed.add_field(name="説明", value=description, inline=False)
        
        await interaction.response.send_message(embed=embed)
        print(f'[{datetime.now()}] {interaction.user}がロールを追加: {role.name} ({rarity})')
        
    except Exception as e:
        await interaction.response.send_message(f"❌ エラーが発生しました: {e}", ephemeral=True)

# 管理者専用スラッシュコマンド: ロール削除
@bot.tree.command(name="remove_role", description="ガチャロールを削除します（管理者専用）")
async def remove_role_command(interaction: discord.Interaction, role_id: int):
    if not is_admin_interaction(interaction):
        await interaction.response.send_message("❌ このコマンドは管理者のみ使用できます。", ephemeral=True)
        return
    
    # ロールの存在確認
    role_data = await get_gacha_role_by_id(role_id)
    if not role_data:
        await interaction.response.send_message(f"❌ ロールID {role_id} が見つかりません。", ephemeral=True)
        return
    
    try:
        await remove_gacha_role(role_id)
        
        rarity_emoji = get_rarity_emoji(role_data["rarity"])
        embed = discord.Embed(
            title="✅ ロール削除完了",
            description=f"ガチャロールを削除しました。",
            color=discord.Color.red()
        )
        embed.add_field(name="削除されたロール", value=f"{role_data['name']}", inline=True)
        embed.add_field(name="レアリティ", value=f"{rarity_emoji} {role_data['rarity']}", inline=True)
        
        await interaction.response.send_message(embed=embed)
        print(f'[{datetime.now()}] {interaction.user}がロールを削除: {role_data["name"]} (ID: {role_id})')
        
    except Exception as e:
        await interaction.response.send_message(f"❌ エラーが発生しました: {e}", ephemeral=True)

# 管理者専用スラッシュコマンド: ロール一覧管理
@bot.tree.command(name="manage_roles", description="ガチャロール管理（一覧表示・管理者専用）")
async def manage_roles(interaction: discord.Interaction):
    if not is_admin_interaction(interaction):
        await interaction.response.send_message("❌ このコマンドは管理者のみ使用できます。", ephemeral=True)
        return
    
    roles = await get_all_gacha_roles()
    
    embed = discord.Embed(
        title="🎭 ガチャロール管理",
        color=discord.Color.blue()
    )
    
    if not roles:
        embed.description = "現在、登録されているガチャロールはありません。"
    else:
        embed.description = f"登録されているガチャロール数: {len(roles)}"
        for role in roles:
            rarity_emoji = get_rarity_emoji(role["rarity"])
            embed.add_field(
                name=f"ID: {role['id']} | {rarity_emoji} {role['name']}",
                value=f"レアリティ: {role['rarity']}\n価格: {role['price']:,}円\n{role['description']}",
                inline=False
            )
    
    embed.set_footer(text="/add_role で追加、/remove_role <ID> で削除")
    await interaction.response.send_message(embed=embed, ephemeral=True)

# 従来のコマンド（管理用）
def is_admin(ctx):
    """管理者権限をチェックする関数"""
    return ctx.author.guild_permissions.administrator or ctx.author == ctx.guild.owner

@bot.command(name='restart')
async def restart_bot(ctx):
    """ボットを再起動するコマンド（管理者専用）"""
    if not is_admin(ctx):
        await ctx.send('⚠️ このコマンドは管理者のみ使用できます。')
        return
    
    embed = discord.Embed(
        title='🔄 ボット再起動',
        description='ボットを再起動しています...\n数秒後に再接続されます。',
        color=discord.Color.orange()
    )
    embed.set_footer(text=f'実行者: {ctx.author}')
    await ctx.send(embed=embed)
    
    print(f'[{datetime.now()}] {ctx.author}によりボットが再起動されました')
    
    # プロセス全体を終了（Replitワークフローが自動的に再起動）
    await asyncio.sleep(1)  # メッセージ送信を待つ
    sys.exit(0)

@bot.command(name='status')
async def bot_status(ctx):
    """ボットの状態を表示するコマンド"""
    embed = discord.Embed(
        title='🤖 ボットステータス',
        color=discord.Color.green()
    )
    
    # 稼働時間の計算
    if bot_start_time:
        uptime = datetime.now() - bot_start_time
        uptime_str = f'{uptime.days}日 {uptime.seconds//3600}時間 {(uptime.seconds//60)%60}分'
    else:
        uptime_str = '不明'
    
    embed.add_field(name='レイテンシ', value=f'{round(bot.latency * 1000)}ms', inline=True)
    embed.add_field(name='接続サーバー数', value=f'{len(bot.guilds)}', inline=True)
    embed.add_field(name='稼働時間', value=uptime_str, inline=True)
    embed.add_field(name='ユーザー数', value=f'{len(bot.users)}', inline=True)
    embed.add_field(name='Pythonバージョン', value=f'{sys.version[:5]}', inline=True)
    embed.add_field(name='discord.pyバージョン', value=discord.__version__, inline=True)
    
    await ctx.send(embed=embed)

@bot.command(name='sync')
async def sync_commands(ctx):
    """スラッシュコマンドを強制同期するコマンド（管理者専用）"""
    if not is_admin(ctx):
        await ctx.send('⚠️ このコマンドは管理者のみ使用できます。')
        return
    
    embed = discord.Embed(
        title='🔄 コマンド同期中',
        description='スラッシュコマンドを同期しています...',
        color=discord.Color.blue()
    )
    message = await ctx.send(embed=embed)
    
    try:
        # グローバル同期
        synced_global = await bot.tree.sync()
        
        # 現在のギルドで同期
        synced_guild = await bot.tree.sync(guild=ctx.guild)
        
        embed = discord.Embed(
            title='✅ コマンド同期完了',
            color=discord.Color.green()
        )
        embed.add_field(name='グローバル同期', value=f'{len(synced_global)}個のコマンド', inline=True)
        embed.add_field(name='ギルド同期', value=f'{len(synced_guild)}個のコマンド', inline=True)
        embed.add_field(name='注意', value='コマンドが反映されるまで最大1時間かかる場合があります', inline=False)
        
        await message.edit(embed=embed)
        print(f'[{datetime.now()}] {ctx.author}がコマンド同期を実行')
        
    except Exception as e:
        embed = discord.Embed(
            title='❌ 同期エラー',
            description=f'エラー: {e}',
            color=discord.Color.red()
        )
        await message.edit(embed=embed)

async def start_bot():
    """ボットを開始する関数（自動再接続機能付き）"""
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
        finally:
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
