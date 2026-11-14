import asyncio, os, time, aiohttp
from aiohttp import web
import discord
from discord.ext import commands

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip().strip('"').strip("'")
LEAD_IDS = [1567026565483859991]
STAFF_ROLE_IDS = [1567026563369664590]
START_TIME, BOT_STATUS = time.time(), "Starting..."
ASSISTANT_SCORES = {}  # {user_id: completed_tasks_count}

def is_team(m: discord.Member) -> bool:
    return isinstance(m, discord.Member) and (m.id in LEAD_IDS or m.guild_permissions.administrator or any(r.id in STAFF_ROLE_IDS for r in m.roles))

async def run_web():
    app = web.Application()
    app.router.add_get("/", lambda r: web.Response(text=f"Bot Lead Taskboard 24/7 | Up: {int((time.time()-START_TIME)//60)}m | Status: {BOT_STATUS}"))
    runner = web.AppRunner(app); await runner.setup()
    try: await web.TCPSite(runner, "0.0.0.0", int(os.environ.get("PORT", 10000))).start()
    except Exception: pass

async def pinger():
    await asyncio.sleep(20)
    url = os.environ.get("RENDER_EXTERNAL_URL") or f"http://127.0.0.1:{os.environ.get('PORT', 10000)}/"
    async with aiohttp.ClientSession() as s:
        while True:
            try: await s.get(url, timeout=10)
            except Exception: pass
            await asyncio.sleep(240)

class TaskCardView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)

    async def set_stage(self, i: discord.Interaction, status_txt: str, color: discord.Color, done: bool = False):
        if not is_team(i.user): return await i.response.send_message("❌ Bot Lead & Assistants only.", ephemeral=True)
        emb = i.message.embeds[0]
        emb.color = color
        emb.set_field_at(2, name="📌 Task Status", value=status_txt, inline=False)
        if done:
            ASSISTANT_SCORES[i.user.id] = ASSISTANT_SCORES.get(i.user.id, 0) + 1
            for child in self.children: child.disabled = True
        await i.response.edit_message(embed=emb, view=self)

    @discord.ui.button(label="Assistant: In Progress", style=discord.ButtonStyle.primary, emoji="🔧", custom_id="task:prog")
    async def prog_b(self, i: discord.Interaction, b: discord.ui.Button):
        await self.set_stage(i, f"🔧 **In Progress** — Claimed by {i.user.mention}", discord.Color.blurple())

    @discord.ui.button(label="Ready for Bot Lead Review", style=discord.ButtonStyle.secondary, emoji="🧪", custom_id="task:rev")
    async def rev_b(self, i: discord.Interaction, b: discord.ui.Button):
        await self.set_stage(i, f"🧪 **Ready for Bot Lead Review** (Submitted by {i.user.mention})", discord.Color.gold())

    @discord.ui.button(label="Bot Lead: Approve & Complete", style=discord.ButtonStyle.success, emoji="✅", custom_id="task:done")
    async def done_b(self, i: discord.Interaction, b: discord.ui.Button):
        await self.set_stage(i, f"✅ **APPROVED & DEPLOYED** (Verified by {i.user.mention})", discord.Color.green(), True)

class BugReportModal(discord.ui.Modal, title="🐛 Submit Bot Bug or Feature Task"):
    bot_name = discord.ui.TextInput(label="Which Bot / System?", placeholder="e.g. Ticket Bot, SSU Bot, New Feature", required=True)
    details = discord.ui.TextInput(label="Describe the Bug or Task Needed", style=discord.TextStyle.paragraph, required=True)
    async def on_submit(self, i: discord.Interaction):
        emb = discord.Embed(title=f"📋 Dev Task: {self.bot_name.value}", description=self.details.value, color=discord.Color.orange())
        emb.add_field(name="👤 Submitted By", value=i.user.mention, inline=True)
        emb.add_field(name="⚡ Priority", value="`Normal`", inline=True)
        emb.add_field(name="📌 Task Status", value="⏳ **Waiting for Assistant Claim**", inline=False)
        await i.response.send_message(embed=emb, view=TaskCardView())

class TaskBoardPanel(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)

    @discord.ui.button(label="Submit Bot Bug / Dev Task", style=discord.ButtonStyle.primary, emoji="🛠️", custom_id="tb:new")
    async def new_b(self, i: discord.Interaction, b: discord.ui.Button):
        await i.response.send_modal(BugReportModal())

    @discord.ui.button(label="Assistant Leaderboard", style=discord.ButtonStyle.secondary, emoji="🏆", custom_id="tb:lb")
    async def lb_b(self, i: discord.Interaction, b: discord.ui.Button):
        if not ASSISTANT_SCORES:
            return await i.response.send_message("📊 No tasks completed yet!", ephemeral=True)
        top = sorted(ASSISTANT_SCORES.items(), key=lambda x: x[1], reverse=True)
        txt = "\n".join(f"`#{idx}` <@{uid}> — **`{cnt}` Tasks Completed**" for idx, (uid, cnt) in enumerate(top, 1))
        await i.response.send_message(embed=discord.Embed(title="🏆 Bot Lead & Assistants Leaderboard", description=txt, color=discord.Color.gold()), ephemeral=True)

class TaskBoardBot(commands.Bot):
    def __init__(self, msg_intent: bool = True):
        intents = discord.Intents.default(); intents.message_content = msg_intent
        super().__init__(command_prefix="!", intents=intents, help_command=None)
    async def setup_hook(self):
        self.add_view(TaskCardView()); self.add_view(TaskBoardPanel()); await self.tree.sync()
    async def on_ready(self):
        global BOT_STATUS; BOT_STATUS = f"ONLINE as {self.user}"
        print(f"✅ Bot Lead Taskboard ONLINE as {self.user}")

def reg_cmds(b: TaskBoardBot):
    @b.tree.command(name="assign", description="Assign a bot/server task to one of your Assistants")
    async def s_assign(i: discord.Interaction, assistant: discord.Member, task: str, priority: str = "High 🔥"):
        if not is_team(i.user): return await i.response.send_message("❌ Bot Lead only.", ephemeral=True)
        emb = discord.Embed(title="🛠️ OFFICIAL BOT LEAD TASK ASSIGNMENT", description=f"**Task:** {task}", color=discord.Color.red())
        emb.add_field(name="👤 Assigned Assistant", value=assistant.mention, inline=True)
        emb.add_field(name="⚡ Priority", value=f"`{priority}`", inline=True)
        emb.add_field(name="📌 Task Status", value=f"⏳ **Assigned by {i.user.mention}**", inline=False)
        await i.response.send_message(content=assistant.mention, embed=emb, view=TaskCardView())

    @b.tree.command(name="taskboard", description="Post the Bot Lead & Assistant Task Board panel")
    async def s_tb(i: discord.Interaction):
        if not is_team(i.user): return await i.response.send_message("❌ Bot Lead & Staff only.", ephemeral=True)
        emb = discord.Embed(title="🛠️ Office of the Bot Lead — Dev Task Board", description="Click below to submit a **Bot Bug / Feature Task** for the Bot Lead & Assistants, or check the **Assistant Leaderboard**!", color=discord.Color.blurple())
        await i.response.send_message(embed=emb, view=TaskBoardPanel())

async def main():
    global BOT_STATUS
    await run_web(); asyncio.create_task(pinger())
    if not BOT_TOKEN:
        BOT_STATUS = "MISSING BOT_TOKEN IN RENDER ENVIRONMENT"
        while True: await asyncio.sleep(3600)
    bot = TaskBoardBot(True); reg_cmds(bot)
    try: await bot.start(BOT_TOKEN)
    except discord.PrivilegedIntentsRequired:
        await bot.close(); bot = TaskBoardBot(False); reg_cmds(bot); await bot.start(BOT_TOKEN)
    except Exception as e:
        BOT_STATUS = f"ERROR: {type(e).__name__}: {e}"
        while True: await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
