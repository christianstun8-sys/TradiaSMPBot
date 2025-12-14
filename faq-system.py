import discord
from discord.ext import commands
from pymongo import MongoClient
import dotenv
import os

dotenv.load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = "serverdata"
COLLECTION_NAME = "faq"


class AddFAQModal(discord.ui.Modal, title='FAQ Eintrag hinzufügen'):
    def __init__(self, collection):
        super().__init__()
        self.collection = collection

    question = discord.ui.TextInput(
        label='Frage',
        placeholder='Gib hier die Frage ein...',
        style=discord.TextStyle.short,
        max_length=100
    )

    answer = discord.ui.TextInput(
        label='Antwort',
        placeholder='Gib hier die detaillierte Antwort ein...',
        style=discord.TextStyle.long
    )

    async def on_submit(self, interaction: discord.Interaction):
        faq_data = {
            "question": str(self.question),
            "answer": str(self.answer),
            "added_by": interaction.user.id
        }

        try:
            self.collection.insert_one(faq_data)
            await interaction.response.send_message(
                f'✅ FAQ Eintrag erfolgreich hinzugefügt: **{self.question}**',
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f'❌ Fehler beim Speichern des Eintrags: {e}',
                ephemeral=True
            )

class FAQSelect(discord.ui.Select):
    def __init__(self, faq_items):
        options = []
        for i, item in enumerate(faq_items):
            options.append(discord.SelectOption(
                label=item["question"][:100],
                value=item["_id"]
            ))

        super().__init__(
            placeholder='Wähle eine Frage aus, um die Antwort zu sehen...',
            min_values=1,
            max_values=1,
            options=options
        )
        self.faq_items = faq_items

    async def callback(self, interaction: discord.Interaction):
        selected_id = self.values[0]
        faq_item = next((item for item in self.faq_items if str(item["_id"]) == selected_id), None)

        if faq_item:
            await interaction.response.send_message(
                f'**Frage:** {faq_item["question"]}\n\n**Antwort:** {faq_item["answer"]}',
                ephemeral=True
            )
        else:
            await interaction.response.send_message('❌ Fehler: FAQ Eintrag nicht gefunden.', ephemeral=True)

class FAQView(discord.ui.View):
    def __init__(self, faq_items):
        super().__init__(timeout=180)
        self.add_item(FAQSelect(faq_items))


class FAQSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.client = MongoClient(MONGO_URI)
        self.db = self.client[DB_NAME]
        self.collection = self.db[COLLECTION_NAME]

    @commands.command(name="add-faq")
    @commands.has_permissions(administrator=True)
    async def add_faq_command(self, ctx):
        await ctx.interaction.response.send_modal(AddFAQModal(self.collection))

    @commands.command(name="faq-panel")
    async def faq_panel_command(self, ctx):
        faq_items_cursor = self.collection.find()
        faq_items = [{"question": item["question"], "answer": item["answer"], "_id": str(item["_id"])} for item in faq_items_cursor]

        if not faq_items:
            await ctx.send("Es sind derzeit keine FAQ-Fragen verfügbar...", ephemeral=True)
            return

        embed = discord.Embed(
            title="📚 Häufig gestellte Fragen (FAQ)",
            description="Wähle eine Frage aus dem Dropdown-Menü, um die entsprechende Antwort zu sehen.",
            color=discord.Color.blue()
        )

        view = FAQView(faq_items)
        await ctx.send(embed=embed, view=view)


async def setup(bot):
    await bot.add_cog(FAQSystem(bot))