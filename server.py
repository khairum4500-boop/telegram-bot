from flask import Flask
import os
import threading

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running"

def run_flask():
    # Render এর জন্য পোর্ট সেট করা
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    # ব্যাকগ্রাউন্ডে সার্ভার চালানো
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()
    
    # আপনার মেইন বট ফাইল রান করা
    import bot
