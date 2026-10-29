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

    # --------------------------------------------
    # DESIGN CLAIM 22: NEWCOMER ONBOARDING
    # --------------------------------------------

    # Save whether each user has acknowledged the rules.
    with app.app_context():
        db = get_db()
        db.execute("""
            CREATE TABLE IF NOT EXISTS newcomer_onboarding (
                user_id INTEGER PRIMARY KEY,
                rules_acknowledged INTEGER NOT NULL DEFAULT 0
            )
        """)
        db.commit()

    @app.route("/onboarding")
    def newcomer_onboarding():

        user_id = session.get("user_id")

        if not user_id:
            flash("Please log in first.", "warning")
            return redirect(url_for("login"))

        db = get_db()

        # Step 1: Has the user acknowledged the rules?
        rules = db.execute(
            """
            SELECT rules_acknowledged
            FROM newcomer_onboarding
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()

        rules_done = bool(rules and rules["rules_acknowledged"])

        # Step 2: Has the user introduced themselves?
        introduction = db.execute(
            """
            SELECT COUNT(*) AS total
            FROM newcomer_introductions
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()

        introduction_done = introduction["total"] > 0

        # Step 3: Does the user follow another member?
        following = db.execute(
            """
            SELECT COUNT(*) AS total
            FROM follows
            WHERE follower_id = ?
              AND followed_id != ?
            """,
            (user_id, user_id),
        ).fetchone()

        following_done = following["total"] > 0

        # Step 4: Has the user commented on another user's post?
        discussion = db.execute(
            """
            SELECT COUNT(*) AS total
            FROM comments c
            JOIN posts p ON c.post_id = p.id
            WHERE c.user_id = ?
              AND p.user_id != ?
            """,
            (user_id, user_id),
        ).fetchone()

        discussion_done = discussion["total"] > 0

        # Calculate progress from completed activities.
        steps = [
            rules_done,
            introduction_done,
            following_done,
            discussion_done,
        ]

        completed = sum(steps)
        progress = int((completed / len(steps)) * 100)

        return render_template_string(
            """
        <!doctype html>
        <html>
        <head>
            <title>My MiniSocial Journey</title>
            <link rel="stylesheet"
              href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css">
        </head>

        <body class="container py-4">

            <a href="/" class="btn btn-secondary mb-3">
                Back to Home
            </a>

            <h2>My MiniSocial Journey</h2>

            <p>
                Complete these activities to get familiar
                with the community.
            </p>

            <div class="card p-4 mb-4">

                <h5>Your Progress: {{ completed }}/4</h5>

                <div class="progress mb-3" style="height: 25px;">
                    <div class="progress-bar bg-success"
                         role="progressbar"
                         style="width: {{ progress }}%;"
                         aria-valuenow="{{ progress }}"
                         aria-valuemin="0"
                         aria-valuemax="100">
                        {{ progress }}%
                    </div>
                </div>

                {% if completed == 4 %}
                <div class="alert alert-success">
                    Congratulations! You have completed
                    your newcomer journey!
                </div>
                {% endif %}

                <div class="list-group">

                    <!-- STEP 1 -->
                    <div class="list-group-item p-3">
                        <h5>
                            {% if rules_done %}✅{% else %}⬜{% endif %}
                            1. Learn the Community Rules
                        </h5>

                        <p>
                            Understand how to participate
                            respectfully in MiniSocial.
                        </p>

                        <a href="/rules"
                           class="btn btn-outline-primary btn-sm">
                            Read Rules
                        </a>

                        {% if not rules_done %}
                        <form method="POST"
                              action="{{ url_for('acknowledge_newcomer_rules') }}"
                              class="mt-2">

                            <button type="submit"
                                    class="btn btn-primary btn-sm">
                                I Have Read the Rules
                            </button>
                        </form>
                        {% else %}
                        <span class="badge bg-success">
                            Completed
                        </span>
                        {% endif %}
                    </div>

                    <!-- STEP 2 -->
                    <div class="list-group-item p-3">
                        <h5>
                            {% if introduction_done %}✅{% else %}⬜{% endif %}
                            2. Introduce Yourself
                        </h5>

                        <p>
                            Tell the community about yourself
                            and your interests.
                        </p>

                        {% if introduction_done %}
                        <span class="badge bg-success">Completed</span>
                        {% else %}
                        <a href="{{ url_for('newcomers') }}"
                           class="btn btn-primary btn-sm">
                            Write Introduction
                        </a>
                        {% endif %}
                    </div>

                    <!-- STEP 3 -->
                    <div class="list-group-item p-3">
                        <h5>
                            {% if following_done %}✅{% else %}⬜{% endif %}
                            3. Follow Another Member
                        </h5>

                        <p>
                            Find someone interesting and follow
                            their posts.
                        </p>

                        {% if following_done %}
                        <span class="badge bg-success">Completed</span>
                        {% else %}
                        <a href="/"
                           class="btn btn-primary btn-sm">
                            Discover Members
                        </a>
                        {% endif %}
                    </div>

                    <!-- STEP 4 -->
                    <div class="list-group-item p-3">
                        <h5>
                            {% if discussion_done %}✅{% else %}⬜{% endif %}
                            4. Join a Discussion
                        </h5>

                        <p>
                            Comment on another member's post
                            and join the conversation.
                        </p>

                        {% if discussion_done %}
                        <span class="badge bg-success">Completed</span>
                        {% else %}
                        <a href="/?sort=needs_reply"
                           class="btn btn-primary btn-sm">
                            Find a Discussion
                        </a>
                        {% endif %}
                    </div>

                </div>
            </div>
        </body>
        </html>
        """,
            completed=completed,
            progress=progress,
            rules_done=rules_done,
            introduction_done=introduction_done,
            following_done=following_done,
            discussion_done=discussion_done,
        )

    # Mark the community rules as acknowledged.
    @app.route("/onboarding/acknowledge", methods=["POST"])
    def acknowledge_newcomer_rules():

        user_id = session.get("user_id")

        if not user_id:
            abort(403)

        db = get_db()

        db.execute(
            """
            INSERT INTO newcomer_onboarding
            (user_id, rules_acknowledged)
            VALUES (?, 1)
            ON CONFLICT(user_id)
            DO UPDATE SET rules_acknowledged = 1
            """,
            (user_id,),
        )

        db.commit()

        return redirect(url_for("newcomer_onboarding"))
