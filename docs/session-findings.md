# Session lifecycle investigation

The app is a single-worker Flask service with room state held in the `rooms`
dictionary. A browser reconnects by resubmitting its saved room code and player
ID; there is no expiring login cookie involved in a case ending.

## Reproduced behavior before changes

A Flask test-client reproduction created a solo lead, joined a friend through
the invitation, started the case, and called `/api/end`. The friend's
`/api/state` returned **200**, with phase `over`. Replaying through
`/api/restart` also returned **200** for the same friend's identity.

The actual removal occurred when the lead chose **Choose another story**. Its
old handler called `/api/leave`, and the solo lead's leave route deleted the
entire room. The friend's next state request returned **404**, “Room not found.
It may have expired.” The lead's local saved identity was also cleared.

Natural town and Mafia victories likewise change the phase to `over` and settle
scores; they do not delete rooms or team members. An eliminated Detective can
still reconnect, view the ending, and choose a new case as lead.

## Fix and contracts

`POST /api/solo-next`, called with the lead's existing `code` and `pid` plus
`scenario_id` (a catalog ID or `random`), replaces the case inside the existing
room. It is available in the briefing or after a case ends. Active cases must
first finish or be ended through the existing host control.

The room code, lead ID, friends' IDs, invitation token, private team conversation,
and lead's accumulated score survive. Authored NPCs and all case progress are
replaced. The team returns to the new briefing, and the lead starts it using the
usual control. Random selection excludes the current story. Invalid selections
leave the current case intact. Friends and NPCs cannot select a new case.

Incoming cast names are checked against every team alias. Conflicts are renamed
through the complete authored case so testimony and character labels remain
consistent; the shared catalog remains unchanged.

`POST /api/tutorial` creates a separate fixed practice case using the same solo
engine and action routes. State includes `tutorial: true`; its first night has
no victim and its ending awards no points. Selecting a normal story through
`solo-next` clears the practice flag. Human private team messages include the
actual submitting player ID as `speaker` so notification ownership is reliable.

Explicitly leaving a solo room as lead still closes it. A friend's explicit
leave removes only that friend. Online room behavior is preserved.

## Lifetime and reconnection limits

Every valid lead or friend request refreshes the room's last-activity time. A
room is eligible for cleanup after six hours without requests; cleanup runs
when another room is created. Case completion does not trigger this cleanup.
Because storage is in memory, a service restart still removes all rooms. These
existing deployment limits are distinct from the verified story-selection bug.

## Verification

`tests/test_session_lifecycle.py` covers natural wins, host-ended games,
replay/briefing reset, reconnecting from a fresh client, next-case preservation,
alias conflicts, access checks, invalid/active selections, explicit leave,
idle expiry, online session preservation, and tutorial behavior.

Existing solo and team tests passed after the lifecycle refactor: 44 tests via
`/workspace/.venvs/a-mafia-game/bin/python -m unittest tests.test_solo tests.test_solo_team -q`.
The eleven focused lifecycle tests cover a complete one-round practice win through
investigation, a question, inspection, comparison, influence, and the final
ballot. The supported path changes five witnesses' preferences and ends with a
town victory while every score stays zero. Final integrated check counts are
recorded in the implementation report.
Practice guidance is also checked against aliases matching Mara or Ellis; its
runtime target IDs survive renaming and never appear in a normal mystery.

## Skills and tooling assessment

Read `cloud-environment:cloud-environment-runtime` from the supported cloud
registry (`c0/cloud-environment-runtime`) and inspected
`cloud_environment_environment_status` before work. Queried `skills.list` for
the supported cloud registry; the other available skill is environment
onboarding and is unnecessary for this focused Flask lifecycle change. The
existing virtual environment, standard-library `unittest`, Flask test client,
and `rg` provide the required investigation and validation tools. No additional
skills, packages, external network calls, or installation commands were needed.
