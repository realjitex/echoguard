import discord
from discord import app_commands
from discord.ext import commands
import os
import asyncio

# ============================================================
TOKEN = ""

# ============================================================
# ЦВЕТА
# ============================================================
COLOR_DARK = 0xB35ADD


# ============================================================
# БОТ
# ============================================================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)


# ============================================================
# ID РОЛЕЙ
# ============================================================
ROLE_ACCEPT_ID = 1535601375713689640
ROLE_BLACKLIST_ID = 1535646004668403723

ROLE_NEWS_ID = 1535652271315222618
ROLE_TECH_NEWS_ID = 1535652277468274748
ROLE_CONTENT_ID = 1535652280630644766

ALLOWED_ADMIN_IDS = [
    1535594782812930181,
    1535596345539305492,
    1535600640116391986,
]

TICKET_LOG_CHANNEL_ID = 1542201821089628260

# ID ролей, которые могут управлять тикетами (смотреть и нажимать кнопки)
STAFF_ROLE_IDS = [
    1535601356176359454,
    1535596398609833994,
    1535596415856672808,
    1535601347624308736,
    1535600640116391986,
    1535596345539305492,
    1535594782812930181,
]

# ID категорий для тикетов
CATEGORY_APPLICATIONS_ID = 1535994523262394368  # Заявки на сервер
CATEGORY_SUPPORT_ID = 1535977372782698506         # Поддержка / Идеи
CATEGORY_TEAM_ID = 1535977753931685940            # Набор в команду
CATEGORY_COURT_ID = 1537489712082591854            # Суд

# ID ролей, которые могут управлять тикетами команды
TEAM_STAFF_ROLE_IDS = [
    1535596415856672808,
    1535601347624308736,
    1535600640116391986,
    1535596345539305492,
    1535594782812930181,
]


# ============================================================
# МОДАЛКА — ФОРМА ЗАЯВКИ
# ============================================================
class ServerApplicationModal(discord.ui.Modal, title="📝 Заявка на сервер Эхо Бездны"):
    nickname = discord.ui.TextInput(label="Никнейм", style=discord.TextStyle.short, required=True, max_length=50)
    age = discord.ui.TextInput(label="Возраст", style=discord.TextStyle.short, required=True, max_length=3)
    gender = discord.ui.TextInput(label="Пол (М или Д)", style=discord.TextStyle.short, required=True, max_length=1)
    where_from = discord.ui.TextInput(label="Откуда узнали?", style=discord.TextStyle.long, required=True, max_length=500)
    about = discord.ui.TextInput(label="О себе", style=discord.TextStyle.long, required=True, max_length=1000)

    async def on_submit(self, interaction: discord.Interaction):
        if not MC_NAME.fullmatch(self.nickname.value.strip()):
            await interaction.response.send_message("Ник Minecraft: 3–16 латинских букв, цифр или подчёркиваний.", ephemeral=True)
            return
        # Проверка на дубликат тикета
        category = interaction.guild.get_channel(CATEGORY_APPLICATIONS_ID)
        if category and isinstance(category, discord.CategoryChannel):
            for ch in category.text_channels:
                if ch.name == f"заявка-{interaction.user.name}":
                    await interaction.response.send_message(
                        f"❌ У вас уже есть открытая заявка! {ch.mention}", ephemeral=True
                    )
                    return

        await interaction.response.defer(ephemeral=True, thinking=True)

        gender_input = self.gender.value.upper().strip()
        if gender_input in ["М", "M"]:
            gender_text = "Мальчик ♂️"
        elif gender_input in ["Д", "D"]:
            gender_text = "Девочка ♀️"
        else:
            gender_text = self.gender.value

        guild = interaction.guild
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
        }

        for role_id in STAFF_ROLE_IDS:
            role = guild.get_role(role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True)

        # Добавляем админов для просмотра тикетов
        for admin_id in ALLOWED_ADMIN_IDS:
            admin_member = guild.get_member(admin_id)
            if admin_member:
                overwrites[admin_member] = discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True)

        category = interaction.guild.get_channel(CATEGORY_APPLICATIONS_ID)
        if not category or not isinstance(category, discord.CategoryChannel):
            await interaction.followup.send("❌ Категория для заявок не найдена!", ephemeral=True)
            return

        ticket_channel = await guild.create_text_channel(
            name=f"заявка-{interaction.user.name}", category=category, overwrites=overwrites
        )

        # Сохраняем никнейм в тему канала для использования при принятии заявки
        await ticket_channel.edit(topic=f"NICK:{self.nickname.value.strip()}|OWNER:{interaction.user.id}")

        guard.store.execute("INSERT OR REPLACE INTO tickets VALUES (?,?,?)", (str(ticket_channel.id), str(interaction.user.id), self.nickname.value.strip()))

        ticket_embed = discord.Embed(
            title=f"📋 Заявка от {self.nickname.value}",
            description=(
                f"**Никнейм:** {self.nickname.value}\n"
                f"**Возраст:** {self.age.value}\n"
                f"**Пол:** {gender_text}\n"
                f"**Откуда узнали:** {self.where_from.value}\n\n"
                f"**О себе:**\n{self.about.value}\n\n"
                "---\n⏳ *Ожидайте проверки администратором.*"
            ),
            color=COLOR_DARK,
        )
        ticket_embed.set_footer(text="Эхо Бездны — приватный Minecraft сервер", icon_url="attachment://Logo.png")

        close_view = TicketActionsView()
        logo_path = os.path.join(os.path.dirname(__file__), "Logo.png")
        if os.path.exists(logo_path):
            logo_file = discord.File(logo_path, filename="Logo.png")
            await ticket_channel.send(embed=ticket_embed, view=close_view, file=logo_file)
        else:
            await ticket_channel.send(embed=ticket_embed, view=close_view)

        await interaction.followup.send(
            f"✅ Ваша заявка создана! Перейдите в {ticket_channel.mention}", ephemeral=True
        )

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        import traceback
        traceback.print_exc()
        try:
            await interaction.response.send_message(f"❌ Ошибка: {error}", ephemeral=True)
        except:
            await interaction.followup.send(f"❌ Ошибка: {error}", ephemeral=True)


# ============================================================
# КНОПКИ УПРАВЛЕНИЯ ТИКЕТОМ
# ============================================================
class TicketActionsView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    def is_staff(self, member: discord.Member) -> bool:
        """Проверяет, есть ли у участника хотя бы одна из ролей staff."""
        if member.guild_permissions.administrator:
            return True
        return any(role.id in STAFF_ROLE_IDS for role in member.roles)

    @discord.ui.button(label="Принять", style=discord.ButtonStyle.success, emoji="✅", custom_id="ticket_accept_v1")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        await accept_application(interaction, self)

    @discord.ui.button(label="Отклонить", style=discord.ButtonStyle.danger, emoji="❌", custom_id="ticket_decline_v1")
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.channel_id in guard.ticket_busy:
            await interaction.response.send_message("⏳ Заявка уже обрабатывается.", ephemeral=True)
            return
        member, name = ticket_identity(interaction.channel, interaction.guild)
        pending = guard.store.one("SELECT id FROM commands WHERE name=? COLLATE NOCASE AND state='pending'", (name,))
        owner = guard.store.one("SELECT active FROM owners WHERE name=?", (name,))
        if pending or (owner and owner['active']):
            await interaction.response.send_message("⚠️ Для этой заявки уже запущено добавление в Minecraft. Завершите «Принять». Для отзыва доступа используйте whitelist remove в консоли сервера; эта кнопка не отменяет выполненное принятие.", ephemeral=True)
            return
        guard.ticket_busy.add(interaction.channel_id)
        async def perform():
            if not self.is_staff(interaction.user):
                await interaction.response.send_message("❌ У вас нет прав.", ephemeral=True)
                return
            await interaction.response.send_message("🔒 Заявка **отклонена**.")
    
            # Личное сообщение пользователю
            channel_name = interaction.channel.name
            if channel_name.startswith("заявка-"):
                username = channel_name.replace("заявка-", "")
                member = ticket_identity(interaction.channel, interaction.guild)[0]
                if member:
                    try:
                        await member.send(":x: **Ваша заявка была отклонена!**")
                    except discord.Forbidden:
                        pass
    
            try:
                await log_ticket_close(interaction.channel, interaction.guild, "Заявка отклонена", interaction.user)
            except Exception as e:
                print(f"⚠️ Ошибка логирования тикета: {e}")
                await interaction.followup.send("Архивирование не удалось; тикет оставлен открытым.", ephemeral=True)
                return
            await asyncio.sleep(5)
            try:
                await interaction.channel.delete(reason="Заявка отклонена")
            except Exception as e:
                print(f"⚠️ Ошибка удаления канала: {e}")
        try:
            await perform()
        finally:
            guard.ticket_busy.discard(interaction.channel_id)

    @discord.ui.button(label="Blacklist", style=discord.ButtonStyle.secondary, emoji="🚫", custom_id="ticket_blacklist_v1")
    async def blacklist(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.channel_id in guard.ticket_busy:
            await interaction.response.send_message("⏳ Заявка уже обрабатывается.", ephemeral=True)
            return
        member, name = ticket_identity(interaction.channel, interaction.guild)
        pending = guard.store.one("SELECT id FROM commands WHERE name=? COLLATE NOCASE AND state='pending'", (name,))
        owner = guard.store.one("SELECT active FROM owners WHERE name=?", (name,))
        if pending or (owner and owner['active']):
            await interaction.response.send_message("⚠️ Для этой заявки уже запущено добавление в Minecraft. Завершите «Принять». Для отзыва доступа используйте whitelist remove в консоли сервера; эта кнопка не отменяет выполненное принятие.", ephemeral=True)
            return
        guard.ticket_busy.add(interaction.channel_id)
        async def perform():
            if not self.is_staff(interaction.user):
                await interaction.response.send_message("❌ У вас нет прав.", ephemeral=True)
                return
    
            channel_name = interaction.channel.name
            if channel_name.startswith("заявка-"):
                username = channel_name.replace("заявка-", "")
                member = ticket_identity(interaction.channel, interaction.guild)[0]
                if member:
                    role = interaction.guild.get_role(ROLE_BLACKLIST_ID)
                    if not role:
                        role = discord.utils.get(interaction.guild.roles, name="Blacklist")
                    if role:
                        await member.add_roles(role)
                        await interaction.response.send_message(
                            f"🚫 {member.mention} добавлен в **чёрный список**."
                        )
                    else:
                        await interaction.response.send_message("⚠️ Роль 'Blacklist' не найдена!")
                        return
    
            # Личное сообщение пользователю
            if channel_name.startswith("заявка-"):
                username = channel_name.replace("заявка-", "")
                member_check = ticket_identity(interaction.channel, interaction.guild)[0]
                if member_check:
                    try:
                        await member_check.send(":no_entry: **Вы были внесены в чёрный список проекта!**")
                    except discord.Forbidden:
                        pass
    
            try:
                await log_ticket_close(interaction.channel, interaction.guild, "Blacklist", interaction.user)
            except Exception as e:
                print(f"⚠️ Ошибка логирования тикета: {e}")
                await interaction.followup.send("Архивирование не удалось; тикет оставлен открытым.", ephemeral=True)
                return
            await asyncio.sleep(5)
            try:
                await interaction.channel.delete(reason="Blacklist")
            except Exception as e:
                print(f"⚠️ Ошибка удаления канала: {e}")
        try:
            await perform()
        finally:
            guard.ticket_busy.discard(interaction.channel_id)



# ============================================================
# КОНТЕЙНЕР ЗАЯВКИ (Components V2)
# ============================================================
class ApplicationContainer(discord.ui.Container):
    def __init__(self):
        super().__init__(accent_color=0xB35ADD)

    action_row = discord.ui.ActionRow()

    @action_row.button(
        label="Подать заявку",
        style=discord.ButtonStyle.secondary,
        emoji="📩",
        custom_id="apply_to_server_v12"
    )
    async def apply_to_server(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ServerApplicationModal())


# ============================================================
# ВЫБОР КАТЕГОРИИ ПОДДЕРЖКИ
# ============================================================
class SupportSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.select(
        placeholder="Выберите категорию...",
        options=[
            discord.SelectOption(label="Проблемы с оплатой", description="Покупка проходки/плюса", emoji="💰", value="оплата"),
            discord.SelectOption(label="Связь с администрацией", description="Связаться с администрацией", emoji="⚠️", value="связь"),
            discord.SelectOption(label="Жалоба", description="Подать жалобу", emoji="🚫", value="жалоба"),
            discord.SelectOption(label="Техническая поддержка", description="Тех. помощь", emoji="🔧", value="техподдержка"),
        ],
        custom_id="support_select_v1"
    )
    async def support_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        category_labels = {
            "оплата": "Проблемы с оплатой",
            "связь": "Связь с администрацией",
            "жалоба": "Жалоба",
            "техподдержка": "Техническая поддержка",
        }
        selected = select.values[0]
        label = category_labels.get(selected, selected)

        guild = interaction.guild
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
        }

        # Добавляем роли staff для просмотра и управления тикетами
        for role_id in STAFF_ROLE_IDS:
            role = guild.get_role(role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True)

        # Добавляем админов для просмотра тикетов
        for admin_id in ALLOWED_ADMIN_IDS:
            admin_member = guild.get_member(admin_id)
            if admin_member:
                overwrites[admin_member] = discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True)

        category = guild.get_channel(CATEGORY_SUPPORT_ID)
        if not category or not isinstance(category, discord.CategoryChannel):
            await interaction.response.send_message("❌ Категория для поддержки не найдена!", ephemeral=True)
            return

        ticket_channel = await guild.create_text_channel(
            name=f"{selected}-{interaction.user.name}", category=category, overwrites=overwrites
        )

        support_embed = discord.Embed(
            title=f"💬 {label}",
            description=(
                f"Здравствуйте, {interaction.user.mention}!\n\n"
                "**Опишите вашу проблему** подробно и ожидайте ответа администратора.\n\n"
                "-# Среднее время ответа: 10-30 минут"
            ),
            color=COLOR_DARK,
        )
        support_embed.set_footer(text="Эхо Бездны — приватный Minecraft сервер", icon_url="attachment://Logo.png")

        # Тикеты поддержки с кнопками: Взять на рассмотрение + Закрыть
        support_view = SupportTicketView()
        logo_path = os.path.join(os.path.dirname(__file__), "Logo.png")
        if os.path.exists(logo_path):
            logo_file = discord.File(logo_path, filename="Logo.png")
            await ticket_channel.send(embed=support_embed, view=support_view, file=logo_file)
        else:
            await ticket_channel.send(embed=support_embed, view=support_view)

        await interaction.response.send_message(
            f"✅ Тикет создан! Перейдите в {ticket_channel.mention}", ephemeral=True
        )


# ============================================================
# КНОПКИ ТИКЕТА ПОДДЕРЖКИ
# ============================================================
class SupportTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    def is_staff(self, member: discord.Member) -> bool:
        """Проверяет, есть ли у участника хотя бы одна из ролей staff."""
        if member.guild_permissions.administrator:
            return True
        return any(role.id in STAFF_ROLE_IDS for role in member.roles)

    @discord.ui.button(
        label="Взять на рассмотрение",
        style=discord.ButtonStyle.primary,
        emoji="👀",
        custom_id="support_take_v1"
    )
    async def take_for_review(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_staff(interaction.user):
            await interaction.response.send_message("❌ У вас нет прав.", ephemeral=True)
            return

        await interaction.response.send_message(
            f"👀 **{interaction.user.mention}** взял тикет на рассмотрение!"
        )

    @discord.ui.button(
        label="Закрыть",
        style=discord.ButtonStyle.danger,
        emoji="🔒",
        custom_id="support_close_v1"
    )
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_staff(interaction.user):
            await interaction.response.send_message("❌ У вас нет прав.", ephemeral=True)
            return

        await interaction.response.send_message("🔒 Тикет закрыт.")
        try:
            await log_ticket_close(interaction.channel, interaction.guild, "Тикет закрыт", interaction.user)
        except Exception as e:
            print(f"⚠️ Ошибка логирования тикета: {e}")
        await asyncio.sleep(3)
        try:
            await interaction.channel.delete(reason="Тикет закрыт")
        except Exception as e:
            print(f"⚠️ Ошибка удаления канала: {e}")


# ============================================================
# КНОПКИ ТИКЕТА КОМАНДЫ
# ============================================================
class TeamTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    def is_team_staff(self, member: discord.Member) -> bool:
        """Проверяет, есть ли у участника хотя бы одна из ролей team staff."""
        if member.guild_permissions.administrator:
            return True
        return any(role.id in TEAM_STAFF_ROLE_IDS for role in member.roles)

    @discord.ui.button(
        label="Взять на рассмотрение",
        style=discord.ButtonStyle.primary,
        emoji="👀",
        custom_id="team_take_v1"
    )
    async def take_for_review(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_team_staff(interaction.user):
            await interaction.response.send_message("❌ У вас нет прав.", ephemeral=True)
            return

        await interaction.response.send_message(
            f"👀 **{interaction.user.mention}** взял тикет на рассмотрение!"
        )

    @discord.ui.button(
        label="Закрыть",
        style=discord.ButtonStyle.danger,
        emoji="🔒",
        custom_id="team_close_v1"
    )
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_team_staff(interaction.user):
            await interaction.response.send_message("❌ У вас нет прав.", ephemeral=True)
            return

        await interaction.response.send_message("🔒 Тикет закрыт.")
        try:
            await log_ticket_close(interaction.channel, interaction.guild, "Тикет закрыт", interaction.user)
        except Exception as e:
            print(f"⚠️ Ошибка логирования тикета: {e}")
        await asyncio.sleep(3)
        try:
            await interaction.channel.delete(reason="Тикет закрыт")
        except Exception as e:
            print(f"⚠️ Ошибка удаления канала: {e}")


# ============================================================
# ЛОГИРОВАНИЕ ТИКЕТОВ
# ============================================================
async def log_ticket_close(channel: discord.TextChannel, guild: discord.Guild, action: str, staff: discord.Member):
    """Сохраняет лог закрытия тикета в канал логов."""
    import io
    log_channel = guild.get_channel(TICKET_LOG_CHANNEL_ID)
    if not log_channel:
        raise RuntimeError("Канал логов недоступен; тикет сохранён")
    lines = []
    async for msg in channel.history(limit=None, oldest_first=True):
        lines.append(f"[{msg.created_at.isoformat()}] {msg.author} ({msg.author.id}): {msg.content}")
        for embed in msg.embeds:
            lines.append(json.dumps(embed.to_dict(), ensure_ascii=False))
        for attachment in msg.attachments:
            lines.append(f"Вложение: {attachment.filename} {attachment.url}")
    data = "\n".join(lines).encode("utf-8")
    if len(data) > 8_000_000:
        raise RuntimeError("Транскрипт больше 8 MB; сохраните вручную перед закрытием")
    await log_channel.send(
        embed=discord.Embed(title=f"📋 {channel.name}",
                            description=f"**Действие:** {action}\n**Администратор:** {staff.mention}\n**ID канала:** {channel.id}",
                            color=COLOR_DARK),
        file=discord.File(io.BytesIO(data), filename=f"ticket-{channel.id}.txt"),
        allowed_mentions=discord.AllowedMentions.none())


# ============================================================
# МОДАЛКА — ФОРМА ИСКА В СУД
# ============================================================
class CourtModal(discord.ui.Modal, title="⚖️ Подать в суд"):
    offender = discord.ui.TextInput(
        label="Ник нарушителя",
        style=discord.TextStyle.short,
        placeholder="Введите никнейм нарушителя...",
        required=True,
        max_length=50,
    )
    what_happened = discord.ui.TextInput(
        label="Что произошло",
        style=discord.TextStyle.long,
        placeholder="Подробно опишите ситуацию...",
        required=True,
        max_length=1000,
    )
    demand = discord.ui.TextInput(
        label="Ваше требование",
        style=discord.TextStyle.long,
        placeholder="Чего вы хотите добиться?..",
        required=True,
        max_length=500,
    )

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
        }

        for role_id in STAFF_ROLE_IDS:
            role = guild.get_role(role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True)

        for admin_id in ALLOWED_ADMIN_IDS:
            admin_member = guild.get_member(admin_id)
            if admin_member:
                overwrites[admin_member] = discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True)

        category = guild.get_channel(CATEGORY_COURT_ID)
        if not category or not isinstance(category, discord.CategoryChannel):
            await interaction.response.send_message("❌ Категория для суда не найдена!", ephemeral=True)
            return

        ticket_channel = await guild.create_text_channel(
            name=f"суд-{interaction.user.name}", category=category, overwrites=overwrites
        )

        ticket_embed = discord.Embed(
            title=f"⚖️ Суд — {self.offender.value}",
            description=(
                f"**Истец:** {interaction.user.mention}\n"
                f"**Нарушитель:** {self.offender.value}\n\n"
                f"**Что произошло:**\n{self.what_happened.value}\n\n"
                f"**Требование:**\n{self.demand.value}\n\n"
                "---\n⏳ *Ожидайте разбирательства.*"
            ),
            color=COLOR_DARK,
        )
        ticket_embed.set_footer(text="Эхо Бездны — приватный Minecraft сервер", icon_url="attachment://Logo.png")

        court_view = SupportTicketView()
        logo_path = os.path.join(os.path.dirname(__file__), "Logo.png")
        if os.path.exists(logo_path):
            logo_file = discord.File(logo_path, filename="Logo.png")
            await ticket_channel.send(embed=ticket_embed, view=court_view, file=logo_file)
        else:
            await ticket_channel.send(embed=ticket_embed, view=court_view)

        await interaction.response.send_message(
            f"✅ Иск подан! Перейдите в {ticket_channel.mention}", ephemeral=True
        )

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        import traceback
        traceback.print_exc()
        try:
            await interaction.response.send_message(f"❌ Ошибка: {error}", ephemeral=True)
        except:
            await interaction.followup.send(f"❌ Ошибка: {error}", ephemeral=True)


# ============================================================
# МОДАЛКА — ФОРМА ПОДАЧИ ИДЕИ
# ============================================================
class IdeaModal(discord.ui.Modal, title="💡 Подать идею"):
    idea = discord.ui.TextInput(
        label="Опишите предложение",
        style=discord.TextStyle.long,
        placeholder="Расскажите о вашей идее для сервера...",
        required=True,
        max_length=1000,
    )

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
        }

        for role_id in STAFF_ROLE_IDS:
            role = guild.get_role(role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True)

        for admin_id in ALLOWED_ADMIN_IDS:
            admin_member = guild.get_member(admin_id)
            if admin_member:
                overwrites[admin_member] = discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True)

        category = guild.get_channel(CATEGORY_SUPPORT_ID)
        if not category or not isinstance(category, discord.CategoryChannel):
            await interaction.response.send_message("❌ Категория для идей не найдена!", ephemeral=True)
            return

        ticket_channel = await guild.create_text_channel(
            name=f"идея-{interaction.user.name}", category=category, overwrites=overwrites
        )

        ticket_embed = discord.Embed(
            title=f"💡 Идея от {interaction.user.display_name}",
            description=(
                f"**Автор:** {interaction.user.mention}\n\n"
                f"**Предложение:**\n{self.idea.value}\n\n"
                "---\n⏳ *Ожидайте рассмотрения администратором.*"
            ),
            color=COLOR_DARK,
        )
        ticket_embed.set_footer(text="Эхо Бездны — приватный Minecraft сервер", icon_url="attachment://Logo.png")

        idea_view = SupportTicketView()
        logo_path = os.path.join(os.path.dirname(__file__), "Logo.png")
        if os.path.exists(logo_path):
            logo_file = discord.File(logo_path, filename="Logo.png")
            await ticket_channel.send(embed=ticket_embed, view=idea_view, file=logo_file)
        else:
            await ticket_channel.send(embed=ticket_embed, view=idea_view)

        await interaction.response.send_message(
            f"✅ Идея отправлена! Перейдите в {ticket_channel.mention}", ephemeral=True
        )

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        import traceback
        traceback.print_exc()
        try:
            await interaction.response.send_message(f"❌ Ошибка: {error}", ephemeral=True)
        except:
            await interaction.followup.send(f"❌ Ошибка: {error}", ephemeral=True)


# ============================================================
# ВЫБОР КАТЕГОРИИ — СУД И ИДЕИ
# ============================================================
class CourtSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.select(
        placeholder="Выберите категорию...",
        options=[
            discord.SelectOption(label="Подать идею", description="Предложить идею для сервера", emoji="💡", value="idea"),
            discord.SelectOption(label="Подать в суд", description="Подать жалобу/иск", emoji="⚖️", value="court"),
        ],
        custom_id="court_select_v1"
    )
    async def court_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        selected = select.values[0]
        if selected == "idea":
            await interaction.response.send_modal(IdeaModal())
        elif selected == "court":
            await interaction.response.send_modal(CourtModal())


# ============================================================
# КОНТЕЙНЕР УВЕДОМЛЕНИЙ (Components V2) — ОДИН КОНТЕЙНЕР
# ============================================================
class NotificationsPanelContainer(discord.ui.Container):
    """Один контейнер со всеми уведомлениями и кнопками внутри."""

    def __init__(self):
        super().__init__(accent_color=0xB35ADD)

    # Кнопка новостей
    news_row = discord.ui.ActionRow()

    @news_row.button(label="Переключить уведомления", style=discord.ButtonStyle.secondary, custom_id="toggle_news_v8")
    async def toggle_news(self, interaction: discord.Interaction, button: discord.ui.Button):
        role = interaction.guild.get_role(ROLE_NEWS_ID)
        if role in interaction.user.roles:
            await interaction.user.remove_roles(role)
            await interaction.response.send_message("❌ Роль **Новости** убрана.", ephemeral=True)
        else:
            await interaction.user.add_roles(role)
            await interaction.response.send_message("✅ Роль **Новости** выдана!", ephemeral=True)

    # Кнопка тех-новостей
    tech_row = discord.ui.ActionRow()

    @tech_row.button(label="Переключить уведомления", style=discord.ButtonStyle.secondary, custom_id="toggle_tech_v8")
    async def toggle_tech(self, interaction: discord.Interaction, button: discord.ui.Button):
        role = interaction.guild.get_role(ROLE_TECH_NEWS_ID)
        if role in interaction.user.roles:
            await interaction.user.remove_roles(role)
            await interaction.response.send_message("❌ Роль **Тех-новости** убрана.", ephemeral=True)
        else:
            await interaction.user.add_roles(role)
            await interaction.response.send_message("✅ Роль **Тех-новости** выдана!", ephemeral=True)

    # Кнопка контента
    content_row = discord.ui.ActionRow()

    @content_row.button(label="Переключить уведомления", style=discord.ButtonStyle.secondary, custom_id="toggle_content_v8")
    async def toggle_content(self, interaction: discord.Interaction, button: discord.ui.Button):
        role = interaction.guild.get_role(ROLE_CONTENT_ID)
        if role in interaction.user.roles:
            await interaction.user.remove_roles(role)
            await interaction.response.send_message("❌ Роль **Контент** убрана.", ephemeral=True)
        else:
            await interaction.user.add_roles(role)
            await interaction.response.send_message("✅ Роль **Контент** выдана!", ephemeral=True)


# ============================================================
# ПАНЕЛЬ ПОДДЕРЖКИ (ОДИН КОНТЕЙНЕР)
# ============================================================
async def send_support_panel(channel: discord.TextChannel):
    view = discord.ui.LayoutView(timeout=None)
    container = discord.ui.Container(accent_color=0xB35ADD)

    banner_path = os.path.join(os.path.dirname(__file__), "feedback.png")
    banner_file = None
    if os.path.exists(banner_path):
        banner_file = discord.File(banner_path, filename="feedback.png")
        media = discord.ui.MediaGallery()
        media.add_item(media="attachment://feedback.png")
        container.add_item(media)

    container.add_item(discord.ui.TextDisplay("## 👥 **Поддержка**"))
    container.add_item(discord.ui.Separator())
    container.add_item(discord.ui.TextDisplay("**Все вопросы и проблемы** решаются через систему тикетов."))
    container.add_item(discord.ui.Separator())
    container.add_item(discord.ui.TextDisplay(
        "**🧩 Виды поддержки:**\n"
        "> ・ Проблема с оплатой\n"
        "> ・ Связь с поддержкой\n"
        "> ・ Жалобы и нарушения\n"
        "> ・ Техническая поддержка"
    ))
    container.add_item(discord.ui.Separator())
    container.add_item(discord.ui.TextDisplay(
        "**🔍 Перед открытием**\n"
        "Ознакомьтесь с <#1535849701490827304> — возможно, ответ уже есть."
    ))
    view.add_item(container)

    logo_path = os.path.join(os.path.dirname(__file__), "Logo.png")
    logo_file = None
    if os.path.exists(logo_path):
        logo_file = discord.File(logo_path, filename="Logo.png")

    files = [f for f in [banner_file, logo_file] if f is not None]
    if files:
        await channel.send(view=view, files=files)
    else:
        await channel.send(view=view)

    # Select Menu отдельным сообщением
    await channel.send(view=SupportSelectView())


# ============================================================
# ПАНЕЛЬ ЗАЯВОК (ОДИН КОНТЕЙНЕР — Components V2)
# ============================================================
async def send_panel(channel: discord.TextChannel):
    view = discord.ui.LayoutView(timeout=None)
    container = ApplicationContainer()

    # Находим кнопку "Подать заявку"
    action_row = None
    for item in container._children:
        if isinstance(item, discord.ui.ActionRow):
            action_row = item
            break

    # Баннер
    banner_path = os.path.join(os.path.dirname(__file__), "application.png")
    banner_file = None
    if os.path.exists(banner_path):
        banner_file = discord.File(banner_path, filename="application.png")
        media = discord.ui.MediaGallery()
        media.add_item(media="attachment://application.png")
        container.add_item(media)

    # Блок 1: Заявка
    container.add_item(discord.ui.TextDisplay("## 🎮 **Подать заявку на сервер**"))
    container.add_item(discord.ui.Separator())
    container.add_item(discord.ui.TextDisplay(
        "> Наш сервер **является приватным** — мы тщательно отбираем участников, "
        "чтобы **сохранить дружескую** и безопасную **атмосферу**. "
        "Уделите заполнению заявки **максимальное внимание**, ведь она — "
        "**первое впечатление о вас**!"
    ))
    container.add_item(discord.ui.Separator())
    if action_row:
        container._children.remove(action_row)
        container._children.append(action_row)

    # Блок 2: Проходка
    container.add_item(discord.ui.TextDisplay("## 🛒 **Приобрести проходку**"))
    container.add_item(discord.ui.Separator())
    container.add_item(discord.ui.TextDisplay(
        "> Если вы не хотите ждать рассмотрения заявки, **вы можете приобрести** "
        "проходку на сервер **за 200 рублей**. Для этого перейдите в "
        "[магазин сервера](https://ehobezdni.cdonate.ru/), ознакомьтесь с товаром "
        "и следуйте инструкциям для оплаты."
    ))
    container.add_item(discord.ui.Separator())

    shop_row = discord.ui.ActionRow()
    shop_button = discord.ui.Button(
        label="Приобрести проходку",
        style=discord.ButtonStyle.link,
        emoji="💳",
        url="https://ehobezdni.cdonate.ru/"
    )
    shop_row.add_item(shop_button)
    container.add_item(shop_row)

    # Блок 3: Важное
    container.add_item(discord.ui.TextDisplay("## ❗**Важные моменты:**"))
    container.add_item(discord.ui.Separator())
    container.add_item(discord.ui.TextDisplay(
        "> **1**. Заявку можно подать **лишь раз в неделю**.\n"
        "> **2**. **Не пишите** администраторам о статусе заявки. "
        "Проверка проходит с **00:00 по 17:00** каждый день по Московскому времени.\n"
        "> **3**. Развёрнутые вопросы **требуют** полных и **осмысленных** ответов. "
        "**Краткие** или шаблонные заявки отклоняются."
    ))
    container.add_item(discord.ui.Separator())
    container.add_item(discord.ui.TextDisplay(
        "-# *Надеемся, ваша заявка станет началом долгого, и увлекательного путешествия на Эхо Бездны.*"
    ))

    view.add_item(container)

    logo_path = os.path.join(os.path.dirname(__file__), "Logo.png")
    logo_file = None
    if os.path.exists(logo_path):
        logo_file = discord.File(logo_path, filename="Logo.png")

    files = [f for f in [banner_file, logo_file] if f is not None]
    if files:
        await channel.send(view=view, files=files)
    else:
        await channel.send(view=view)


# ============================================================
# ПАНЕЛЬ УВЕДОМЛЕНИЙ (ОДИН КОНТЕЙНЕР — Components V2)
# ============================================================
async def send_notifications_panel(channel: discord.TextChannel):
    """Отправляет панель уведомлений — ОДИН контейнер, всё внутри."""

    view = discord.ui.LayoutView(timeout=None)
    container = NotificationsPanelContainer()

    # Находим кнопки по custom_id
    news_row = None
    tech_row = None
    content_row = None
    for item in container._children:
        if isinstance(item, discord.ui.ActionRow):
            for child in item.children:
                if hasattr(child, 'custom_id'):
                    if child.custom_id == "toggle_news_v8":
                        news_row = item
                    elif child.custom_id == "toggle_tech_v8":
                        tech_row = item
                    elif child.custom_id == "toggle_content_v8":
                        content_row = item

    # Заголовок
    container.add_item(discord.ui.TextDisplay("## 📢 **УВЕДОМЛЕНИЯ**"))
    container.add_item(discord.ui.Separator())
    container.add_item(discord.ui.TextDisplay(
        "Выберите, какие уведомления вы хотите получать. "
        "Нажмите, чтобы **включить** — нажмите ещё раз, чтобы **выключить**."
    ))
    container.add_item(discord.ui.Separator())

    # Новости
    container.add_item(discord.ui.TextDisplay("### 📰 **Новости**"))
    container.add_item(discord.ui.TextDisplay("Узнавайте первыми о новостях сервера и его ивентах."))
    if news_row:
        container._children.remove(news_row)
        container._children.append(news_row)
    container.add_item(discord.ui.Separator())

    # Тех-новости
    container.add_item(discord.ui.TextDisplay("### 🛠️ **Тех-новости**"))
    container.add_item(discord.ui.TextDisplay("Следите за обновлениями и изменениями на сервере."))
    if tech_row:
        container._children.remove(tech_row)
        container._children.append(tech_row)
    container.add_item(discord.ui.Separator())

    # Контент
    container.add_item(discord.ui.TextDisplay("### 🎬 **Контент**"))
    container.add_item(discord.ui.TextDisplay("Получайте уведомления о новых стримах и видео о нашем сервере."))
    if content_row:
        container._children.remove(content_row)
        container._children.append(content_row)

    view.add_item(container)
    await channel.send(view=view)


# ============================================================
# ВЫБОР ДОЛЖНОСТИ В КОМАНДЕ
# ============================================================
class TeamSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.select(
        placeholder="Выберите должность...",
        options=[
            discord.SelectOption(label="Хелпер", description="Рассматривает заявки, помогает игрокам", emoji="🎮"),
            discord.SelectOption(label="Модератор", description="Помогает игрокам и решает вопросы", emoji="🛡️"),
            discord.SelectOption(label="Технический администратор", description="Создаёт техническую часть проекта", emoji="⚙️"),
            discord.SelectOption(label="Медиа", description="Создаёт контент для продвижения", emoji="🎬"),
            discord.SelectOption(label="Контент-мейкер", description="Создаёт рекламные видеоролики", emoji="📦"),
        ],
        custom_id="team_select_v1"
    )
    async def team_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        selected = select.values[0]
        await interaction.response.send_modal(TeamApplicationModal(role=selected))


# ============================================================
# МОДАЛКА — ЗАЯВКА В КОМАНДУ
# ============================================================
class TeamApplicationModal(discord.ui.Modal, title="📝 Заявка в команду"):
    def __init__(self, role: str):
        super().__init__(title=f"📝 Заявка: {role}")
        self.role = role

    nickname = discord.ui.TextInput(label="Никнейм", style=discord.TextStyle.short, required=True, max_length=50)
    age = discord.ui.TextInput(label="Возраст", style=discord.TextStyle.short, required=True, max_length=3)
    experience = discord.ui.TextInput(label="Опыт работы", style=discord.TextStyle.long, required=True, max_length=500)
    why = discord.ui.TextInput(label="Почему хотите вступить?", style=discord.TextStyle.long, required=True, max_length=1000)

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
        }

        # Добавляем роли team staff для просмотра и управления тикетами
        for role_id in TEAM_STAFF_ROLE_IDS:
            role = guild.get_role(role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True)

        # Добавляем админов
        for admin_id in ALLOWED_ADMIN_IDS:
            admin_member = guild.get_member(admin_id)
            if admin_member:
                overwrites[admin_member] = discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True)

        category = guild.get_channel(CATEGORY_TEAM_ID)
        if not category or not isinstance(category, discord.CategoryChannel):
            await interaction.response.send_message("❌ Категория для команды не найдена!", ephemeral=True)
            return

        ticket_channel = await guild.create_text_channel(
            name=f"команда-{interaction.user.name}", category=category, overwrites=overwrites
        )

        ticket_embed = discord.Embed(
            title=f"📋 Заявка в команду: {self.role}",
            description=(
                f"**Никнейм:** {self.nickname.value}\n"
                f"**Возраст:** {self.age.value}\n"
                f"**Должность:** {self.role}\n\n"
                f"**Опыт работы:**\n{self.experience.value}\n\n"
                f"**Почему хотите вступить:**\n{self.why.value}\n\n"
                "---\n⏳ *Ожидайте проверки администратором.*"
            ),
            color=COLOR_DARK,
        )
        ticket_embed.set_footer(text="Эхо Бездны — приватный Minecraft сервер", icon_url="attachment://Logo.png")

        team_view = TeamTicketView()
        logo_path = os.path.join(os.path.dirname(__file__), "Logo.png")
        if os.path.exists(logo_path):
            logo_file = discord.File(logo_path, filename="Logo.png")
            await ticket_channel.send(embed=ticket_embed, view=team_view, file=logo_file)
        else:
            await ticket_channel.send(embed=ticket_embed, view=team_view)

        await interaction.response.send_message(
            f"✅ Заявка создана! Перейдите в {ticket_channel.mention}", ephemeral=True
        )

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        import traceback
        traceback.print_exc()
        try:
            await interaction.response.send_message(f"❌ Ошибка: {error}", ephemeral=True)
        except:
            await interaction.followup.send(f"❌ Ошибка: {error}", ephemeral=True)


# ============================================================
# ПАНЕЛЬ КОМАНДЫ (ОДИН КОНТЕЙНЕР — Components V2)
# ============================================================
async def send_team_panel(channel: discord.TextChannel):
    """Отправляет панель команды — ОДИН контейнер со всем."""

    view = discord.ui.LayoutView(timeout=None)
    container = discord.ui.Container(accent_color=0xB35ADD)

    # Баннер
    banner_path = os.path.join(os.path.dirname(__file__), "team.png")
    banner_file = None
    if os.path.exists(banner_path):
        banner_file = discord.File(banner_path, filename="team.png")
        media = discord.ui.MediaGallery()
        media.add_item(media="attachment://team.png")
        container.add_item(media)

    # Заголовок
    container.add_item(discord.ui.TextDisplay("## 📋 **Заявки в команду проекта**"))
    container.add_item(discord.ui.Separator())

    # Описание
    container.add_item(discord.ui.TextDisplay(
        "🤝 **Хотите стать частью нашей команды?**\n"
        "Здесь вы можете подать заявку на одну из доступных должностей. "
        "Выберите интересующую вас роль, ознакомьтесь с её обязанностями и заполните анкету."
    ))
    container.add_item(discord.ui.Separator())

    # Футер
    container.add_item(discord.ui.TextDisplay(
        "📩 **После рассмотрения заявки мы свяжемся с вами.**"
    ))

    view.add_item(container)

    logo_path = os.path.join(os.path.dirname(__file__), "Logo.png")
    logo_file = None
    if os.path.exists(logo_path):
        logo_file = discord.File(logo_path, filename="Logo.png")

    files = [f for f in [banner_file, logo_file] if f is not None]
    if files:
        await channel.send(view=view, files=files)
    else:
        await channel.send(view=view)

    # Select Menu отдельным сообщением
    await channel.send(view=TeamSelectView())


# ============================================================
# ПАНЕЛЬ СУДА (ОДИН КОНТЕЙНЕР — Components V2)
# ============================================================
async def send_court_panel(channel: discord.TextChannel):
    """Отправляет панель суда и идей."""

    view = discord.ui.LayoutView(timeout=None)
    container = discord.ui.Container(accent_color=0xB35ADD)

    # Баннер
    banner_path = os.path.join(os.path.dirname(__file__), "court.png")
    banner_file = None
    if os.path.exists(banner_path):
        banner_file = discord.File(banner_path, filename="court.png")
        media = discord.ui.MediaGallery()
        media.add_item(media="attachment://court.png")
        container.add_item(media)

    # Заголовок
    container.add_item(discord.ui.TextDisplay("## 📌 **Заявки и предложения**"))
    container.add_item(discord.ui.Separator())
    container.add_item(discord.ui.TextDisplay("Идеи и суд — в одном месте."))
    container.add_item(discord.ui.Separator())

    # Блок: Идея для сервера
    container.add_item(discord.ui.TextDisplay("### 💡 **Идея для сервера**"))
    container.add_item(discord.ui.TextDisplay(
        "Опишите предложение — администрация рассмотрит и опубликуют, если идея подойдёт."
    ))
    container.add_item(discord.ui.Separator())

    # Блок: Суд
    container.add_item(discord.ui.TextDisplay("### ⚖️ **Суд «Эхо Бездны»**"))
    container.add_item(discord.ui.TextDisplay(
        "Сложные конфликты: ник нарушителя, что произошло и ваше требование."
    ))
    container.add_item(discord.ui.Separator())

    view.add_item(container)

    logo_path = os.path.join(os.path.dirname(__file__), "Logo.png")
    logo_file = None
    if os.path.exists(logo_path):
        logo_file = discord.File(logo_path, filename="Logo.png")

    files = [f for f in [banner_file, logo_file] if f is not None]
    if files:
        await channel.send(view=view, files=files)
    else:
        await channel.send(view=view)

    # Select Menu отдельным сообщением
    await channel.send(view=CourtSelectView())


# ============================================================
# СЛЭШ-КОМАНДЫ
# ============================================================
@bot.tree.command(name="create_panel", description="Отправить панель заявок на сервер")
@app_commands.describe(channel="Куда отправить панель заявок")
async def create_panel(interaction: discord.Interaction, channel: discord.TextChannel):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ У вас нет прав.", ephemeral=True)
        return
    await interaction.response.send_message(f"✅ Панель заявок отправлена в {channel.mention}!", ephemeral=True)
    await send_panel(channel)


@bot.tree.command(name="create_panel2", description="Отправить панель поддержки")
@app_commands.describe(channel="Куда отправить панель поддержки")
async def create_panel2(interaction: discord.Interaction, channel: discord.TextChannel):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ У вас нет прав.", ephemeral=True)
        return
    await interaction.response.send_message(f"✅ Панель поддержки отправлена в {channel.mention}!", ephemeral=True)
    await send_support_panel(channel)


@bot.tree.command(name="create_panel3", description="Отправить панель уведомлений")
@app_commands.describe(channel="Куда отправить панель уведомлений")
async def create_panel3(interaction: discord.Interaction, channel: discord.TextChannel):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ У вас нет прав.", ephemeral=True)
        return
    await interaction.response.send_message(f"✅ Панель уведомлений отправлена в {channel.mention}!", ephemeral=True)
    await send_notifications_panel(channel)


@bot.tree.command(name="create_panel4", description="Отправить панель команды")
@app_commands.describe(channel="Куда отправить панель команды")
async def create_panel4(interaction: discord.Interaction, channel: discord.TextChannel):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ У вас нет прав.", ephemeral=True)
        return
    await interaction.response.send_message(f"✅ Панель команды отправлена в {channel.mention}!", ephemeral=True)
    await send_team_panel(channel)


@bot.tree.command(name="create_panel5", description="Отправить панель суда и идей")
@app_commands.describe(channel="Куда отправить панель суда")
async def create_panel5(interaction: discord.Interaction, channel: discord.TextChannel):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ У вас нет прав.", ephemeral=True)
        return
    await interaction.response.send_message(f"✅ Панель суда отправлена в {channel.mention}!", ephemeral=True)
    await send_court_panel(channel)


@bot.tree.command(name="help_panel", description="Список команд бота")
async def help_panel(interaction: discord.Interaction):
    embed = discord.Embed(
        title="📖 Команды Echo-voids Bot",
        description=(
            "`/create_panel` — Панель заявок\n"
            "`/create_panel2` — Панель поддержки\n"
            "`/create_panel3` — Панель уведомлений\n"
            "`/create_panel4` — Панель команды\n"
            "`/create_panel5` — Панель суда и идей\n"
            "`/help_panel` — Эта справка"
        ),
        color=COLOR_DARK,
    )
    embed.set_footer(text="Эхо Бездны — приватный Minecraft сервер", icon_url="attachment://Logo.png")

    logo_path = os.path.join(os.path.dirname(__file__), "Logo.png")
    if os.path.exists(logo_path):
        logo_file = discord.File(logo_path, filename="Logo.png")
        await interaction.response.send_message(embed=embed, file=logo_file)
    else:
        await interaction.response.send_message(embed=embed)


# ============================================================
# ECHO GUARD — Discord ↔ Minecraft, состояние в SQLite
# Все настройки и секреты бота остаются в app.py.
# ============================================================
import hashlib
import hmac
import ipaddress
import json
import logging
import re
import secrets
import sqlite3
import time
import uuid
from collections import defaultdict
from aiohttp import web

BRIDGE_HOST = "0.0.0.0"
BRIDGE_PORT = 5001  # Выделенный TCP-порт хостинга БОТА
BRIDGE_SECRET = "96b8f77f9f99baebf04c3aaf26d5d6ce0aa8c303375b036565891789db3b8263"
LINK_TTL = 600
REQUEST_TTL = 180
APPROVAL_TTL = 90
DATABASE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "echo_guard.sqlite3")
MC_NAME = re.compile(r"[A-Za-z0-9_]{3,16}\Z")
log = logging.getLogger("echo.guard")


def card(title, description, color=COLOR_DARK):
    embed = discord.Embed(title=title, description=description, color=color)
    embed.set_footer(text="ЭХО БЕЗДНЫ • Защита аккаунта")
    return embed


class GuardStore:
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS owners (
                name TEXT PRIMARY KEY COLLATE NOCASE, discord_id TEXT NOT NULL UNIQUE,
                uuid TEXT UNIQUE, active INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS commands (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'pending',
                error TEXT NOT NULL DEFAULT '', created REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS links (
                code TEXT PRIMARY KEY, uuid TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
                discord_id TEXT NOT NULL, expires REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS issued_link_codes (code TEXT PRIMARY KEY);
            INSERT OR IGNORE INTO issued_link_codes SELECT code FROM links;
            CREATE TABLE IF NOT EXISTS requests (
                id TEXT PRIMARY KEY, uuid TEXT NOT NULL, name TEXT NOT NULL,
                discord_id TEXT NOT NULL, ip TEXT NOT NULL, state TEXT NOT NULL,
                expires REAL NOT NULL, created REAL NOT NULL);
            CREATE INDEX IF NOT EXISTS requests_uuid ON requests(uuid);
            CREATE TABLE IF NOT EXISTS tickets (
                channel_id TEXT PRIMARY KEY, discord_id TEXT NOT NULL, name TEXT NOT NULL);
        ''')
        self.db.commit()

    def issue_link(self, player_uuid, name, discord_id, expires):
        # One transaction: collision retries never replace another player's link.
        with self.db:
            for _ in range(128):
                code = secrets.token_hex(5).upper()
                inserted = self.db.execute(
                    "INSERT OR IGNORE INTO issued_link_codes VALUES (?)", (code,))
                if inserted.rowcount:
                    self.db.execute("DELETE FROM links WHERE uuid=?", (player_uuid,))
                    self.db.execute("INSERT INTO links VALUES (?,?,?,?,?)",
                                    (code, player_uuid, name, discord_id, expires))
                    return code
            raise RuntimeError("Unable to allocate a unique linking code")

    def one(self, sql, args=()):
        return self.db.execute(sql, args).fetchone()

    def execute(self, sql, args=()):
        with self.db:
            return self.db.execute(sql, args)

    def reserve(self, name, discord_id):
        if not MC_NAME.fullmatch(name):
            raise ValueError("Ник Minecraft: 3–16 латинских букв, цифр или подчёркиваний.")
        owner = self.one("SELECT * FROM owners WHERE name=?", (name,))
        account = self.one("SELECT * FROM owners WHERE discord_id=?", (str(discord_id),))
        if owner and owner['discord_id'] != str(discord_id):
            raise ValueError("Этот ник уже закреплён за другим Discord. Нужна проверка администратора.")
        if account and account['name'].lower() != name.lower():
            raise ValueError("За этим Discord уже закреплён другой ник. Сначала проверьте прежнюю привязку.")
        self.execute("INSERT OR IGNORE INTO owners(name,discord_id) VALUES (?,?)", (name, str(discord_id)))

    def decision(self, request_id, discord_id, approve):
        row = self.one("SELECT * FROM requests WHERE id=?", (request_id,))
        if not row or row['discord_id'] != str(discord_id):
            return "Это не ваш запрос или он больше не существует."
        if row['state'] != 'pending' or row['expires'] <= time.time():
            return "Запрос уже обработан или истёк. Подключитесь к серверу ещё раз."
        self.execute("UPDATE requests SET state=?,expires=? WHERE id=? AND state='pending'",
                     ('approved' if approve else 'denied', time.time() + (APPROVAL_TTL if approve else 15), request_id))
        return (f"✅ Вход подтверждён. Подключитесь с того же IP в течение {APPROVAL_TTL} секунд."
                if approve else "⛔ Эта попытка отклонена. Аккаунт не заблокирован.")

    def consume(self, player_uuid, ip):
        now = time.time()
        row = self.one("SELECT * FROM requests WHERE uuid=? AND ip=? AND state='approved' AND expires>? ORDER BY created DESC LIMIT 1",
                       (player_uuid, ip, now))
        if not row:
            return False
        changed = self.execute("UPDATE requests SET state='used' WHERE id=? AND state='approved'", (row['id'],))
        return changed.rowcount == 1

    def bind(self, code, discord_id):
        row = self.one("SELECT * FROM links WHERE code=? AND expires>?", (code, time.time()))
        if not row or (row['discord_id'] and row['discord_id'] != str(discord_id)):
            return False
        owner = self.one("SELECT * FROM owners WHERE name=?", (row['name'],))
        account = self.one("SELECT * FROM owners WHERE discord_id=?", (str(discord_id),))
        if account and account['name'].lower() != row['name'].lower():
            return False
        if owner and (not owner['active'] or owner['discord_id'] != str(discord_id)
                      or owner['uuid'] not in (None, row['uuid'])):
            return False
        try:
            with self.db:
                if not owner:
                    # Empty Discord ID marks an eligible legacy whitelist player.
                    if row['discord_id']:
                        return False
                    self.db.execute("INSERT INTO owners(name,discord_id,uuid,active) VALUES (?,?,?,1)",
                                    (row['name'], str(discord_id), row['uuid']))
                else:
                    self.db.execute("UPDATE owners SET uuid=? WHERE name=?", (row['uuid'], row['name']))
                self.db.execute("DELETE FROM links WHERE uuid=? OR name=? COLLATE NOCASE", (row['uuid'], row['name']))
            return True
        except sqlite3.IntegrityError:
            return False


class AuthButton(discord.ui.DynamicItem[discord.ui.Button], template=r"echo:auth:(?P<action>yes|no):(?P<request>[a-f0-9]{32})"):
    def __init__(self, action, request_id):
        self.action, self.request_id = action, request_id
        super().__init__(discord.ui.Button(
            label="Подтвердить вход" if action == 'yes' else "Отклонить",
            emoji="✅" if action == 'yes' else "⛔",
            style=discord.ButtonStyle.success if action == 'yes' else discord.ButtonStyle.danger,
            custom_id=f"echo:auth:{action}:{request_id}"))

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(match['action'], match['request'])

    async def callback(self, interaction):
        result = guard.store.decision(self.request_id, interaction.user.id, self.action == 'yes')
        await interaction.response.send_message(embed=card("Решение по входу", result), ephemeral=True)
        # Чужой клик не может отключить кнопки владельцу.
        row = guard.store.one("SELECT * FROM requests WHERE id=?", (self.request_id,))
        if row and row['discord_id'] == str(interaction.user.id) and row['state'] != 'pending':
            try:
                await interaction.message.edit(view=None)
            except discord.HTTPException:
                pass


class GuardBridge:
    def __init__(self, store):
        self.store = store
        self.last_poll = 0
        self.nonces = {}
        self.player_locks = defaultdict(asyncio.Lock)
        self.ticket_busy = set()
        self.dm_rates = {}
        self.runner = None

    async def start(self):
        app = web.Application(client_max_size=16384)
        app.router.add_post('/bridge/{operation}', self.api)
        self.runner = web.AppRunner(app, access_log=None)
        await self.runner.setup()
        await web.TCPSite(self.runner, BRIDGE_HOST, BRIDGE_PORT).start()
        log.info("Minecraft bridge слушает порт %s", BRIDGE_PORT)

    async def api(self, request):
        raw = await request.read()
        stamp = request.headers.get('X-Echo-Time', '')
        nonce = request.headers.get('X-Echo-Nonce', '')
        signature = request.headers.get('X-Echo-Signature', '')
        now = time.time()
        try:
            if abs(now - int(stamp)) > 30 or not re.fullmatch(r'[a-f0-9]{32}', nonce):
                raise ValueError()
            expected = hmac.new(BRIDGE_SECRET.encode(), stamp.encode() + b'\n' + nonce.encode() + b'\n' + request.path.encode() + b'\n' + raw, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected, signature):
                raise ValueError()
            self.nonces = {n: t for n, t in self.nonces.items() if t > now - 60}
            if nonce in self.nonces:
                raise ValueError()
            self.nonces[nonce] = now
        except (ValueError, OverflowError):
            raise web.HTTPUnauthorized()
        try:
            payload = json.loads(raw)
            if not isinstance(payload, dict):
                raise ValueError('object required')
            if not bot.is_ready():
                result = {'ok': False, 'message': 'Discord пока недоступен. Повторите вход позже.'}
            else:
                result = await self.dispatch(request.match_info['operation'], payload)
        except (ValueError, KeyError, TypeError):
            result = {'ok': False, 'message': 'Некорректный запрос.'}
        except Exception:
            log.exception("Ошибка обработки bridge")
            result = {'ok': False, 'message': 'Ошибка сервиса защиты. Повторите позже.'}
        body = json.dumps(result, ensure_ascii=False, separators=(',', ':')).encode()
        sig = hmac.new(BRIDGE_SECRET.encode(), nonce.encode() + b'\n' + body, hashlib.sha256).hexdigest()
        return web.Response(body=body, content_type='application/json', headers={'X-Echo-Signature': sig})

    async def dispatch(self, operation, data):
        now = time.time()
        if operation == 'poll':
            self.last_poll = now
            self.store.execute("DELETE FROM links WHERE expires<?", (now,))
            self.store.execute("DELETE FROM requests WHERE expires<?", (now - 86400,))
            rows = self.store.db.execute("SELECT id,name FROM commands WHERE state='pending' ORDER BY created LIMIT 20").fetchall()
            return {'ok': True, 'commands': [dict(r) for r in rows]}
        if operation == 'ack':
            row = self.store.one("SELECT * FROM commands WHERE id=?", (data['id'],))
            if not row:
                return {'ok': False}
            if row['state'] != 'pending':
                return {'ok': True}
            with self.store.db:
                if data.get('success') is True:
                    self.store.db.execute("UPDATE owners SET active=1 WHERE name=?", (row['name'],))
                self.store.db.execute("UPDATE commands SET state=?,error=? WHERE id=?",
                                      ('done' if data.get('success') is True else 'failed', str(data.get('error', ''))[:200], data['id']))
            return {'ok': True}
        if operation == 'login':
            player_uuid = str(uuid.UUID(data['uuid']))
            name = data['name']
            ip = str(ipaddress.ip_address(data['ip']))
            if not isinstance(name, str) or not MC_NAME.fullmatch(name):
                raise ValueError()
            # Lock covers DM delivery, avoiding duplicate notifications from reconnects.
            async with self.player_locks[player_uuid]:
                return await self.login(player_uuid, name, ip, data.get('whitelisted') is True)
        return {'ok': False, 'message': 'Неизвестная операция.'}

    async def login(self, player_uuid, name, ip, whitelisted=False):
        now = time.time()
        owner = self.store.one("SELECT * FROM owners WHERE name=? AND active=1", (name,))
        reserved = self.store.one("SELECT * FROM owners WHERE name=?", (name,))
        if not owner and (not whitelisted or reserved):
            return {'ok': True, 'allow': False, 'message': 'Сначала дождитесь принятия заявки в Discord.'}
        if owner and owner['uuid'] and owner['uuid'] != player_uuid:
            return {'ok': True, 'allow': False, 'message': 'Идентификатор аккаунта изменился.\nОбратитесь к администрации для проверки.'}
        if not owner or not owner['uuid']:
            expected_discord = owner['discord_id'] if owner else ''
            code = self.store.issue_link(player_uuid, name, expected_discord, now + LINK_TTL)
            hint = 'Используйте Discord, с которого подана заявка.' if owner else 'Это единоразовая привязка вашего Discord.'
            return {'ok': True, 'allow': False, 'message': f'Привяжите Discord к Minecraft\n\nОтправьте боту в личные сообщения:\n{code}\n\nКод действует 10 минут.\n{hint}'}
        if self.store.consume(player_uuid, ip):
            return {'ok': True, 'allow': True}
        row = self.store.one("SELECT * FROM requests WHERE uuid=? AND expires>? AND state IN ('pending','approved','denied') ORDER BY created DESC LIMIT 1", (player_uuid, now))
        if row:
            if row['state'] == 'approved':
                message = 'Подтверждён другой IP.\nПодключитесь с подтверждённого адреса\nили дождитесь истечения запроса (до 90 секунд).'
            elif row['state'] == 'denied':
                message = 'Попытка отклонена. Аккаунт не заблокирован.\nНовый запрос можно отправить через 15 секунд.'
            else:
                message = 'Подтвердите вход в личных сообщениях Discord.\nЗатем подключитесь ещё раз.\nЗапрос действует до 3 минут.'
            return {'ok': True, 'allow': False, 'message': message}
        request_id = uuid.uuid4().hex
        self.store.execute("INSERT INTO requests VALUES (?,?,?,?,?,'pending',?,?)", (request_id, player_uuid, name, owner['discord_id'], ip, now + REQUEST_TTL, now))
        view = discord.ui.View(timeout=None)
        view.add_item(AuthButton('yes', request_id))
        view.add_item(AuthButton('no', request_id))
        try:
            user = bot.get_user(int(owner['discord_id'])) or await bot.fetch_user(int(owner['discord_id']))
            embed = card("🛡️ Подтвердите вход", f"Попытка входа на **Эхо Бездны**\n\n**Игрок:** `{name}`\n**IP:** `{ip}`\n**Время:** <t:{int(now)}:F>\n\nЕсли входите вы — подтвердите и подключитесь снова.\nЕсли это не вы — отклоните попытку. Бан не выдаётся.\n\n⏳ Запрос действует **3 минуты**.")
            await asyncio.wait_for(user.send(embed=embed, view=view), timeout=4)
        except (discord.HTTPException, asyncio.TimeoutError):
            self.store.execute("UPDATE requests SET state='denied',expires=? WHERE id=?", (now + 30, request_id))
            return {'ok': True, 'allow': False, 'message': 'Не удалось доставить сообщение Discord.\nРазрешите личные сообщения от бота\nи повторите через 30 секунд.'}
        return {'ok': True, 'allow': False, 'message': 'Запрос отправлен в Discord\n\nНажмите «Подтвердить вход» в ЛС бота,\nзатем подключитесь повторно с того же IP.'}

    async def whitelist(self, name, discord_id):
        self.store.reserve(name, discord_id)
        pending = self.store.one("SELECT * FROM commands WHERE name=? COLLATE NOCASE AND state='pending'", (name,))
        command_id = pending['id'] if pending else uuid.uuid4().hex
        if not pending:
            self.store.execute("INSERT INTO commands(id,name,created) VALUES (?,?,?)", (command_id, name, time.time()))
        for _ in range(30):
            row = self.store.one("SELECT * FROM commands WHERE id=?", (command_id,))
            if row['state'] == 'done':
                return
            if row['state'] == 'failed':
                raise ValueError("Плагин не смог добавить игрока в whitelist. Проверьте консоль Minecraft.")
            await asyncio.sleep(0.4)
        raise ValueError("Нет подтверждения от Minecraft. Задание сохранено в очереди; тикет остаётся открытым. После запуска плагина нажмите «Принять» повторно.")


guard = None


def ticket_identity(channel, guild):
    """Старые NICK: темы и permissions сохраняются; ник Discord не является ID."""
    row = guard.store.one("SELECT * FROM tickets WHERE channel_id=?", (str(channel.id),))
    if row:
        return guild.get_member(int(row['discord_id'])), row['name']
    topic = channel.topic or ''
    match = re.search(r'(?:^|\|)OWNER:(\d+)', topic)
    nick = re.match(r'NICK:([^|]+)', topic)
    name = nick.group(1).strip() if nick else ''
    if match:
        return guild.get_member(int(match.group(1))), name
    visible = [target for target, perms in channel.overwrites.items()
               if isinstance(target, discord.Member) and not target.bot
               and perms.view_channel is True]
    # Старый канал создавался из username, не из Minecraft/display_name.
    channel_user = channel.name.removeprefix('заявка-').casefold()
    matches = [m for m in visible if m.name.casefold() == channel_user]
    candidates = [m for m in visible if m.id not in ALLOWED_ADMIN_IDS
                  and not any(r.id in STAFF_ROLE_IDS for r in m.roles)]
    if len(matches) == 1:
        member = matches[0]
    elif len(candidates) == 1:
        member = candidates[0]
    else:
        member = None
    if member and name:
        guard.store.execute("INSERT OR REPLACE INTO tickets VALUES (?,?,?)", (str(channel.id), str(member.id), name))
    return member, name


async def resolve_ticket_identity(channel, guild):
    """Сохранённый ID имеет приоритет; отсутствие в кэше не означает выход."""
    member, name = ticket_identity(channel, guild)
    if member:
        return member, name
    row = guard.store.one("SELECT * FROM tickets WHERE channel_id=?", (str(channel.id),))
    match = re.search(r'(?:^|\|)OWNER:(\d+)', channel.topic or '')
    owner_id = int(row['discord_id']) if row else int(match.group(1)) if match else None
    if owner_id is not None:
        try:
            member = await guild.fetch_member(owner_id)
        except discord.NotFound:
            return None, name
        return member, name
    # Discord может ещё не загрузить участников со старыми permission overwrites.
    if not guild.chunked:
        try:
            await asyncio.wait_for(guild.chunk(cache=True), timeout=10)
        except asyncio.TimeoutError:
            return None, name
        return ticket_identity(channel, guild)
    return None, name


async def accept_application(interaction, staff_view):
    if not staff_view.is_staff(interaction.user):
        await interaction.response.send_message("❌ У вас нет прав.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True, thinking=True)
    channel = interaction.channel
    if channel.id in guard.ticket_busy:
        await interaction.followup.send("⏳ Эта заявка уже обрабатывается.", ephemeral=True)
        return
    guard.ticket_busy.add(channel.id)
    try:
        if channel.category_id != CATEGORY_APPLICATIONS_ID or not channel.name.startswith('заявка-'):
            raise ValueError("Это не канал заявки на сервер.")
        member, name = await resolve_ticket_identity(channel, interaction.guild)
        if not member:
            raise ValueError("Не удалось однозначно определить автора. Используйте /mc_ticket_owner в этом тикете.")
        role = interaction.guild.get_role(ROLE_ACCEPT_ID)
        if not role:
            raise ValueError("Роль принятого игрока не найдена. Тикет сохранён.")
        await guard.whitelist(name, member.id)
        await member.add_roles(role, reason="Заявка принята; Minecraft подтвердил whitelist")
        nick_note = ''
        try:
            await member.edit(nick=name)
        except discord.HTTPException:
            nick_note = '\n⚠️ Ник Discord не изменён: проверьте права/иерархию ролей.'
        await channel.send(embed=card("✅ Заявка принята", f"{member.mention}, **{name}** добавлен в whitelist.\nПри первом входе отправьте код в личные сообщения боту.\nДалее каждый вход подтверждается через Discord.{nick_note}"))
        try:
            await member.send(embed=card("Добро пожаловать в Эхо Бездны", f"Заявка принята! Ник: **{name}**.\n\n**1.** Подключитесь к Minecraft и скопируйте код.\n**2.** Отправьте код сюда.\n**3.** Снова зайдите и подтвердите вход кнопкой.\n\nРекомендуемые моды: Simple Voice Chat и EmoteCraft."))
        except discord.HTTPException:
            pass
        # При ошибке архивации не удаляем историю заявки.
        await log_ticket_close(channel, interaction.guild, "Заявка принята + whitelist", interaction.user)
        await interaction.followup.send("✅ Minecraft подтвердил whitelist, роль выдана. Тикет закрывается.", ephemeral=True)
        await asyncio.sleep(5)
        await channel.delete(reason="Заявка принята; whitelist подтверждён")
    except ValueError as exc:
        await interaction.followup.send(str(exc), ephemeral=True)
    except Exception:
        log.exception("Ошибка принятия заявки %s", channel.id)
        await interaction.followup.send("⚠️ Не удалось завершить все действия. Тикет не удалён; проверьте роли/права и журнал бота. Повторное принятие безопасно.", ephemeral=True)
    finally:
        guard.ticket_busy.discard(channel.id)


@bot.event
async def on_message(message):
    if message.author.bot:
        return
    if message.guild is None:
        code = message.content.strip().upper()
        now = time.time()
        attempts = [t for t in guard.dm_rates.get(message.author.id, []) if t > now - 60]
        if len(attempts) >= 5:
            return
        attempts.append(now)
        guard.dm_rates[message.author.id] = attempts
        if re.fullmatch(r'[A-F0-9]{10}', code) and guard.store.bind(code, message.author.id):
            await message.channel.send(embed=card("🔗 Аккаунт привязан", "Теперь подключитесь к Minecraft ещё раз.\nЯ пришлю кнопки подтверждения входа."))
        else:
            await message.channel.send(embed=card("Привязка Minecraft", "Отправьте **только код** с экрана отключения Minecraft.\nКод действует 10 минут. Для новых заявок используйте Discord их автора.\nЕсли вы уже в whitelist, просто подключитесь к Minecraft и получите код."))
        return
    await bot.process_commands(message)


@bot.tree.command(name='mc_assign', description='Закрепить ник за Discord и добавить в whitelist (также для старых игроков)')
@app_commands.guild_only()
@app_commands.default_permissions(administrator=True)
async def mc_assign(interaction: discord.Interaction, member: discord.Member, nickname: str):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("Нет прав.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    try:
        await guard.whitelist(nickname.strip(), member.id)
        await interaction.followup.send(f"✅ `{nickname}` закреплён за {member.mention} и добавлен в whitelist.", ephemeral=True)
    except ValueError as exc:
        await interaction.followup.send(str(exc), ephemeral=True)


@bot.tree.command(name='mc_ticket_owner', description='Восстановить автора старого тикета, если он неоднозначен')
@app_commands.guild_only()
@app_commands.default_permissions(administrator=True)
async def mc_ticket_owner(interaction: discord.Interaction, member: discord.Member, nickname: str):
    if not interaction.user.guild_permissions.administrator or interaction.channel.category_id != CATEGORY_APPLICATIONS_ID:
        await interaction.response.send_message("Команда доступна администратору внутри заявки.", ephemeral=True)
        return
    if not MC_NAME.fullmatch(nickname):
        await interaction.response.send_message("Некорректный ник Minecraft.", ephemeral=True)
        return
    guard.store.execute("INSERT OR REPLACE INTO tickets VALUES (?,?,?)", (str(interaction.channel_id), str(member.id), nickname))
    await interaction.response.send_message("✅ Автор сохранён. Теперь нажмите «Принять».", ephemeral=True)


@bot.tree.command(name='mc_status', description='Статус связи с Minecraft')
@app_commands.guild_only()
@app_commands.default_permissions(administrator=True)
async def mc_status(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("Нет прав.", ephemeral=True)
        return
    age = time.time() - guard.last_poll
    await interaction.response.send_message(embed=card("Связь с Minecraft", "🟢 Плагин на связи" if age < 15 else "🔴 Плагин недоступен: проверьте адрес, порт и ключ связи."), ephemeral=True)


async def setup_guard():
    global guard
    guard = GuardBridge(GuardStore(DATABASE_PATH))
    bot.add_dynamic_items(AuthButton)
    # Регистрируем также старые Components V2 панели — исходник их не восстанавливал.
    for container_cls in (ApplicationContainer, NotificationsPanelContainer):
        view = discord.ui.LayoutView(timeout=None)
        view.add_item(container_cls())
        bot.add_view(view)
    await guard.start()

bot.setup_hook = setup_guard


# ============================================================
# ЗАПУСК
# ============================================================
@bot.event
async def on_ready():
    print(f"✅ Бот {bot.user} запущен!")
    print(f"📡 Серверы: {len(bot.guilds)}")

    # Persistent views
    bot.add_view(TicketActionsView())
    bot.add_view(SupportSelectView())
    bot.add_view(SupportTicketView())
    bot.add_view(TeamSelectView())
    bot.add_view(TeamTicketView())
    bot.add_view(CourtSelectView())
    print("✅ Persistent views зарегистрированы")

    try:
        synced = await bot.tree.sync()
        print(f"🔄 Синхронизировано {len(synced)} команд:")
        for cmd in synced:
            print(f"   - /{cmd.name}")
    except Exception as e:
        print(f"❌ Ошибка синхронизации: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    if TOKEN == "СЮДА_ВСТАВЬ_СВОЙ_ТОКЕН":
        print("❌ ОШИБКА: Вставь свой токен в файл bot.py!")
    else:
        bot.run(TOKEN)
