import discord
from discord.ext import commands
import aiosqlite
import random
import os
import asyncio
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# Bot設定
intents = discord.Intents.default()
bot = commands.Bot(command_prefix='!', intents=intents)


# データベース初期化
async def init_db():
    async with aiosqlite.connect('bot_database.db') as db:
        # ユーザーのお金を管理するテーブル
        await db.execute('''
            CREATE TABLE IF NOT EXISTS user_money (
                user_id INTEGER PRIMARY KEY,
                balance INTEGER DEFAULT 1000,
                last_daily DATE
            )
        ''')

        # 既存テーブルにlast_dailyカラムを追加（存在しない場合）
        try:
            await db.execute(
                'ALTER TABLE user_money ADD COLUMN last_daily DATE')
        except:
            pass  # カラムが既に存在する場合はエラーを無視

        # ショップアイテムを管理するテーブル
        await db.execute('''
            CREATE TABLE IF NOT EXISTS shop_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                price INTEGER NOT NULL,
                description TEXT,
                stock INTEGER DEFAULT -1
            )
        ''')

        # ガチャロールを管理するテーブル
        await db.execute('''
            CREATE TABLE IF NOT EXISTS gacha_roles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role_id INTEGER NOT NULL,
                role_name TEXT NOT NULL,
                probability REAL NOT NULL,
                description TEXT
            )
        ''')

        # 既存テーブルからcostカラムを削除（存在する場合）
        try:
            await db.execute('ALTER TABLE gacha_roles DROP COLUMN cost')
        except:
            pass  # カラムが存在しない場合はエラーを無視

        await db.commit()


# ユーザーの残高取得・初期化
async def get_user_balance(user_id):
    async with aiosqlite.connect('bot_database.db') as db:
        cursor = await db.execute(
            'SELECT balance FROM user_money WHERE user_id = ?', (user_id, ))
        result = await cursor.fetchone()

        if result is None:
            await db.execute(
                'INSERT INTO user_money (user_id, balance) VALUES (?, ?)',
                (user_id, 1000))
            await db.commit()
            return 1000

        return result[0]


# ユーザーの残高更新
async def update_user_balance(user_id, new_balance):
    async with aiosqlite.connect('bot_database.db') as db:
        await db.execute('UPDATE user_money SET balance = ? WHERE user_id = ?',
                         (new_balance, user_id))
        await db.commit()


@bot.event
async def on_ready():
    print(f'{bot.user} としてログインしました！')
    await init_db()

    # スラッシュコマンドを同期
    try:
        synced = await bot.tree.sync()
        print(f"{len(synced)} 個のスラッシュコマンドを同期しました")
    except Exception as e:
        print(f"スラッシュコマンドの同期に失敗しました: {e}")


# スロットマシンコマンド
@bot.tree.command(
    name="slot",
    description="Play slot machine! Bet money and try to get triple matches")
async def slot_machine(interaction: discord.Interaction, bet_amount: int):
    user_id = interaction.user.id

    if bet_amount <= 0:
        await interaction.response.send_message(
            "Bet amount must be 1 or more!", ephemeral=True)
        return

    current_balance = await get_user_balance(user_id)

    if current_balance < bet_amount:
        await interaction.response.send_message(
            f"Insufficient balance! Current: {current_balance} coins",
            ephemeral=True)
        return

    # スロットのシンボル
    symbols = ['🍒', '🍋', '🍊', '🍇', '🍎', '💎', '⭐', '7️⃣']

    # スロット結果生成
    result = [random.choice(symbols) for _ in range(3)]

    # 勝利判定
    win_amount = 0
    if result[0] == result[1] == result[2]:
        if result[0] == '💎':
            win_amount = bet_amount * 10  # Diamond is 10x
        elif result[0] == '7️⃣':
            win_amount = bet_amount * 15  # Lucky 7 is 15x
        elif result[0] == '⭐':
            win_amount = bet_amount * 8  # Star is 8x
        else:
            win_amount = bet_amount * 5  # Others are 5x
    elif len(set(result)) == 2:  # Two matches
        win_amount = bet_amount * 2

    # Update balance
    new_balance = current_balance - bet_amount + win_amount
    await update_user_balance(user_id, new_balance)

    # 結果表示
    embed = discord.Embed(
        title="🎰 スロットマシン 🎰",
        color=0x00ff00 if win_amount > bet_amount else 0xff0000)
    embed.add_field(name="結果", value=" ".join(result), inline=False)
    embed.add_field(name="Bet", value=f"{bet_amount} coins", inline=True)

    if win_amount > 0:
        profit = win_amount - bet_amount
        embed.add_field(name="Won", value=f"{win_amount} coins", inline=True)
        embed.add_field(name="Profit", value=f"+{profit} coins", inline=True)
        if win_amount >= bet_amount * 10:
            embed.add_field(name="🎉 JACKPOT!",
                            value="Congratulations!",
                            inline=False)
    else:
        embed.add_field(name="Result", value="Loss", inline=True)
        embed.add_field(name="Loss", value=f"-{bet_amount} coins", inline=True)

    embed.add_field(name="New Balance",
                    value=f"{new_balance} coins",
                    inline=False)

    await interaction.response.send_message(embed=embed)


# Balance check command
@bot.tree.command(name="balance", description="Check your current balance")
async def check_balance(interaction: discord.Interaction):
    user_id = interaction.user.id
    balance = await get_user_balance(user_id)

    embed = discord.Embed(title="💰 残高確認", color=0x00ff00)
    embed.add_field(name="Your Balance",
                    value=f"{balance} coins",
                    inline=False)

    await interaction.response.send_message(embed=embed, ephemeral=True)


# Shop display command
@bot.tree.command(name="shop", description="Display shop items")
async def shop(interaction: discord.Interaction):
    async with aiosqlite.connect('bot_database.db') as db:
        cursor = await db.execute(
            'SELECT id, name, price, description, stock FROM shop_items')
        items = await cursor.fetchall()

    if not items:
        await interaction.response.send_message("No items in shop.",
                                                ephemeral=True)
        return

    embed = discord.Embed(title="🛒 ショップ", color=0x0099ff)

    for item in items:
        item_id, name, price, description, stock = item
        stock_text = f"Stock: {stock}" if stock != -1 else "Stock: Unlimited"
        embed.add_field(
            name=f"{name} (ID: {item_id})",
            value=f"Price: {price} coins\n{description}\n{stock_text}",
            inline=False)

    embed.add_field(name="How to buy",
                    value="Use /buy <item_id> to purchase items",
                    inline=False)

    await interaction.response.send_message(embed=embed)


# Buy command
@bot.tree.command(name="buy", description="Buy an item from the shop")
async def buy_item(interaction: discord.Interaction, item_id: int):
    user_id = interaction.user.id

    async with aiosqlite.connect('bot_database.db') as db:
        # Get item info
        cursor = await db.execute(
            'SELECT name, price, stock FROM shop_items WHERE id = ?',
            (item_id, ))
        item = await cursor.fetchone()

        if not item:
            await interaction.response.send_message(
                "Item with specified ID not found.", ephemeral=True)
            return

        name, price, stock = item

        # Check stock
        if stock == 0:
            await interaction.response.send_message(
                "This item is out of stock.", ephemeral=True)
            return

        # Check balance
        balance = await get_user_balance(user_id)
        if balance < price:
            await interaction.response.send_message(
                f"Insufficient balance. Need: {price} coins, Current: {balance} coins",
                ephemeral=True)
            return

        # Purchase process
        new_balance = balance - price
        await update_user_balance(user_id, new_balance)

        # Update stock (if not unlimited)
        if stock != -1:
            await db.execute(
                'UPDATE shop_items SET stock = stock - 1 WHERE id = ?',
                (item_id, ))

        await db.commit()

    embed = discord.Embed(title="✅ 購入完了", color=0x00ff00)
    embed.add_field(name="Item", value=name, inline=True)
    embed.add_field(name="Price", value=f"{price} coins", inline=True)
    embed.add_field(name="New Balance",
                    value=f"{new_balance} coins",
                    inline=False)

    await interaction.response.send_message(embed=embed)


# Admin add item command
@bot.tree.command(name="additem",
                  description="[Admin Only] Add a new item to the shop")
async def add_item(interaction: discord.Interaction,
                   item_name: str,
                   price: int,
                   description: str,
                   stock: int = -1):
    # Check admin permissions
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "This command is for administrators only.", ephemeral=True)
        return

    if price <= 0:
        await interaction.response.send_message("Price must be 1 or more.",
                                                ephemeral=True)
        return

    async with aiosqlite.connect('bot_database.db') as db:
        await db.execute(
            'INSERT INTO shop_items (name, price, description, stock) VALUES (?, ?, ?, ?)',
            (item_name, price, description, stock))
        await db.commit()

    embed = discord.Embed(title="✅ 商品追加完了", color=0x00ff00)
    embed.add_field(name="Item Name", value=item_name, inline=True)
    embed.add_field(name="Price", value=f"{price} coins", inline=True)
    embed.add_field(name="Description", value=description, inline=False)
    embed.add_field(name="Stock",
                    value="Unlimited" if stock == -1 else f"{stock}",
                    inline=True)

    await interaction.response.send_message(embed=embed)


# Admin remove item command
@bot.tree.command(name="removeitem",
                  description="[Admin Only] Remove an item from the shop")
async def remove_item(interaction: discord.Interaction, item_id: int):
    # 管理者権限チェック
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("このコマンドは管理者のみ使用できます。",
                                                ephemeral=True)
        return

    async with aiosqlite.connect('bot_database.db') as db:
        cursor = await db.execute('SELECT name FROM shop_items WHERE id = ?',
                                  (item_id, ))
        item = await cursor.fetchone()

        if not item:
            await interaction.response.send_message(
                "Item with specified ID not found.", ephemeral=True)
            return

        await db.execute('DELETE FROM shop_items WHERE id = ?', (item_id, ))
        await db.commit()

    embed = discord.Embed(title="✅ Item Removed", color=0xff0000)
    embed.add_field(name="Removed Item", value=item[0], inline=False)

    await interaction.response.send_message(embed=embed)


# Admin add money command
@bot.tree.command(name="addmoney",
                  description="[Admin Only] Add money to a user's balance")
async def add_money(interaction: discord.Interaction, user: discord.Member,
                    amount: int):
    # Check admin permissions
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "This command is for administrators only.", ephemeral=True)
        return

    if amount <= 0:
        await interaction.response.send_message(
            "Amount must be greater than 0.", ephemeral=True)
        return

    # Get current balance and add money
    current_balance = await get_user_balance(user.id)
    new_balance = current_balance + amount
    await update_user_balance(user.id, new_balance)

    embed = discord.Embed(title="💰 Money Added", color=0x00ff00)
    embed.add_field(name="User", value=user.mention, inline=True)
    embed.add_field(name="Amount Added", value=f"{amount} coins", inline=True)
    embed.add_field(name="New Balance",
                    value=f"{new_balance} coins",
                    inline=False)

    await interaction.response.send_message(embed=embed)


# Daily bonus command
@bot.tree.command(name="daily", description="Claim your daily bonus coins!")
async def daily_bonus(interaction: discord.Interaction):
    user_id = interaction.user.id
    today = datetime.now().date()
    daily_amount = 500  # Daily bonus amount

    async with aiosqlite.connect('bot_database.db') as db:
        # Check when user last claimed daily bonus
        cursor = await db.execute(
            'SELECT balance, last_daily FROM user_money WHERE user_id = ?',
            (user_id, ))
        result = await cursor.fetchone()

        if result is None:
            # New user - create entry and give bonus
            await db.execute(
                'INSERT INTO user_money (user_id, balance, last_daily) VALUES (?, ?, ?)',
                (user_id, 1000 + daily_amount, today))
            await db.commit()

            embed = discord.Embed(title="🎁 Daily Bonus!", color=0x00ff00)
            embed.add_field(name="Welcome Bonus",
                            value=f"+{daily_amount} coins",
                            inline=True)
            embed.add_field(name="New Balance",
                            value=f"{1000 + daily_amount} coins",
                            inline=True)
            embed.add_field(name="Next Claim", value="Tomorrow!", inline=False)

            await interaction.response.send_message(embed=embed)
            return

        balance, last_daily = result

        # Check if user already claimed today
        if last_daily:
            last_daily_date = datetime.strptime(last_daily, '%Y-%m-%d').date()
            if last_daily_date >= today:
                # Already claimed today
                next_claim = today + timedelta(days=1)
                embed = discord.Embed(title="⏰ Already Claimed",
                                      color=0xff9900)
                embed.add_field(
                    name="Status",
                    value="You already claimed your daily bonus today!",
                    inline=False)
                embed.add_field(name="Next Claim",
                                value=f"{next_claim.strftime('%Y-%m-%d')}",
                                inline=True)
                embed.add_field(name="Current Balance",
                                value=f"{balance} coins",
                                inline=True)

                await interaction.response.send_message(embed=embed,
                                                        ephemeral=True)
                return

        # Give daily bonus
        new_balance = balance + daily_amount
        await db.execute(
            'UPDATE user_money SET balance = ?, last_daily = ? WHERE user_id = ?',
            (new_balance, today, user_id))
        await db.commit()

    # Calculate streak bonus (optional)
    streak_bonus = 0
    if last_daily:
        last_daily_date = datetime.strptime(last_daily, '%Y-%m-%d').date()
        if (today - last_daily_date).days == 1:  # Consecutive day
            streak_bonus = 100
            new_balance += streak_bonus
            await update_user_balance(user_id, new_balance)

    embed = discord.Embed(title="🎁 Daily Bonus Claimed!", color=0x00ff00)
    embed.add_field(name="Daily Bonus",
                    value=f"+{daily_amount} coins",
                    inline=True)
    if streak_bonus > 0:
        embed.add_field(name="Streak Bonus",
                        value=f"+{streak_bonus} coins",
                        inline=True)
    embed.add_field(name="New Balance",
                    value=f"{new_balance} coins",
                    inline=False)
    embed.add_field(name="Next Claim", value="Tomorrow!", inline=True)

    await interaction.response.send_message(embed=embed)


# Admin add gacha role command
@bot.tree.command(name="addrole",
                  description="[Admin Only] Add a role to gacha system")
async def add_gacha_role(interaction: discord.Interaction,
                         role: discord.Role,
                         probability: float,
                         description: str = ""):
    # Check admin permissions
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "This command is for administrators only.", ephemeral=True)
        return

    if probability < 0.1 or probability > 100:
        await interaction.response.send_message(
            "Probability must be between 0.1 and 100.0", ephemeral=True)
        return

    async with aiosqlite.connect('bot_database.db') as db:
        # Check if role already exists
        cursor = await db.execute(
            'SELECT id FROM gacha_roles WHERE role_id = ?', (role.id, ))
        existing = await cursor.fetchone()

        if existing:
            await interaction.response.send_message(
                f"Role {role.mention} is already in gacha system!",
                ephemeral=True)
            return

        # Add role to gacha
        await db.execute(
            'INSERT INTO gacha_roles (role_id, role_name, probability, description) VALUES (?, ?, ?, ?)',
            (role.id, role.name, probability, description))
        await db.commit()

    embed = discord.Embed(title="🎲 Gacha Role Added", color=0x00ff00)
    embed.add_field(name="Role", value=role.mention, inline=True)
    embed.add_field(name="Probability", value=f"{probability}%", inline=True)
    embed.add_field(name="Description",
                    value=description or "No description",
                    inline=False)

    await interaction.response.send_message(embed=embed)


# Admin remove gacha role command
@bot.tree.command(name="removerole",
                  description="[Admin Only] Remove a role from gacha system")
async def remove_gacha_role(interaction: discord.Interaction,
                            role: discord.Role):
    # Check admin permissions
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "This command is for administrators only.", ephemeral=True)
        return

    async with aiosqlite.connect('bot_database.db') as db:
        cursor = await db.execute(
            'SELECT role_name FROM gacha_roles WHERE role_id = ?', (role.id, ))
        existing = await cursor.fetchone()

        if not existing:
            await interaction.response.send_message(
                f"Role {role.mention} is not in gacha system!", ephemeral=True)
            return

        await db.execute('DELETE FROM gacha_roles WHERE role_id = ?',
                         (role.id, ))
        await db.commit()

    embed = discord.Embed(title="🗑️ Gacha Role Removed", color=0xff0000)
    embed.add_field(name="Removed Role", value=role.mention, inline=False)

    await interaction.response.send_message(embed=embed)


# Gacha list command
@bot.tree.command(name="gachalist",
                  description="View all available gacha roles")
async def gacha_list(interaction: discord.Interaction):
    async with aiosqlite.connect('bot_database.db') as db:
        cursor = await db.execute(
            'SELECT role_id, role_name, probability, description FROM gacha_roles ORDER BY probability DESC'
        )
        roles = await cursor.fetchall()

    if not roles:
        await interaction.response.send_message("No gacha roles available.",
                                                ephemeral=True)
        return

    embed = discord.Embed(title="🎲 Role Gacha List", color=0x9932cc)

    for role_id, role_name, probability, description in roles:
        try:
            role = interaction.guild.get_role(role_id)
            role_display = role.mention if role else f"@{role_name} (Deleted)"
        except:
            role_display = f"@{role_name}"

        embed.add_field(
            name=f"{role_display}",
            value=
            f"**Probability:** {probability}%\n**Description:** {description or 'No description'}",
            inline=False)

    embed.add_field(
        name="How to play",
        value="Use /gacha to try your luck! Cost: 100 coins per roll",
        inline=False)

    await interaction.response.send_message(embed=embed)


# Role gacha command
@bot.tree.command(name="gacha", description="Try your luck at role gacha!")
async def role_gacha(interaction: discord.Interaction):
    user_id = interaction.user.id
    gacha_cost = 100  # Fixed cost per gacha roll

    async with aiosqlite.connect('bot_database.db') as db:
        # Get all gacha roles
        cursor = await db.execute(
            'SELECT role_id, role_name, probability, description FROM gacha_roles'
        )
        roles = await cursor.fetchall()

    if not roles:
        await interaction.response.send_message(
            "No gacha roles are currently available.", ephemeral=True)
        return

    # Check user balance
    balance = await get_user_balance(user_id)

    if balance < gacha_cost:
        await interaction.response.send_message(
            f"Insufficient balance! You need {gacha_cost} coins to play gacha.",
            ephemeral=True)
        return

    # Pay the gacha cost first
    new_balance = balance - gacha_cost
    await update_user_balance(user_id, new_balance)

    # Weighted random selection based on probability
    import random

    # Calculate total probability weight
    total_weight = sum(role[2] for role in roles)

    # Add "miss" chance if total probability < 100
    miss_chance = max(0, 100 - total_weight)

    # Generate random number
    rand = random.uniform(0, 100)
    current = 0

    selected_role = None
    for role_id, role_name, probability, description in roles:
        current += probability
        if rand <= current:
            selected_role = (role_id, role_name, probability, description)
            break

    # Check if it's a miss
    if selected_role is None or rand > (100 - miss_chance):
        embed = discord.Embed(title="💸 Gacha Result", color=0xff0000)
        embed.add_field(name="Result",
                        value="**MISS!** Better luck next time!",
                        inline=False)
        embed.add_field(name="Cost", value=f"{gacha_cost} coins", inline=True)
        embed.add_field(name="New Balance",
                        value=f"{new_balance} coins",
                        inline=True)

        await interaction.response.send_message(embed=embed)
        return

    # Success - give role (no additional cost)
    role_id, role_name, probability, description = selected_role

    try:
        role = interaction.guild.get_role(role_id)
        if role is None:
            await interaction.response.send_message(
                "Error: Role no longer exists on this server.", ephemeral=True)
            return

        # Check if user already has the role
        if role in interaction.user.roles:
            embed = discord.Embed(title="🔄 Duplicate Role", color=0xff9900)
            embed.add_field(name="Result",
                            value=f"You already have {role.mention}!",
                            inline=False)
            embed.add_field(name="Cost",
                            value=f"{gacha_cost} coins",
                            inline=True)
            embed.add_field(name="New Balance",
                            value=f"{new_balance} coins",
                            inline=True)

            await interaction.response.send_message(embed=embed)
            return

        # Give role to user
        await interaction.user.add_roles(role)

        embed = discord.Embed(title="🎉 Gacha Success!", color=0x00ff00)
        embed.add_field(name="Congratulations!",
                        value=f"You won {role.mention}!",
                        inline=False)
        embed.add_field(name="Probability",
                        value=f"{probability}%",
                        inline=True)
        embed.add_field(name="Cost", value=f"{gacha_cost} coins", inline=True)
        embed.add_field(name="New Balance",
                        value=f"{new_balance} coins",
                        inline=False)

        await interaction.response.send_message(embed=embed)

    except discord.Forbidden:
        await interaction.response.send_message(
            "Error: Bot doesn't have permission to assign roles.",
            ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"Error occurred: {str(e)}",
                                                ephemeral=True)


# Leaderboard command
@bot.tree.command(name="leaderboard",
                  description="View the top 10 richest users")
async def leaderboard(interaction: discord.Interaction):
    async with aiosqlite.connect('bot_database.db') as db:
        # Get top 10 users by balance
        cursor = await db.execute('''
            SELECT user_id, balance 
            FROM users 
            WHERE balance > 0 
            ORDER BY balance DESC 
            LIMIT 10
        ''')
        top_users = await cursor.fetchall()

    if not top_users:
        await interaction.response.send_message(
            "No users with positive balance found.", ephemeral=True)
        return

    embed = discord.Embed(title="💰 Wealth Leaderboard", color=0xffd700)
    embed.set_footer(text="Top 10 Richest Users")

    for i, (user_id, balance) in enumerate(top_users, 1):
        try:
            user = bot.get_user(user_id) or await bot.fetch_user(user_id)
            username = user.display_name if user else f"Unknown User ({user_id})"
        except:
            username = f"Unknown User ({user_id})"

        # Medal emojis for top 3
        if i == 1:
            rank_emoji = "🥇"
        elif i == 2:
            rank_emoji = "🥈"
        elif i == 3:
            rank_emoji = "🥉"
        else:
            rank_emoji = f"{i}."

        embed.add_field(name=f"{rank_emoji} {username}",
                        value=f"{balance:,} coins",
                        inline=False)

    await interaction.response.send_message(embed=embed)


# ボット起動
if __name__ == "__main__":
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        print("DISCORD_TOKEN が設定されていません。.env ファイルまたは環境変数を確認してください。")
    else:
        asyncio.run(init_db())
        bot.run(token)
