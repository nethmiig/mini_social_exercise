from flask import (
    request,
    session,
    redirect,
    url_for,
    flash,
    abort,
    render_template_string,
)


def register_assignment3_features(app, get_db, moderate_content):

    # Store newcomer introductions and responses.
    with app.app_context():
        db = get_db()

        db.execute("""
            CREATE TABLE IF NOT EXISTS newcomer_introductions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS newcomer_replies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                introduction_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        db.commit()

    # Display introductions and welcoming messages.
    @app.route("/newcomers")
    def newcomers():

        db = get_db()

        introductions = db.execute("""
            SELECT i.id, i.user_id, i.content,
                   i.created_at, u.username
            FROM newcomer_introductions i
            JOIN users u ON u.id = i.user_id
            ORDER BY i.created_at DESC
        """).fetchall()

        replies = db.execute("""
            SELECT r.introduction_id, r.content,
                   r.created_at, u.username
            FROM newcomer_replies r
            JOIN users u ON u.id = r.user_id
            ORDER BY r.created_at ASC
        """).fetchall()

        return render_template_string(
            """
        <!doctype html>
        <html>
        <head>
            <title>Welcome to MiniSocial</title>
            <link rel="stylesheet"
              href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css">
        </head>
        <body class="container py-4">

            <a href="/" class="btn btn-secondary mb-3">
                Back to Home
            </a>

            <h2>Welcome to MiniSocial!</h2>
            <p>Introduce yourself and meet other members.</p>

            {% if session.get('user_id') %}
            <div class="card p-3 mb-4">
                <h5>Introduce Yourself</h5>

                <form method="POST"
                      action="{{ url_for('add_introduction') }}">

                    <textarea name="content"
                              class="form-control mb-2"
                              placeholder="Hi! I'm new here. My interests are..."
                              maxlength="1000"
                              required></textarea>

                    <button class="btn btn-primary">
                        Share Introduction
                    </button>
                </form>
            </div>
            {% endif %}

            <h4>Meet Our New Members</h4>

            {% for intro in introductions %}
            <div class="card p-3 mb-3">
                <strong>@{{ intro.username }}</strong>
                <p class="mt-2">{{ intro.content }}</p>

                <h6>Welcoming Replies</h6>

                {% for reply in replies %}
                    {% if reply.introduction_id == intro.id %}
                    <div class="alert alert-light border py-2">
                        <strong>@{{ reply.username }}</strong>:
                        {{ reply.content }}
                    </div>
                    {% endif %}
                {% endfor %}

                {% if session.get('user_id')
                      and session.get('user_id') != intro.user_id %}
                <form method="POST"
                      action="{{ url_for('reply_to_newcomer', intro_id=intro.id) }}">

                    <input name="content"
                           class="form-control mb-2"
                           placeholder="Write a welcoming message..."
                           maxlength="500"
                           required>

                    <button class="btn btn-sm btn-success">
                        Send Welcome
                    </button>
                </form>
                {% endif %}
            </div>
            {% else %}
                <p>No introductions yet. Be the first!</p>
            {% endfor %}

        </body>
        </html>
        """,
            introductions=introductions,
            replies=replies,
        )

    # Save an introduction.
    @app.route("/newcomers/introduce", methods=["POST"])
    def add_introduction():

        user_id = session.get("user_id")
        if not user_id:
            abort(403)

        content = request.form.get("content", "").strip()
        moderated, risk = moderate_content(content)

        if not content or risk >= 5:
            flash("Introduction could not be submitted.", "warning")
            return redirect(url_for("newcomers"))

        db = get_db()

        db.execute(
            """
            INSERT INTO newcomer_introductions (user_id, content)
            VALUES (?, ?)
            ON CONFLICT(user_id)
            DO UPDATE SET content = excluded.content
        """,
            (user_id, moderated),
        )

        db.commit()

        flash("Your introduction was saved!", "success")
        return redirect(url_for("newcomers"))

    # Save a welcoming reply.
    @app.route("/newcomers/<int:intro_id>/reply", methods=["POST"])
    def reply_to_newcomer(intro_id):

        user_id = session.get("user_id")
        if not user_id:
            abort(403)

        content = request.form.get("content", "").strip()
        moderated, risk = moderate_content(content)

        if not content or risk >= 5:
            flash("Reply could not be submitted.", "warning")
            return redirect(url_for("newcomers"))

        db = get_db()

        introduction = db.execute(
            "SELECT user_id FROM newcomer_introductions WHERE id = ?", (intro_id,)
        ).fetchone()

        if introduction is None:
            abort(404)

        if introduction["user_id"] == user_id:
            abort(403)

        db.execute(
            """
            INSERT INTO newcomer_replies
            (introduction_id, user_id, content)
            VALUES (?, ?, ?)
        """,
            (intro_id, user_id, moderated),
        )

        db.commit()

        flash("Your welcome message was sent!", "success")
        return redirect(url_for("newcomers"))
