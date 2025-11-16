import discord
from discord.ext import commands
from flask import Flask, request, jsonify
import threading
import asyncio
import requests
import logging

logging.getLogger('werkzeug').setLevel(logging.ERROR)

N8N_WEBHOOK_URL = 'https://n8n.tradiateam.xyz/webhook-test/db8b659d-3849-40d9-b78f-cffd000f67ce'
FORUM_CHANNEL_ID = 1426518118989168650
FLASK_PORT = 2022

app = Flask(__name__)

class SupportCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.flask_thread = None

        self.add_flask_route()
        print(f"[COG INIT] Forum-ID: {FORUM_CHANNEL_ID}, n8n-URL: {N8N_WEBHOOK_URL}")

    def add_flask_route(self):

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
        app.run(host='0.0.0.0', port=FLASK_PORT)

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.flask_thread:
            self.flask_thread = threading.Thread(target=self.run_flask)
            self.flask_thread.daemon = True
            self.flask_thread.start()
            print(f'[COG] Flask-Server für n8n-Antworten gestartet auf Port {FLASK_PORT}')

    @commands.Cog.listener()
    async def on_thread_create(self, thread):

        if thread.parent_id != FORUM_CHANNEL_ID:
            return

        try:
            first_message = await thread.fetch_message(thread.id)
        except Exception:
            print("[COG] Fehler beim Abrufen der ersten Nachricht des neuen Threads.")
            return

        payload = {
            "thread_id": str(thread.id),
            "post_title": thread.name,
            "post_content": first_message.content,
            "author": str(thread.owner),
            "post_url": thread.jump_url
        }

        try:
            response = requests.post(N8N_WEBHOOK_URL, json=payload, timeout=5)
            response.raise_for_status()
            print(f"[COG] Trigger für Thread {thread.id} erfolgreich an n8n gesendet.")
        except requests.exceptions.RequestException as e:
            print(f"[COG ERROR] FEHLER beim Senden an n8n: {e}")

async def setup(bot):
    await bot.add_cog(SupportCog(bot))