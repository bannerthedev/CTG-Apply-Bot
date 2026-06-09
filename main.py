import asyncio
import os
from dotenv import load_dotenv

import discord
from discord.ext import commands
from discord.ui import View, Select, Button
from discord import app_commands, TextChannel

load_dotenv()

# ============== CONFIG ==============
GUILD_IDS = 1469203259842494497  # or None to register globally
APPLICATION_CHANNEL_ID = 1470568892194881642
TRANSACTIONS_CHANNEL_ID = 1469208105559658702
ANNOUNCEMENTS_CHANNEL_ID = 1469204156110733322

CASTER_ROLE_ID = 1470388240602366126
REF_ROLE_ID = 1470388292900880487
COMMENTATOR_ROLE_ID = 1470388326493323335
HELPER_ROLE_ID = 1470383693641027616  # trial staff/helper

STAFF_ROLE_ID = 111111111111111111  # placeholder

APP_STATUS = {
    "caster": True,
    "ref": True,
    "commentator": True,
    "staff": True,
    "team": True,
}
# ======================================

# Colors and helpers
GREEN = 0x57F287  # Discord success green
BLURPLE = 0x5865F2  # Discord blurple
DARK = 0x2F3136

def green_embed(title: str = None, description: str = None):
    return discord.Embed(title=title, description=description, color=GREEN)

# QUESTION TEXTS USED FOR EMBED TITLES (copied / adapted from your originals; no media section)
QUESTION_TEXTS = {
    "staff": {
        "1": "What's your discord username?",
        "2": "What's your discord ID? If you don't know how to find your discord id, here's a tutorial:https://youtu.be/KmTQLj6NIfI",
        "3": "What is your age? Discord TOS states nobody under the age of 13 may be on their platform.",
        "4": "What previous discord moderation experience do you have? Please state the name of the discord server, your role there and the member count of that server.",
        "5": "Why should we accept you?",
    },
    "caster": {
        "1": "What's your Discord Username? (EX. Odspace)",
        "2": "What Casting Mod do you use? (EX. Sakuras)",
        "3": "How much experience do you have? (EX. 1 month)",
        "4": "If you have a clip of your casting, please send it here ⬇️ Make sure it's a link.",
        "5": "Make sure to read the league rules before completing the application.",
        "6": "What is your age?",
        "7": "Timezone / availability:",
        "8": "Any additional notes?",
        "9": "Upload/download speed (optional):",
        "10": "Anything else?",
    },
    "team": {
        "1": "What is your team name?",
        "2": "What is your team abbreviation? (EX. TSO, TTT, SV)",
        "3": "Team exc:",
        "4": "Team cap:",
        "5": "Team players:",
    },
    "ref": {
        "1": "What is your Discord username & ID?",
        "2": "Name 3 official scrims you have reffed for (include teams and score).",
        "3": "What is the recommended minimum time a ref should give late players?",
        "4": "How long do runners have before taggers can pursue them?",
        "5": "Where do runners go when tagged by the opposing team?",
        "6": "What headsets are allowed in MMM official scrims?",
        "7": "Can teams have different colors than their teammates? If not, why?",
        "8": "Do players have team abbreviation in their name while playing? If not, why?",
        "9": "Do you understand that if you don't ref at least 3-5 matches per season you may be removed/demoted?",
        "10": "Do you understand that if you are caught being bias you WILL be removed?",
        "11": "Do you understand you must follow your Head Referees instructions at all times?",
    },
    "commentator": {
        "1": "What is your Discord Username?",
        "2": "Do you know in-game callouts and how the league rules work?",
        "3": "Do you have experience commentating? If so list the discords you have been a commentator for.",
        "4": "Why should you be commentator? Please give a thorough reasoning on why.",
        "5": "If you use a PC to call on discord what microphone do you use?",
    },
}

# Announcement / team data (example)
TEAMS_FOR_ANNOUNCEMENT = [
    "Uncrowned", "Sovereign", "Fusion", "Kitty Power", "Avalanche",
    "Relic", "LOVE", "We Eat Concrete", "Dark Crimson", "Vivid Dreams"
]
TEAMS_FOR_CREATION = [
    # ("TeamName", "ff00ff", 123456789012345678),
]

# Track newly accepted for "Everything Wave"
NEW_REFS = set()
NEW_CASTERS = set()
NEW_STAFF = set()
NEW_COMMENTATORS = set()

# Intents & bot
intents = discord.Intents.default()
intents.messages = True
intents.dm_messages = True
intents.guilds = True
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Keep track of posted panels per guild (channel_id, message_id) list
PANEL_MESSAGES = {}

# ---------- Register UI ----------
class RegisterSelect(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(RegisterTypeSelect())

class RegisterTypeSelect(Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Caster", value="caster", description="Apply to be a caster"),
            discord.SelectOption(label="Referee", value="ref", description="Apply to be a referee"),
            discord.SelectOption(label="Commentator", value="commentator", description="Apply to be a commentator"),
            discord.SelectOption(label="Staff", value="staff", description="Apply to be staff"),
            discord.SelectOption(label="Team", value="team", description="Apply as a team"),
        ]
        super().__init__(placeholder="Choose application type", min_values=1, max_values=1, options=options, custom_id="register_select")

    async def callback(self, interaction: discord.Interaction):
        app_type = self.values[0]
        # Prevent staff from applying as team
        if app_type == "team" and isinstance(interaction.user, discord.Member):
            if any(r.id == STAFF_ROLE_ID for r in interaction.user.roles):
                await interaction.response.send_message("You already have a staff role and cannot apply for a team.", ephemeral=True)
                return
        if not APP_STATUS.get(app_type, True):
            await interaction.response.send_message("This application is currently closed.", ephemeral=True)
            return
        await interaction.response.send_message("Application started — check your DMs.", ephemeral=True)
        await start_application_flow(interaction.user, app_type, interaction)

# ---------- Application flow ----------
async def start_application_flow(user: discord.User, app_type: str, interaction: discord.Interaction):
    try:
        dm = await user.create_dm()
    except Exception:
        try:
            await interaction.followup.send("I couldn't DM you. Enable DMs and try again.", ephemeral=True)
        except:
            pass
        return

    # Intro with Start / Cancel
    class IntroView(View):
        def __init__(self):
            super().__init__(timeout=300)
            self.choice = None

        @discord.ui.button(label="Start Application", style=discord.ButtonStyle.primary, custom_id="intro_start")
        async def start_app(self, button_interaction: discord.Interaction, button: Button):
            if button_interaction.user.id != user.id:
                await button_interaction.response.send_message("This is not for you.", ephemeral=True)
                return
            self.choice = "accept"
            await button_interaction.response.edit_message(content="Beginning application — please answer the prompts in this DM.", view=None)
            self.stop()

        @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, custom_id="intro_cancel")
        async def cancel_app(self, button_interaction: discord.Interaction, button: Button):
            if button_interaction.user.id != user.id:
                await button_interaction.response.send_message("This is not for you.", ephemeral=True)
                return
            self.choice = "deny"
            await button_interaction.response.edit_message(content="Application cancelled. Re-run /register when ready.", view=None)
            self.stop()

    intro_view = IntroView()
    intro_embed = discord.Embed(
        title=f"{app_type.capitalize()} Application",
        description="You will have limited time to answer. Click Start Application to continue or Cancel to stop.",
        color=BLURPLE
    )
    try:
        await dm.send(embed=intro_embed, view=intro_view)
    except Exception:
        try:
            await interaction.followup.send("Couldn't send the intro DM. Enable DMs and try again.", ephemeral=True)
        except:
            pass
        return

    await intro_view.wait()
    if intro_view.choice is None:
        try:
            await dm.send("Timed out. Please re-run /register to begin again.")
        except:
            pass
        return
    if intro_view.choice == "deny":
        return

    # helpers for collecting answers
    async def collect_text(question: str, timeout: float = 300.0):
        await dm.send(question)
        def check(m: discord.Message):
            return m.author.id == user.id and isinstance(m.channel, discord.DMChannel)
        try:
            msg = await bot.wait_for('message', timeout=timeout, check=check)
        except asyncio.TimeoutError:
            await dm.send("Timed out. Please re-run /register to start again.")
            return None
        content = msg.content.strip()
        if not content:
            await dm.send("Response cannot be empty. Please re-run /register.")
            return None
        return content

    async def ask_yes_no(question: str, timeout: float = 300.0):
        class YesNoView(View):
            def __init__(self):
                super().__init__(timeout=timeout)
                self.value = None

            @discord.ui.select(placeholder="Choose", min_values=1, max_values=1, options=[
                discord.SelectOption(label="Yes", value="Yes"),
                discord.SelectOption(label="No", value="No")
            ])
            async def sel(self, interaction2: discord.Interaction, select: Select):
                if interaction2.user.id != user.id:
                    await interaction2.response.send_message("This is not for you.", ephemeral=True)
                    return
                self.value = select.values[0]
                await interaction2.response.edit_message(content=f"{question}\nAnswer: {self.value}", view=None)
                self.stop()

        view = YesNoView()
        msg = await dm.send(question, view=view)
        await view.wait()
        if view.value is None:
            try:
                await msg.edit(content="Timed out. Please re-run /register.", view=None)
            except:
                pass
            return None
        return view.value

    async def ask_select(question: str, options: list, timeout: float = 300.0):
        class SelectView(View):
            def __init__(self):
                super().__init__(timeout=timeout)
                self.value = None

            @discord.ui.select(placeholder="Select an option", min_values=1, max_values=1, options=[discord.SelectOption(label=o, value=o) for o in options])
            async def sel(self, interaction2: discord.Interaction, select: Select):
                if interaction2.user.id != user.id:
                    await interaction2.response.send_message("This is not for you.", ephemeral=True)
                    return
                self.value = select.values[0]
                await interaction2.response.edit_message(content=f"{question}\nAnswer: {self.value}", view=None)
                self.stop()

        view = SelectView()
        msg = await dm.send(question, view=view)
        await view.wait()
        if view.value is None:
            try:
                await msg.edit(content="Timed out. Please re-run /register.", view=None)
            except:
                pass
            return None
        return view.value

    answers = {}

    # Questions per app_type (matching the "bottom" script wording)
    if app_type == "caster":
        answers["1"] = await collect_text("1/10. What is your Discord username & ID?")
        if answers["1"] is None: return
        answers["2"] = await collect_text("2/10. Do you have a mic?")
        if answers["2"] is None: return
        answers["3"] = await collect_text("3/10. Do you have any past experience with casting in Gorilla Tag? If so please explain.")
        if answers["3"] is None: return
        answers["4"] = await collect_text("4/10. Why do you want to become a Caster for MMM?")
        if answers["4"] is None: return
        answers["5"] = await collect_text("5/10. What is your Upload & Download Speed? (use https://www.speedtest.net/)")
        if answers["5"] is None: return
        answers["6"] = await collect_text("6/10. List your PC specifications.")
        if answers["6"] is None: return
        answers["7"] = await collect_text("7/10. If you have past casting experience, link your YouTube/Twitch/etc.")
        if answers["7"] is None: return
        answers["8"] = await collect_text("8/10. Are you familiar with OBS?")
        if answers["8"] is None: return
        answers["9"] = await collect_text("9/10. Please send a video showing OBS tasks (make Game Capture, add mic, import/export profile, make scene). Upload via Drive/MediaFire and send link.")
        if answers["9"] is None: return
        answers["10"] = await collect_text("10/10. Any questions?")
        if answers["10"] is None: return

    elif app_type == "ref":
        answers["1"] = await collect_text("1/11. What is your Discord username & ID?")
        if answers["1"] is None: return
        answers["2"] = await collect_text("2/11. Name 3 official scrims you have reffed for (include teams and score).")
        if answers["2"] is None: return
        answers["3"] = await collect_text("3/11. What is the recommended minimum time a ref should give late players?")
        if answers["3"] is None: return
        answers["4"] = await collect_text("4/11. How long do runners have before taggers can pursue them?")
        if answers["4"] is None: return
        answers["5"] = await collect_text("5/11. Where do runners go when tagged by the opposing team?")
        if answers["5"] is None: return
        answers["6"] = await collect_text("6/11. What headsets are allowed in MMM official scrims?")
        if answers["6"] is None: return
        answers["7"] = await collect_text("7/11. Can teams have different colors than their teammates? If not, why?")
        if answers["7"] is None: return
        answers["8"] = await collect_text("8/11. Do players have team abbreviation in their name while playing? If not, why?")
        if answers["8"] is None: return
        ans9 = await ask_yes_no("9/11. Do you understand that if you don't ref at least 3-5 matches per season you may be removed/demoted?")
        if ans9 is None: return
        answers["9"] = ans9
        ans10 = await ask_yes_no("10/11. Do you understand that if you are caught being bias you WILL be removed?")
        if ans10 is None: return
        answers["10"] = ans10
        ans11 = await ask_yes_no("11/11. Do you understand you must follow your Head Referees instructions at all times?")
        if ans11 is None: return
        answers["11"] = ans11

    elif app_type == "commentator":
        answers["1"] = await collect_text("1/5. What is your Discord Username?")
        if answers["1"] is None: return
        answers["2"] = await collect_text("2/5. Do you know in-game callouts and how the league rules work?")
        if answers["2"] is None: return
        answers["3"] = await collect_text("3/5. Do you have experience commentating? If so list the discords you have been a commentator for.")
        if answers["3"] is None: return
        answers["4"] = await collect_text("4/5. Why should you be commentator? Please give a thorough reasoning on why.")
        if answers["4"] is None: return
        answers["5"] = await collect_text("5/5. If you use a PC to call on discord what microphone do you use?")
        if answers["5"] is None: return

    elif app_type == "staff":
        answers["1"] = await collect_text("1/4. What Is Your Username And ID.")
        if answers["1"] is None: return
        answers["2"] = await collect_text("2/4. What Is Your Age.")
        if answers["2"] is None: return
        answers["3"] = await collect_text("3/4. Do you have experience being a moderator for a league? If yes, please list the league and when you served.")
        if answers["3"] is None: return
        answers["4"] = await collect_text("4/4. Why Should We Accept You.")
        if answers["4"] is None: return

    elif app_type == "team":
        answers["1"] = await collect_text("1/5. What is your team name?")
        if answers["1"] is None: return
        answers["2"] = await collect_text("2/5. What is your team abbreviation? (EX. TSO, TTT, SV)")
        if answers["2"] is None: return
        answers["3"] = await collect_text("3/5. Team exc:")
        if answers["3"] is None: return
        answers["4"] = await collect_text("4/5. Team cap:")
        if answers["4"] is None: return
        answers["5"] = await collect_text("5/5. Team players:")
        if answers["5"] is None: return

    # Confirmation to user
    await dm.send("Application submitted.\nYour application has been submitted.")

    # Build embed (use QUESTION_TEXTS for nicer field names where available)
    embed = discord.Embed(
        title=f"{user.display_name}'s {app_type.capitalize()} Application",
        description="Application Submitted",
        color=DARK
    )
    try:
        embed.set_thumbnail(url=user.display_avatar.url)
    except:
        pass

    qtext_map = QUESTION_TEXTS.get(app_type, {})
    for qnum, ans in answers.items():
        question_text = qtext_map.get(qnum, f"Question {qnum}")
        field_name = f"Q{qnum}: {question_text}"
        embed.add_field(name=field_name, value=ans if len(ans) < 1024 else ans[:1021] + "...", inline=False)

    embed.set_footer(text=f"User ID: {user.id}")

    # Staff decision view (anonymized public messages)
    class StaffDecisionView(View):
        def __init__(self, target_user_id: int, app_type: str, answers_dict: dict):
            super().__init__(timeout=None)
            self.target_user_id = target_user_id
            self.app_type = app_type
            self.answers = answers_dict

        @discord.ui.button(label="Accept", style=discord.ButtonStyle.green, custom_id="app_accept")
        async def accept(self, interaction2: discord.Interaction, button: Button):
            staff_member = interaction2.user
            if not isinstance(staff_member, discord.Member) or not staff_member.guild_permissions.administrator:
                await interaction2.response.send_message("You don't have permission to use this.", ephemeral=True)
                return

            # Public edit without revealing staff member
            try:
                await interaction2.response.edit_message(content="Application accepted.", embed=interaction2.message.embeds[0], view=None)
            except:
                try:
                    await interaction2.message.edit(content="Application accepted.", view=None)
                except:
                    pass

            # DM applicant (anonymous)
            try:
                applicant = await bot.fetch_user(self.target_user_id)
                await applicant.send(green_embed("Application Result", "Your application was accepted."))
            except:
                pass

            # give role if applicable + track for everything wave
            try:
                guild = interaction2.guild or (await bot.fetch_guild(GUILD_IDS) if isinstance(GUILD_IDS, int) else None)
                if guild:
                    role_id = None
                    target_set = None

                    if self.app_type == "caster":
                        role_id = CASTER_ROLE_ID
                        target_set = NEW_CASTERS
                    elif self.app_type in ("ref", "referee"):
                        role_id = REF_ROLE_ID
                        target_set = NEW_REFS
                    elif self.app_type == "commentator":
                        role_id = COMMENTATOR_ROLE_ID
                        target_set = NEW_COMMENTATORS
                    elif self.app_type == "staff":
                        role_id = HELPER_ROLE_ID
                        target_set = NEW_STAFF

                    if role_id:
                        role = guild.get_role(role_id) or await guild.fetch_role(role_id)
                        if role:
                            try:
                                member = await guild.fetch_member(self.target_user_id)
                                await member.add_roles(role, reason="Application accepted")
                                if target_set is not None:
                                    target_set.add(member.id)
                            except discord.NotFound:
                                pass
                            except:
                                pass
            except:
                pass

            # TEAM: send /create-team line then delete
            if self.app_type == "team":
                try:
                    chan = bot.get_channel(TRANSACTIONS_CHANNEL_ID) or await bot.fetch_channel(TRANSACTIONS_CHANNEL_ID)
                    team_name = self.answers.get("1", "Unknown Team")
                    color = "ffffff"
                    captain_mention = f"<@{self.target_user_id}>"
                    team_command = f'/create-team "{team_name}" {captain_mention} {color}'
                    msg = await chan.send(team_command)
                    try:
                        await msg.delete()
                    except:
                        pass
                except:
                    pass

        @discord.ui.button(label="Deny", style=discord.ButtonStyle.red, custom_id="app_deny")
        async def deny(self, interaction2: discord.Interaction, button: Button):
            staff_member = interaction2.user
            if not isinstance(staff_member, discord.Member) or not staff_member.guild_permissions.administrator:
                await interaction2.response.send_message("You don't have permission to use this.", ephemeral=True)
                return

            # Public edit without revealing staff member
            try:
                await interaction2.response.edit_message(content="Application denied.", embed=interaction2.message.embeds[0], view=None)
            except:
                try:
                    await interaction2.message.edit(content="Application denied.", view=None)
                except:
                    pass

            # DM applicant (anonymous)
            try:
                u = await bot.fetch_user(self.target_user_id)
                await u.send(embed=green_embed("Application Result", "Your application was denied."))
            except:
                pass

    # send to applications channel
    try:
        app_channel = bot.get_channel(APPLICATION_CHANNEL_ID) or await bot.fetch_channel(APPLICATION_CHANNEL_ID)
        view = StaffDecisionView(user.id, app_type, answers)
        await app_channel.send(embed=embed, view=view)
    except Exception:
        await dm.send("Error: application channel not configured or bot lacks permission to post. Contact an admin.")
        return

# ---------- Applications Panel ----------
class ApplicationsPanelView(View):
    def __init__(self):
        super().__init__(timeout=None)

    async def _start_if_open(self, interaction: discord.Interaction, key: str, user_friendly: str):
        if not APP_STATUS.get(key, True):
            await interaction.response.send_message(f"{user_friendly} applications are currently closed.", ephemeral=True)
            return
        await interaction.response.send_message(f"Starting {user_friendly} application — check your DMs.", ephemeral=True)
        await start_application_flow(interaction.user, key, interaction)

    @discord.ui.button(custom_id="panel_ref", label="Referee Applications", style=discord.ButtonStyle.primary)
    async def ref_button(self, interaction: discord.Interaction, button: Button):
        await self._start_if_open(interaction, "ref", "Referee")

    @discord.ui.button(custom_id="panel_commentator", label="Commentator Applications", style=discord.ButtonStyle.primary)
    async def commentator_button(self, interaction: discord.Interaction, button: Button):
        await self._start_if_open(interaction, "commentator", "Commentator")

    @discord.ui.button(custom_id="panel_caster", label="Caster Applications", style=discord.ButtonStyle.primary)
    async def caster_button(self, interaction: discord.Interaction, button: Button):
        await self._start_if_open(interaction, "caster", "Caster")

    @discord.ui.button(custom_id="panel_staff", label="Staff Applications", style=discord.ButtonStyle.primary)
    async def staff_button(self, interaction: discord.Interaction, button: Button):
        await self._start_if_open(interaction, "staff", "Staff")

    @discord.ui.button(custom_id="panel_team", label="Team Applications", style=discord.ButtonStyle.primary)
    async def team_button(self, interaction: discord.Interaction, button: Button):
        await self._start_if_open(interaction, "team", "Team")

def build_panel_content():
    content = (
        "# 📝Applications 📝 #\n"
        "Welcome to Pro Division Association. We are currently looking for active refs, casters, commentators, and "
        "staff members. If you would like to be apart of our team please apply and provide sources.\n\n"
        "● Ref Application\n"
        "● Commentator Application\n"
        "● Caster Application\n"
        "● Staff Application\n"
        "● Team Applications\n\n"
        "We really appreciate yall taking your time out of your day to apply and to try to be apart of our team. "
        "This means a lot to the PDA boards and staff for helping us through the scrims and server. We hope you "
        "enjoy your time here and thank you for applying.\n\n"
        "Your fellow\n"
        "Boards of PDA"
    )
    return content

# ---------- on_ready & slash registration ----------
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    try:
        tree = bot.tree
        guild_obj = discord.Object(id=GUILD_IDS) if isinstance(GUILD_IDS, int) else None

        # helper to format new-accept lists
        def fmt_new(ids_set):
            if not ids_set:
                return "• None this wave."
            return "\n".join(f"• <@{uid}>" for uid in ids_set)

        # /register
        @tree.command(
            name="register",
            description="Start an application (Caster / Ref / Commentator / Staff / Team)",
            guild=guild_obj
        )
        async def register_command(interaction: discord.Interaction):
            guild_id = interaction.guild.id if interaction.guild else None
            if guild_id and PANEL_MESSAGES.get(guild_id):
                ch_id, msg_id = PANEL_MESSAGES[guild_id][0]
                try:
                    ch = interaction.guild.get_channel(ch_id) or await interaction.guild.fetch_channel(ch_id)
                    await ch.fetch_message(msg_id)
                    await interaction.response.send_message(
                        f"A panel has already been made — please go apply here <#{ch_id}>",
                        ephemeral=True
                    )
                    return
                except Exception:
                    PANEL_MESSAGES[guild_id].pop(0)
                    if not PANEL_MESSAGES[guild_id]:
                        PANEL_MESSAGES.pop(guild_id, None)

            view = RegisterSelect()
            await interaction.response.send_message("Select application type:", view=view, ephemeral=True)

        # /manage
        @tree.command(name="manage", description="Open or close an application type", guild=guild_obj)
        @app_commands.describe(action="open or close", app="application type to manage")
        @app_commands.choices(
            action=[
                app_commands.Choice(name="open", value="open"),
                app_commands.Choice(name="close", value="close"),
            ],
            app=[
                app_commands.Choice(name="caster", value="caster"),
                app_commands.Choice(name="ref", value="ref"),
                app_commands.Choice(name="commentator", value="commentator"),
                app_commands.Choice(name="staff", value="staff"),
                app_commands.Choice(name="team", value="team"),
            ]
        )
        async def manage_command(
            interaction: discord.Interaction,
            action: app_commands.Choice[str],
            app: app_commands.Choice[str]
        ):
            member = interaction.user
            if not isinstance(member, discord.Member) or not member.guild_permissions.administrator:
                await interaction.response.send_message(
                    "You must be an administrator to use this command.",
                    ephemeral=True
                )
                return

            app_key = app.value
            if action.value == "close":
                APP_STATUS[app_key] = False
                await interaction.response.send_message(
                    f"{app_key.capitalize()} application closed.\n\nThis app has been closed by an admin",
                    ephemeral=True
                )
            else:
                APP_STATUS[app_key] = True
                await interaction.response.send_message(
                    f"{app_key.capitalize()} application opened.",
                    ephemeral=True
                )

            guild_id = interaction.guild.id if interaction.guild else None
            if not guild_id:
                return

            entries = PANEL_MESSAGES.get(guild_id, [])
            if not entries:
                return

            content = build_panel_content()
            view = ApplicationsPanelView()
            for child in view.children:
                cid = getattr(child, "custom_id", None)
                if cid == "panel_ref":
                    child.disabled = not APP_STATUS.get("ref", True)
                elif cid == "panel_commentator":
                    child.disabled = not APP_STATUS.get("commentator", True)
                elif cid == "panel_caster":
                    child.disabled = not APP_STATUS.get("caster", True)
                elif cid == "panel_staff":
                    child.disabled = not APP_STATUS.get("staff", True)
                elif cid == "panel_team":
                    child.disabled = not APP_STATUS.get("team", True)

            valid_entries = []
            for ch_id, msg_id in list(entries):
                try:
                    ch = interaction.guild.get_channel(ch_id) or await interaction.guild.fetch_channel(ch_id)
                    msg = await ch.fetch_message(msg_id)
                    await msg.edit(content=content, view=view)
                    valid_entries.append((ch_id, msg_id))
                except Exception:
                    continue

            if valid_entries:
                PANEL_MESSAGES[guild_id] = valid_entries
            else:
                PANEL_MESSAGES.pop(guild_id, None)

        # /panel - single message containing content + buttons
        @tree.command(
            name="panel",
            description="Post the applications panel (admins only)",
            guild=guild_obj
        )
        @app_commands.describe(channel="Channel to post the applications panel in")
        async def panel_command(interaction: discord.Interaction, channel: TextChannel):
            member = interaction.user
            if not isinstance(member, discord.Member) or not member.guild_permissions.administrator:
                await interaction.response.send_message(
                    "You must be an administrator to use this command.",
                    ephemeral=True
                )
                return

            content = build_panel_content()
            view = ApplicationsPanelView()
            for child in view.children:
                cid = getattr(child, "custom_id", None)
                if cid == "panel_ref":
                    child.disabled = not APP_STATUS.get("ref", True)
                elif cid == "panel_commentator":
                    child.disabled = not APP_STATUS.get("commentator", True)
                elif cid == "panel_caster":
                    child.disabled = not APP_STATUS.get("caster", True)
                elif cid == "panel_staff":
                    child.disabled = not APP_STATUS.get("staff", True)
                elif cid == "panel_team":
                    child.disabled = not APP_STATUS.get("team", True)

            try:
                msg = await channel.send(content, view=view)
                guild_id = interaction.guild.id if interaction.guild else None
                if guild_id:
                    PANEL_MESSAGES.setdefault(guild_id, []).append((channel.id, msg.id))
                await interaction.response.send_message(
                    f"Panel posted in {channel.mention}.",
                    ephemeral=True
                )
            except Exception:
                await interaction.response.send_message(
                    "Failed to post panel. Make sure I have permission to send messages and manage messages in that channel.",
                    ephemeral=True
                )

        # /announcements
        @tree.command(
            name="announcements",
            description="Send league announcements (teams / everything wave)",
            guild=guild_obj
        )
        @app_commands.describe(
            teams="Send the teams announcement",
            everything_wave="Send the Everything Wave announcement"
        )
        async def announcements_command(
            interaction: discord.Interaction,
            teams: bool = False,
            everything_wave: bool = False
        ):
            member = interaction.user
            if not isinstance(member, discord.Member) or not member.guild_permissions.administrator:
                await interaction.response.send_message(
                    "You must be an administrator to use this command.",
                    ephemeral=True
                )
                return

            if not teams and not everything_wave:
                await interaction.response.send_message(
                    "You must select at least one of: `teams` or `everything_wave`.",
                    ephemeral=True
                )
                return

            guild = interaction.guild
            if not guild:
                await interaction.response.send_message(
                    "This command can only be used in a server.",
                    ephemeral=True
                )
                return

            # Resolve announcements channel
            ann_channel = (
                guild.get_channel(ANNOUNCEMENTS_CHANNEL_ID)
                or await bot.fetch_channel(ANNOUNCEMENTS_CHANNEL_ID)
            )
            if not isinstance(ann_channel, discord.TextChannel):
                await interaction.response.send_message(
                    "Announcements channel is not configured correctly. Check ANNOUNCEMENTS_CHANNEL_ID.",
                    ephemeral=True
                )
                return

            # ----- TEAMS ANNOUNCEMENT -----
            if teams:
                teams_count = len(TEAMS_FOR_ANNOUNCEMENT)
                teams_list_text = "\n".join(f"• {name}" for name in TEAMS_FOR_ANNOUNCEMENT)

                teams_announcement = (
                    "@everyone\n"
                    "🏆 ALL TEAMS HAVE BEEN DECIDED 🏆\n\n"
                    "After going through every application, we are officially locked in for Season X. "
                    "Huge congratulations to every team that made it in. We’re excited to see what every roster "
                    "brings this season. 👀\n\n"
                    f"HERE ARE YOUR OFFICIAL {teams_count} TEAMS:\n\n"
                    f"{teams_list_text}\n\n"
                    "Teams will have a week to get all players before roster lock."
                )

                await ann_channel.send(teams_announcement)

                # Automatically create teams in the transactions channel (if configured)
                try:
                    if TEAMS_FOR_CREATION:
                        tx_channel = (
                            bot.get_channel(TRANSACTIONS_CHANNEL_ID)
                            or await bot.fetch_channel(TRANSACTIONS_CHANNEL_ID)
                        )
                        for team_name, color_hex, captain_id in TEAMS_FOR_CREATION:
                            captain_mention = f"<@{captain_id}>"
                            color_clean = color_hex.lstrip("#")
                            if len(color_clean) != 6 or any(
                                c not in "0123456789abcdefABCDEF" for c in color_clean
                            ):
                                continue

                            create_cmd = f'/create-team "{team_name}" {captain_mention} {color_clean}'
                            tmp = await tx_channel.send(create_cmd)
                            try:
                                await tmp.delete()
                            except:
                                pass
                except:
                    pass

            # ----- EVERYTHING WAVE ANNOUNCEMENT (only newly accepted this wave) -----
            if everything_wave:
                helper_mention = f"<@&{HELPER_ROLE_ID}>"

                refs_block = fmt_new(NEW_REFS)
                casters_block = fmt_new(NEW_CASTERS)
                staff_block = fmt_new(NEW_STAFF)
                commentators_block = fmt_new(NEW_COMMENTATORS)

                everything_announcement = (
                    "@here\n\n"
                    "# 🌊 Everything Wave!! 🌊\n\n"
                    "An Everything Wave is gonna happen every few weeks so we can give people the positions they "
                    "deserve and help out the server.\n\n"
                    "This includes:\n"
                    "• Referees\n"
                    "• Casters\n"
                    "• Staff\n"
                    "• Commentators\n\n"
                    "# Referees\n\n"
                    f"{refs_block}\n\n"
                    "# Casters\n\n"
                    f"{casters_block}\n\n"
                    "# Staff\n"
                    f"These people will be {helper_mention} until next staff wave\n"
                    f"{staff_block}\n\n"
                    "# Commentators\n\n"
                    f"{commentators_block}\n\n"
                    "If you think you can help CTG grow and improve, make sure to apply <#1490026985832054794>\n"
                )

                await ann_channel.send(everything_announcement)

                # clear for next wave
                NEW_REFS.clear()
                NEW_CASTERS.clear()
                NEW_STAFF.clear()
                NEW_COMMENTATORS.clear()

            await interaction.response.send_message(
                f"Announcement(s) sent in {ann_channel.mention}.",
                ephemeral=True
            )

        # sync commands
        if guild_obj:
            await tree.sync(guild=guild_obj)
        else:
            await tree.sync()
        print("Slash commands registered.")
    except Exception as e:
        print("Failed to register command:", e)

# Start the bot
bot.run(os.getenv("BOT_TOKEN"))
