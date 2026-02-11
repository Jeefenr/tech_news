from flask import Flask, render_template

app = Flask(__name__)

dummy_news = [
    {"title": "Python 3.13 вийшов!", "source": "Official", "published": "2026-01-25"},
    {"title": "Штучний інтелект замінить програмістів?", "source": "TechBlog", "published": "2026-01-26"}
]

@app.route('/')
def index():
    return render_template('index.html', news=dummy_news)

@app.route('/about')
def about():
    return render_template('about.html')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')