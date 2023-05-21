from flask import Flask
import requests
from threading import Thread
import json


def render_markdown(markdown_text):
    url = "https://api.github.com/markdown"
    headers = {"Content-Type": "application/json"}
    data = {"text": markdown_text, "mode": "markdown"}
    response = requests.post(url, headers=headers, data=json.dumps(data))
    return response.text


app = Flask("")


@app.route("/")
def home():
    html = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>BOSS Bot</title>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <link rel="icon" type="image/png" href="https://i.imgur.com/3DTqt8K.png">
            <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/reset-css@5.0.1/reset.min.css">
            <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/github-markdown-css/5.2.0/github-markdown-dark.css">
            <style>
                .markdown-body {
                    box-sizing: border-box;
                    min-width: 200px;
                    max-width: 100vw;
                    margin: 0 auto;
                    padding: 45px;
                }

                @media (max-width: 767px) {
                    .markdown-body {
                        padding: 15px;
                    }
                }
            </style>
        </head>
        <body>
        <article class="markdown-body">
    """
    with open("README.md", "r", encoding="utf-8") as f:
        md = "> **This is the README.md file of the bot [Github repo](https://github.com/skyewong/boss). Check the repo for the full code and more.**\n"
        md += f.read()
        html += render_markdown(md)
    html += """
        </article>
        </body>
        </html>
    """
    return html


def run():
    app.run(host="0.0.0.0", port=8080)


def keep_alive():
    t = Thread(target=run)
    t.start()
    print("Flask app is now running")
