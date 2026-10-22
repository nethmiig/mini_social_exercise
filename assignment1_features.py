"""Weekly goals and real community membership for Coding Assignment 1.

The existing app supplies its database connection and moderation function.
Keeping these features here makes the new routes easier to find and explain.
"""
from datetime import datetime, time, timedelta, timezone
from functools import wraps
import sqlite3
from zoneinfo import ZoneInfo

from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for


HELSINKI = ZoneInfo('Europe/Helsinki')


def ensure_assignment1_tables(db):
    """Add the new tables safely, preserving existing accounts and content."""
    db.executescript('''
        CREATE TABLE IF NOT EXISTS weekly_goals (
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            week_start TEXT NOT NULL,
            target INTEGER NOT NULL CHECK (target BETWEEN 1 AND 50),
            PRIMARY KEY (user_id, week_start)
        );
        CREATE TABLE IF NOT EXISTS communities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE COLLATE NOCASE,
            description TEXT NOT NULL,
            created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS community_members (
            community_id INTEGER NOT NULL REFERENCES communities(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            joined_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (community_id, user_id)
        );
        CREATE TABLE IF NOT EXISTS community_posts (
            post_id INTEGER PRIMARY KEY REFERENCES posts(id) ON DELETE CASCADE,
            community_id INTEGER NOT NULL REFERENCES communities(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS community_posts_group ON community_posts(community_id);
        CREATE INDEX IF NOT EXISTS community_members_user ON community_members(user_id);
    ''')
    # This is an available public community, not automatic membership. Users
    # explicitly join it, or create a community with their own shared purpose.
    with db:
        db.execute('''
            INSERT OR IGNORE INTO communities (name, description)
            VALUES (?, ?)
        ''', ('Oulu Student Hub',
              'A community for students to share what they learn, ask for help and support each other.'))


def get_week_bounds(now=None):
    """Use Monday-to-Monday Helsinki weeks, with UTC bounds for SQLite.

    SQLite stores CURRENT_TIMESTAMP in UTC. Converting both boundaries
    separately also handles weeks when Finland changes daylight saving time.
    """
    local_now = (now or datetime.now(timezone.utc)).astimezone(HELSINKI)
    monday = local_now.date() - timedelta(days=local_now.weekday())
    start = datetime.combine(monday, time.min, tzinfo=HELSINKI)
    end = start + timedelta(days=7)
    return {
        'key': monday.isoformat(),
        'start_utc': start.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
        'end_utc': end.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
        'label': f"{start:%d %b} – {end - timedelta(days=1):%d %b %Y}",
    }


def get_weekly_goal_data(db, user_id, now=None):
    """Chapter 2, Claim 15: show current feedback against a saved goal."""
    week = get_week_bounds(now)
    saved = db.execute('SELECT target FROM weekly_goals WHERE user_id = ? AND week_start = ?',
                       (user_id, week['key'])).fetchone()
    target = saved['target'] if saved else 3
    # Count conversations, not repeated comments on one post. Exclude replies
    # to your own posts, and calculate from real records on each page load.
    count = db.execute('''
        SELECT COUNT(DISTINCT c.post_id) AS total
        FROM comments c JOIN posts p ON p.id = c.post_id
        WHERE c.user_id = ? AND p.user_id != ?
          AND c.created_at >= ? AND c.created_at < ?
    ''', (user_id, user_id, week['start_utc'], week['end_utc'])).fetchone()['total']
    return {
        **week, 'target': target, 'completed': count,
        'remaining': max(0, target - count),
        'percent': min(100, round(count * 100 / target)),
        'is_saved': saved is not None,
    }


def get_user_communities(db, user_id):
    return db.execute('''
        SELECT c.id, c.name FROM communities c
        JOIN community_members m ON m.community_id = c.id
        WHERE m.user_id = ? ORDER BY c.name COLLATE NOCASE
    ''', (user_id,)).fetchall()


def register_assignment1_features(app, get_db, moderate_content):
    """Register routes once when app.py starts."""
    bp = Blueprint('assignment1', __name__)

    @app.before_request
    def prepare_assignment1_tables():
        # IF NOT EXISTS makes this safe on restarts and in the debug reloader.
        # Running before routes means the existing database is upgraded for the
        # user automatically, without a separate SQL installation step.
        ensure_assignment1_tables(get_db())

    def login_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not session.get('user_id'):
                flash('Please log in to use this feature.', 'warning')
                return redirect(url_for('login'))
            return view(*args, **kwargs)
        return wrapped

    def find_community(community_id):
        community = get_db().execute('SELECT * FROM communities WHERE id = ?',
                                     (community_id,)).fetchone()
        if community is None:
            abort(404)
        return community

    @bp.route('/goals/weekly', methods=['POST'])
    @login_required
    def save_weekly_goal():
        try:
            target = int(request.form.get('target', ''))
        except ValueError:
            target = 0
        if not 1 <= target <= 50:
            flash('Choose a whole-number goal between 1 and 50 conversations.', 'warning')
            return redirect(url_for('feed'))
        week = get_week_bounds()
        db = get_db()
        with db:
            db.execute('''
                INSERT INTO weekly_goals (user_id, week_start, target) VALUES (?, ?, ?)
                ON CONFLICT(user_id, week_start) DO UPDATE SET target = excluded.target
            ''', (session['user_id'], week['key'], target))
        flash('Your goal for this week was saved.', 'success')
        return redirect(url_for('feed', _anchor='weekly-goal'))

    @bp.route('/communities', methods=['GET', 'POST'])
    def communities():
        db = get_db()
        user_id = session.get('user_id')
        if request.method == 'POST':
            if not user_id:
                return redirect(url_for('login'))
            name = request.form.get('name', '').strip()
            description = request.form.get('description', '').strip()
            if not (3 <= len(name) <= 80 and 10 <= len(description) <= 500):
                flash('Use a name of 3–80 characters and a shared purpose of 10–500 characters.', 'warning')
                return redirect(url_for('assignment1.communities'))
            try:
                with db:
                    result = db.execute('''
                        INSERT INTO communities (name, description, created_by) VALUES (?, ?, ?)
                    ''', (name, description, user_id))
                    community_id = result.lastrowid
                    # Creating a community is also an explicit choice to join it.
                    db.execute('INSERT INTO community_members (community_id, user_id) VALUES (?, ?)',
                               (community_id, user_id))
            except sqlite3.IntegrityError:
                flash('A community with that name already exists.', 'warning')
                return redirect(url_for('assignment1.communities'))
            flash('Community created. You are its first member.', 'success')
            return redirect(url_for('assignment1.community_detail', community_id=community_id))

        groups = db.execute('''
            SELECT c.*,
                (SELECT COUNT(*) FROM community_members m WHERE m.community_id = c.id) AS member_count,
                (SELECT COUNT(*) FROM community_posts cp JOIN posts p ON p.id = cp.post_id
                 JOIN users u ON u.id = p.user_id WHERE cp.community_id = c.id) AS post_count,
                EXISTS(SELECT 1 FROM community_members mine
                       WHERE mine.community_id = c.id AND mine.user_id = ?) AS is_member
            FROM communities c ORDER BY is_member DESC, c.name COLLATE NOCASE
        ''', (user_id or -1,)).fetchall()
        return render_template('communities.html.j2', communities=groups)

    @bp.route('/communities/<int:community_id>')
    def community_detail(community_id):
        community = find_community(community_id)
        db = get_db()
        user_id = session.get('user_id')
        is_member = db.execute('''
            SELECT 1 FROM community_members WHERE community_id = ? AND user_id = ?
        ''', (community_id, user_id or -1)).fetchone() is not None
        try:
            page = max(1, int(request.args.get('page', 1)))
        except ValueError:
            page = 1
        total = db.execute('''
            SELECT COUNT(*) AS total FROM community_posts cp JOIN posts p ON p.id = cp.post_id
            JOIN users u ON u.id = p.user_id WHERE cp.community_id = ?
        ''', (community_id,)).fetchone()['total']
        raw_posts = db.execute('''
            SELECT p.*, u.username,
                (SELECT COUNT(*) FROM comments cm WHERE cm.post_id = p.id) AS comment_count
            FROM community_posts cp JOIN posts p ON p.id = cp.post_id
            JOIN users u ON u.id = p.user_id
            WHERE cp.community_id = ? ORDER BY p.created_at DESC, p.id DESC
            LIMIT 10 OFFSET ?
        ''', (community_id, (page - 1) * 10)).fetchall()
        posts = []
        for row in raw_posts:
            post = dict(row)
            post['content'], _ = moderate_content(post['content'])
            posts.append(post)
        members = db.execute('''
            SELECT u.username FROM community_members m JOIN users u ON u.id = m.user_id
            WHERE m.community_id = ? ORDER BY m.joined_at, u.id
        ''', (community_id,)).fetchall()
        return render_template('community_detail.html.j2', community=community,
                               is_member=is_member, posts=posts, members=members,
                               page=page, has_next=page * 10 < total)

    @bp.route('/communities/<int:community_id>/join', methods=['POST'])
    @login_required
    def join_community(community_id):
        find_community(community_id)
        db = get_db()
        with db:
            db.execute('INSERT OR IGNORE INTO community_members (community_id, user_id) VALUES (?, ?)',
                       (community_id, session['user_id']))
        flash('You joined the community.', 'success')
        return redirect(url_for('assignment1.community_detail', community_id=community_id))

    @bp.route('/communities/<int:community_id>/leave', methods=['POST'])
    @login_required
    def leave_community(community_id):
        find_community(community_id)
        db = get_db()
        with db:
            db.execute('DELETE FROM community_members WHERE community_id = ? AND user_id = ?',
                       (community_id, session['user_id']))
        # Leaving never deletes the group or its posts: its identity and shared
        # history continue even when individual members come and go (Ch 3, Claim 1).
        flash('You left the community. Its discussions are still available.', 'success')
        return redirect(url_for('assignment1.communities'))

    @bp.route('/communities/<int:community_id>/posts', methods=['POST'])
    @login_required
    def add_community_post(community_id):
        find_community(community_id)
        db = get_db()
        user_id = session['user_id']
        member = db.execute('SELECT 1 FROM community_members WHERE community_id = ? AND user_id = ?',
                            (community_id, user_id)).fetchone()
        if member is None:
            abort(403)
        content = request.form.get('content', '').strip()
        if not 1 <= len(content) <= 5000:
            flash('Write a post between 1 and 5000 characters.', 'warning')
            return redirect(url_for('assignment1.community_detail', community_id=community_id))
        with db:
            result = db.execute('INSERT INTO posts (user_id, content) VALUES (?, ?)',
                                (user_id, content))
            # Reuse ordinary posts so existing comments, reactions and the
            # needs-reply feature work on community discussions too.
            db.execute('INSERT INTO community_posts (community_id, post_id) VALUES (?, ?)',
                       (community_id, result.lastrowid))
        flash('Your post was shared with the community.', 'success')
        return redirect(url_for('assignment1.community_detail', community_id=community_id))

    app.register_blueprint(bp)
