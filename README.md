# Mafia

Multiplayer Mafia for phones, tablets and PCs. The server is the Moderator.

Run locally:  pip install -r requirements.txt  &&  python app.py
Deploy: push this folder to GitHub, then Railway > New Project > Deploy from GitHub repo.

Optional Railway variables: NIGHT_STEP_SECONDS (default 30), DISCUSS_SECONDS (default 120).

Lobby settings let the host choose an automatic or explicit Mafia count (fewer
than half the players), and enable Doctor/Detective roles or play with only
Mafia and Villagers. Special roles are added as player numbers allow.

The host cannot skip the Mafia turn. It ends when every living Mafia member
votes or the timer expires. Mafia can vote using the private chat's target
buttons, `/vote name`, or the player cards. Unanimous votes choose that target;
split votes choose uniformly among distinct nominated targets. On timeout,
only submitted votes count; no votes means no kill. When enabled, the Doctor
can still protect the chosen target before the night is resolved.

Mafia chat is private and separate from Town chat. Living Mafia can use it
during day and night, while Town chat retains its daytime discussion rules.

Run regression tests: `python -m unittest discover -s tests -v`.
