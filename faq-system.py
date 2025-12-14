import discord
from discord import app_commands
from discord.ext import commands
from pymongo import MongoClient
from bson.objectid import ObjectId
import dotenv
import os

dotenv.load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = "serverdata"
COLLECTION_NAME = "faq"

def get_faq_collection():
    """Stellt die MongoDB-Verbindung her und gibt die Collection zurück."""
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    return db[COLLECTION_NAME]

def fetch_all_faq_items(collection):
    """Ruft alle FAQs ab und konvertiert _id zu String."""
    faq_items_cursor = collection.find()
    return [{"question": item["question"], "answer": item["answer"], "_id": str(item["_id"])} for item in faq_items_cursor]

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

class PersistentFAQSelect(discord.ui.Select):
    def __init__(self):
        super().__init__(
            placeholder='Wähle eine Frage aus, um die Antwort zu sehen...',
            custom_id="persistent_faq_selector",
            min_values=1,
            max_values=1,
        )
        self.collection = get_faq_collection()
        self.update_options_from_db()

    def update_options_from_db(self):
        """Aktualisiert die Optionen vor dem Senden oder beim Start."""
        faq_items = fetch_all_faq_items(self.collection)
        self.options.clear()

        if faq_items:
            for item in faq_items:
                self.options.append(discord.SelectOption(
                    label=item["question"][:100],
                    value=item["_id"]
                ))
        else:
            self.options.append(discord.SelectOption(
                label="Keine FAQs gefunden.",
                value="no_faq",
                default=True,
                description="Bitte einen Admin hinzufügen lassen."
            ))
            self.disabled = True

        return faq_items

    async def callback(self, interaction: discord.Interaction):
        selected_id = self.values[0]

        if selected_id == "no_faq":
            await interaction.response.send_message('Es sind derzeit keine FAQ-Fragen verfügbar.', ephemeral=True)
            return

        faq_item_doc = self.collection.find_one({"_id": ObjectId(selected_id)})

        if faq_item_doc:
            await interaction.response.send_message(
                f'**Frage:** {faq_item_doc["question"]}\n\n**Antwort:** {faq_item_doc["answer"]}',
                ephemeral=True
            )
        else:
            await interaction.response.send_message('❌ Fehler: FAQ Eintrag nicht gefunden. Das Panel muss möglicherweise neu gesendet werden.', ephemeral=True)


class PersistentFAQView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot
        self.add_item(PersistentFAQSelect())

class DeleteFAQSelect(discord.ui.Select):
    def __init__(self, faq_items, collection):
        options = []
        for item in faq_items:
            options.append(discord.SelectOption(
                label=item["question"][:100],
                value=item["_id"]
            ))

        super().__init__(
            placeholder='Wähle eine FAQ zum LÖSCHEN aus...',
            min_values=1,
            max_values=1,
            options=options
        )
        self.collection = collection
        self.faq_items = faq_items

    async def callback(self, interaction: discord.Interaction):
        selected_id_str = self.values[0]

        try:
            object_id = ObjectId(selected_id_str)
            result = self.collection.delete_one({"_id": object_id})

            if result.deleted_count == 1:
                deleted_question = next((item["question"] for item in self.faq_items if item["_id"] == selected_id_str), "Unbekannte Frage")

                await interaction.response.send_message(
                    f'✅ FAQ Eintrag erfolgreich gelöscht: **{deleted_question}**. Bitte das FAQ-Panel neu senden, damit die Änderung sichtbar wird.',
                    ephemeral=True
                )
            else:
                await interaction.response.send_message('❌ Fehler beim Löschen: Eintrag nicht gefunden.', ephemeral=True)

        except Exception as e:
            await interaction.response.send_message(
                f'❌ Ein Fehler ist aufgetreten: {e}',
                ephemeral=True
            )

class DeleteFAQView(discord.ui.View):
    def __init__(self, faq_items, collection):
        super().__init__(timeout=180)
        self.add_item(DeleteFAQSelect(faq_items, collection))

class FAQSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.collection = get_faq_collection()

    @app_commands.command(name="add-faq", description="ADMIN: Fügt eine FAQ-Frage hinzu.")
    @app_commands.checks.has_permissions(administrator=True)
    async def add_faq_command(self, interaction: discord.Interaction):
        await interaction.response.send_modal(AddFAQModal(self.collection))

    @app_commands.command(name="delete-faq", description="ADMIN: Löscht eine existierende FAQ-Frage.")
    @app_commands.checks.has_permissions(administrator=True)
    async def delete_faq_command(self, interaction: discord.Interaction):
        faq_items = fetch_all_faq_items(self.collection)

        if not faq_items:
            await interaction.response.send_message("Es sind derzeit keine FAQs zum Löschen vorhanden.", ephemeral=True)
            return

        embed = discord.Embed(
            title="🗑️ FAQ Lösch-Tool",
            description="Wähle eine Frage aus dem Menü, um sie unwiderruflich zu LÖSCHEN.",
            color=discord.Color.red()
        )

        view = DeleteFAQView(faq_items, self.collection)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @commands.command(name="faq-panel")
    @commands.has_permissions(administrator=True)
    async def send_faq_panel(self, ctx):
        view = PersistentFAQView(self.bot)
        view.children[0].update_options_from_db()

        embed = discord.Embed(
            title="📚 Häufig gestellte Fragen (FAQ)",
            description="Wähle eine Frage aus dem Dropdown-Menü, um die entsprechende Antwort zu sehen.",
            color=discord.Color.blue()
        )

        await ctx.channel.send(embed=embed, view=view)


async def setup(bot):
    await bot.add_cog(FAQSystem(bot))