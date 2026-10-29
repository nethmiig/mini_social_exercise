# Mini Social: Coding Assignment 1 implementation

This update contains all three selected features, including the Needs a reply
feature from the earlier package. It is an update to your existing project,
not a standalone copy of the repository.

## Install

1. Stop the running app with Ctrl+C in its VS Code terminal.
2. Back up your project folder, including database.sqlite, before installing.
3. Extract this ZIP to a separate folder.
4. Copy its app.py, assignment1_features.py and requirements.txt into the main
   mini_social_exercise folder. Replace matching files.
5. Copy the four files inside its templates folder into your project's
   existing templates folder. Replace matching files and add the new files.
6. Keep your existing database.sqlite and the rest of your project files.
7. In the terminal inside your project folder, run these commands one at a time:

   .\.venv\Scripts\python.exe -m pip install -r requirements.txt

   .\.venv\Scripts\python.exe app.py

8. Open http://127.0.0.1:8080 and log in.

The extra tzdata dependency supplies Helsinki time-zone rules on Windows.
The app adds four new tables automatically when the first request arrives.
It preserves your existing accounts, posts and comments, including test replies
you already made. There is no replacement database inside this package.

## Files in the update

- app.py: integrates the three features with the existing application.
- assignment1_features.py: goal calculations, community tables and routes.
- requirements.txt: includes the time-zone data dependency.
- templates/feed.html.j2: reply opportunities, weekly progress and memberships.
- templates/base.html.j2: adds the Communities navigation link.
- templates/communities.html.j2: browse, create, join and leave communities.
- templates/community_detail.html.j2: shared purpose, membership and discussions.

## Feature 1: Needs a reply

Chapter 2, Design Claim 1: make needed contributions visible.

The homepage previews three posts with no comments, and the Needs a reply tab
shows all matching posts with pagination. It excludes your posts when logged
in and supports the Following filter. Write the first reply opens a real form.
Once a comment exists, the post leaves this section on the next page load.
The post and its saved comment remain in the platform's ordinary feed.

Contribution here means a first comment, not a reaction. Deleting the only
comment makes that post eligible again.

## Feature 2: Weekly goal with progress feedback

Chapter 2, Design Claim 15: give frequent feedback about progress toward goals.

The homepage suggests joining three conversations this week. Choose your own
target lets each user save a target between 1 and 50 different posts.

The progress count is calculated from actual comments. It counts distinct
posts by other users that you commented on during the current Helsinki week.
Multiple comments on one post count once, and comments on your own posts do
not count. Deleting your only comment on a post reduces the progress count.

The progress bar updates when the homepage loads. A button helps users find
conversations to join. Reaching the target displays a completion message.
Changing your target preserves your existing contribution count.

Weeks start on Monday at 00:00 in Helsinki. At the start of a new week, the
current count uses that week's comments and the suggested target returns to
three. Previously saved goals remain in the database.

SQLite timestamps are UTC. get_week_bounds() converts both local week
boundaries to UTC so the calculation also works across daylight saving changes.

## Feature 3: Communities with membership and shared identity

Chapter 3, Design Claim 1: encourage identity-based attachment that can persist
through changes in membership.

Use Communities in the navigation to browse public groups. Users can explicitly
join Oulu Student Hub or create a new group with a name and shared purpose.
Creating a community also joins its creator. No user is assigned to a group
just because their posts contain particular keywords or hashtags.

Members receive a Member badge, see their communities on the homepage, and
can publish posts to the community feed. Other users can browse the public
discussion, but must join before publishing a community post.

Community posts are ordinary posts associated with a community. They therefore
support existing comments and reactions, appear in the platform's main feed,
and can appear under Needs a reply. Comments on other members' posts also
contribute to the commenter's weekly goal.

Leaving removes membership and posting access. It preserves the community's
name, purpose and discussions, so remaining members can continue taking part.
The design aims to encourage commitment; an actual increase in retention has
not been measured by this implementation.

## Check each feature on your computer

1. Needs a reply: use account B to comment on an unanswered post by account A.
   Confirm the post leaves the section and its comment remains saved.
2. Weekly goal: save a target of two. Comment on two different posts by others
   this week, then return home. Check that progress reaches the target. Add
   another comment to one of those posts and check that the count stays the same.
3. Communities: use account A to create a community and publish a post. Log in
   as B, join it, and publish a second post. Leave as A. Return as B and check
   that the community and discussions still exist.

After checking the app, commit and push the changed source files to your fork.
Record the three working features within the assignment's two-minute limit.
Use your own words to explain what you learned and disclose the AI assistance.
This technical guide is not a coursework report or a personal reflection.

## Validation completed

Automated checks used temporary copies of the supplied database. They covered
the first-reply workflow, filtering, pagination, saved goal targets, duplicate
comment counting, account separation, new-week boundaries, the Helsinki clock
change, community creation, duplicate names, membership requirements, leaving,
preserving discussions, input validation and escaping user text.

The first feature has also been shown working in your browser screenshots.
The two new features still need a visual check with your original static assets
on your computer. The moderation and recommendation assignment functions are
still the original placeholders; this package implements Coding Assignment 1.
