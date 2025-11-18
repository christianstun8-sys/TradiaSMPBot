import discord
from discord.ext import commands
from flask import Flask, request, jsonify
import threading
import asyncio
import requests
import logging

# --- Konfiguration ---
N8N_WEBHOOK_URL = 'https://n8n.tradiateam.xyz/webhook/db8b659d-3849-40d9-b78f-cffd000f67ce'
FORUM_CHANNEL_ID = 1426518118989168650
FLASK_PORT = 8899 # Port für den Flask-Server

logging.getLogger('werkzeug').setLevel(logging.ERROR)

app = Flask(__name__)

class SupportCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.flask_thread = None

        self.add_flask_route()
        print(f"[COG INIT] Forum-ID: {FORUM_CHANNEL_ID}, n8n-URL: {N8N_WEBHOOK_URL}")

    def add_flask_route(self):
        """Konfiguriert die Flask-Route, die die KI-Antwort von n8n empfängt."""

        @app.route('/ki-antwort', methods=['POST'])
        def handle_ki_response():
            try:
                data = request.json
                thread_id = data.get('thread_id')
                ki_answer = data.get('ki_answer')

                if not thread_id or not ki_answer:
                    return jsonify({"error": "Missing thread_id or ki_answer"}), 400

                print(f"[FLASK] KI-Antwort für Thread {thread_id} empfangen.")

                asyncio.run_coroutine_threadsafe(
                    self.send_ki_response_to_thread(thread_id, ki_answer),
                    self.bot.loop
                )
                return jsonify({"status": "Accepted for Discord sending"}), 200

            except Exception as e:
                print(f"[FLASK ERROR] Fehler im Webhook-Handler: {e}")
                return jsonify({"error": str(e)}), 500

    async def send_ki_response_to_thread(self, thread_id, content):
        """Sendet die KI-Antwort als Bot-Nachricht in den Discord-Thread."""
        await self.bot.wait_until_ready()
        try:
            thread = self.bot.get_channel(int(thread_id))
            if thread and isinstance(thread, discord.Thread):
                await thread.send(f"🤖 **KI-Support-Assistent:**\n\n{content}")
                print(f"[DISCORD] Antwort erfolgreich im Thread {thread_id} gepostet.")
            else:
                print(f"[DISCORD] Fehler: Thread/Post mit ID {thread_id} nicht gefunden oder kein gültiger Thread.")
        except Exception as e:
            print(f"[DISCORD ERROR] Fehler beim Senden der Nachricht: {e}")

    def run_flask(self):
        """Startet den Flask-Server in einem separaten Thread."""
        app.run(host='0.0.0.0', port=FLASK_PORT)

    @commands.Cog.listener()
    async def on_ready(self):
        """Startet den Flask-Server, sobald der Bot bereit ist."""
        if not self.flask_thread:
            self.flask_thread = threading.Thread(target=self.run_flask)
            self.flask_thread.daemon = True
            self.flask_thread.start()
            print(f'[COG] Flask-Server für n8n-Antworten gestartet auf Port {FLASK_PORT}')

    async def trigger_n8n(self, message):
        """Zentrale Funktion: Sendet die Nachricht und Thread-Informationen an n8n zur KI-Verarbeitung."""
        thread = message.channel

        payload = {
            "thread_id": str(thread.id),
            "post_title": f"Neue Nachricht in Thread: {thread.name}", # Angepasster Titel für Kontext
            "post_content": message.content, # Die neue Nachricht
            "author": str(message.author),
            "post_url": message.jump_url
        }

        try:
            response = requests.post(N8N_WEBHOOK_URL, json=payload, timeout=5)
            response.raise_for_status()
            print(f"[COG] Trigger für Thread {thread.id} (Nachricht) erfolgreich an n8n gesendet.")
        except requests.exceptions.RequestException as e:
            print(f"[COG ERROR] FEHLER beim Senden an n8n: {e}")


    @commands.Cog.listener()
    async def on_thread_create(self, thread):
        """Behandelt das erstmalige Erstellen eines Forum-Posts."""
        if thread.parent_id != FORUM_CHANNEL_ID:
            return

        # Ruft die erste Nachricht ab und triggert n8n.
        try:
            first_message = await thread.fetch_message(thread.id)
            if first_message:
                await self.trigger_n8n(first_message)
        except Exception as e:
            print(f"[COG] Fehler beim Abrufen der ersten Nachricht des neuen Threads: {e}")


    @commands.Cog.listener()
    async def on_message(self, message):
        """Reagiert auf jede neue Nachricht in einem relevanten Forum-Thread."""

        # 1. Ignoriere Nachrichten außerhalb eines Threads oder von Bots
        if not isinstance(message.channel, discord.Thread) or message.author.bot:
            return

        thread = message.channel

        # 2. Prüfen, ob der Thread zu unserem Forum gehört
        if thread.parent_id == FORUM_CHANNEL_ID:

            # Die on_thread_create Funktion verarbeitet die erste Nachricht.
            # Um doppelte Trigger zu vermeiden, ignorieren wir die Nachricht, die denselben ID wie der Thread hat (die erste Nachricht).
            is_initial_message = (thread.id == message.id)

            if not is_initial_message:
                # Der Thread existiert bereits, dies ist eine neue Antwort.
                await self.trigger_n8n(message)

async def setup(bot):
    await bot.add_cog(SupportCog(bot))