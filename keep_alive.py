from flask import Flask
from threading import Thread

app = Flask("")


@app.route("/")
def home():
    return """
    <h1 style="color: #0071ad; font-family: sans-serif">Boss Discord Bot</h1>
    <h3 style="font-family: sans-serif"><a href="https://discord.com/api/oauth2/authorize?client_id=906505022441918485&permissions=448824593472&scope=bot">Add me to your server</a></h3>
    """


def run():
    app.run(host="0.0.0.0", port=8080)


def keep_alive():
    t = Thread(target=run)
    t.start()
