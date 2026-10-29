from flask import (
    request,
    session,
    redirect,
    url_for,
    flash,
    abort,
    render_template_string,
)

# Allowed reasons for reporting a post.
REPORT_REASONS = {
    "Spam or scam",
    "Harassment",
    "Inappropriate content",
    "Misinformation",
    "Other",
}


def register_assignment2_features(app, get_db):

    # Create a database table to store user reports.
    with app.app_context():
        db = get_db()
        db.execute("""
            CREATE TABLE IF NOT EXISTS post_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id INTEGER NOT NULL,
                reporter_id INTEGER NOT NULL,
                reason TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(post_id, reporter_id)
            )
        """)
        db.commit()

    # --------------------------------------------------
    # FEATURE 1: REPORT A POST
    # --------------------------------------------------

    @app.route("/posts/<int:post_id>/report", methods=["POST"])
    def report_post(post_id):

        user_id = session.get("user_id")

        if not user_id:
            flash("Please log in to report a post.", "warning")
            return redirect(url_for("login"))

        reason = request.form.get("reason", "").strip()

        if reason not in REPORT_REASONS:
            flash("Please choose a valid report reason.", "danger")
            return redirect(url_for("post_detail", post_id=post_id))

        db = get_db()

        # Check whether the reported post exists.
        post = db.execute("SELECT id FROM posts WHERE id = ?", (post_id,)).fetchone()

        if post is None:
            abort(404)

        # Prevent the same user reporting a post repeatedly.
        existing_report = db.execute(
            """
            SELECT id FROM post_reports
            WHERE post_id = ? AND reporter_id = ?
            """,
            (post_id, user_id),
        ).fetchone()

        if existing_report:
            flash("You have already reported this post.", "info")

        else:
            db.execute(
                """
                INSERT INTO post_reports
                (post_id, reporter_id, reason)
                VALUES (?, ?, ?)
                """,
                (post_id, user_id, reason),
            )

            db.commit()

            flash("Your report was submitted for review.", "success")

        return redirect(url_for("post_detail", post_id=post_id))

    # --------------------------------------------------
    # FEATURE 2: ADMINISTRATOR REPORTS PAGE
    # --------------------------------------------------

    @app.route("/admin/reports")
    def admin_reports():

        # Only administrators can review reports.
        if session.get("username") != "admin":
            abort(403)

        db = get_db()

        reports = db.execute("""
            SELECT
                r.id,
                r.post_id,
                r.reason,
                r.status,
                r.created_at,
                u.username
            FROM post_reports r
            LEFT JOIN users u ON u.id = r.reporter_id
            ORDER BY
                CASE
                    WHEN r.status = 'pending' THEN 0
                    ELSE 1
                END,
                r.created_at DESC,
                r.id DESC
        """).fetchall()

        return render_template_string(
            """
        <!doctype html>
        <html>
        <head>
            <title>MiniSocial Reports</title>
            <link rel="stylesheet"
              href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css">
        </head>

        <body class="container py-4">

            <h2>Reported Posts</h2>

            <p>Review reports submitted by MiniSocial users.</p>

            <a href="/admin""
               class="btn btn-secondary mb-3">
                Back to Admin Dashboard
            </a>

            <table class="table table-bordered table-striped">
                <thead>
                    <tr>
                        <th>Post ID</th>
                        <th>Reported By</th>
                        <th>Reason</th>
                        <th>Status</th>
                        <th>Actions</th>
                    </tr>
                </thead>

                <tbody>

                {% for report in reports %}
                    <tr>
                        <td>{{ report.post_id }}</td>

                        <td>{{ report.username or 'Deleted user' }}</td>

                        <td>{{ report.reason }}</td>

                        <td>
                            {% if report.status == 'pending' %}
                                <span class="badge bg-warning text-dark">
                                    Pending
                                </span>

                            {% elif report.status == 'dismissed' %}
                                <span class="badge bg-secondary">
                                    Dismissed
                                </span>

                            {% elif report.status == 'removed' %}
                                <span class="badge bg-danger">
                                    Removed
                                </span>

                            {% else %}
                                {{ report.status }}
                            {% endif %}
                        </td>

                        <td>

                            {% if report.status != 'removed' %}
                            <a class="btn btn-sm btn-primary"
                               href="{{ url_for('post_detail', post_id=report.post_id) }}">
                                View Post
                            </a>
                            {% endif %}

                            {% if report.status == 'pending' %}

                            <!-- Dismiss a report -->
                            <form method="POST"
                                  action="{{ url_for('review_post_report', report_id=report.id) }}"
                                  class="d-inline">

                                <button type="submit"
                                        class="btn btn-sm btn-success">
                                    Dismiss Report
                                </button>
                            </form>

                            <!-- Remove a reported post -->
                            <form method="POST"
                                  action="{{ url_for('remove_reported_post', report_id=report.id) }}"
                                  class="d-inline"
                                  onsubmit="return confirm('Are you sure you want to permanently remove this post?');">

                                <button type="submit"
                                        class="btn btn-sm btn-danger">
                                    Remove Post
                                </button>
                            </form>

                            {% endif %}

                        </td>
                    </tr>

                {% else %}
                    <tr>
                        <td colspan="5" class="text-center">
                            No reports found.
                        </td>
                    </tr>
                {% endfor %}

                </tbody>
            </table>

        </body>
        </html>
        """,
            reports=reports,
        )

    # --------------------------------------------------
    # FEATURE 3: DISMISS A REPORT
    # --------------------------------------------------

    @app.route("/admin/reports/<int:report_id>/dismiss", methods=["POST"])
    def review_post_report(report_id):

        if session.get("username") != "admin":
            abort(403)

        db = get_db()

        # Mark the report as dismissed.
        cursor = db.execute(
            """
            UPDATE post_reports
            SET status = 'dismissed'
            WHERE id = ? AND status = 'pending'
            """,
            (report_id,),
        )

        db.commit()

        if cursor.rowcount == 0:
            abort(404)

        flash("Report dismissed.", "success")

        return redirect(url_for("admin_reports"))

    # --------------------------------------------------
    # FEATURE 4: REMOVE A REPORTED POST
    # --------------------------------------------------

    @app.route("/admin/reports/<int:report_id>/remove", methods=["POST"])
    def remove_reported_post(report_id):

        # Prevent ordinary users from removing posts.
        if session.get("username") != "admin":
            abort(403)

        db = get_db()

        # Find the report that the administrator selected.
        report = db.execute(
            """
            SELECT post_id
            FROM post_reports
            WHERE id = ? AND status = 'pending'
            """,
            (report_id,),
        ).fetchone()

        if report is None:
            abort(404)

        post_id = report["post_id"]

        # Make sure the post still exists.
        post = db.execute("SELECT id FROM posts WHERE id = ?", (post_id,)).fetchone()

        if post is None:
            abort(404)

        try:
            # Delete associated comments.
            db.execute("DELETE FROM comments WHERE post_id = ?", (post_id,))

            # Delete associated reactions.
            db.execute("DELETE FROM reactions WHERE post_id = ?", (post_id,))

            # Remove the original post.
            db.execute("DELETE FROM posts WHERE id = ?", (post_id,))

            # Preserve all reports about this post.
            db.execute(
                """
                UPDATE post_reports
                SET status = 'removed'
                WHERE post_id = ?
                """,
                (post_id,),
            )

            # Save all database changes together.
            db.commit()

        except Exception:
            db.rollback()
            raise

        flash("Reported post removed successfully.", "success")

        return redirect(url_for("admin_reports"))
