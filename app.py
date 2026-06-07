# pyrefly: ignore [missing-import]
from flask import Flask, render_template
# pyrefly: ignore [missing-import]
from datetime import datetime
# pyrefly: ignore [missing-import]
from installed_apps import get_application_patch_info

app = Flask(__name__)

@app.route("/")
def home():
    data = get_application_patch_info(
        datetime.now().strftime("%Y-%m-%d")
    )
    return render_template("index.html", apps=data)

app.run(host="0.0.0.0", port=5000, debug=True)