# Mafia horror UI

Uses the installed Anthropic frontend-design skill in `.agents/skills/frontend-design/`.

## Design plan

- Palette: soot `#140d0e`, dried blood `#651d28`, fresh blood `#bd3d48`, bone `#f0dfc4`, brass `#c3a170`, clinic green `#91c7b4`. Existing turn colors remain meaningful.
- Type: locally hosted Pirata One for gothic titles and wax seals; system sans for instructions, names and scores. Keep player names readable.
- Layout: a mobile story table with the town record above the current turn, then secret identity, players and chat. All controls stay at least 48px tall.
- Motion: one turn-change announcement, a role-card reveal, a selection stamp, and a blood-drip death reveal. Polls and chat updates never replay the turn announcement. Rescue uses a gentler reveal.

```
[ Mafia                       music / menu ]
[ Town record / last event                  ]
[ Wax seal / turn / time                    ]
[ Secret identity                          ]
[ Player + score       Player + score      ]
[ Action                                  ]
[ Town chat / private Mafia chat            ]
```

## Review before implementation

A black-and-red card grid alone would not distinguish this game. Use the supplied village illustrations as the setting, reduce the repeated pill/uppercase treatment, shape the turn panel like a case-file folio, and reserve blood drips for death announcements. Avoid continuous motion across every card: the memorable moments should correspond to game events and player actions.

## Implementation constraints

Use native CSS and Web Animations; no animation framework is needed for this plain-JavaScript app. Animate transform and opacity with finite durations. Respect reduced motion, avoid strobing, retain keyboard focus and dialog behavior, and preserve dead-player background priority. Fonts load locally with a fallback. Artwork and audio remain the user-supplied and licensed existing assets.
