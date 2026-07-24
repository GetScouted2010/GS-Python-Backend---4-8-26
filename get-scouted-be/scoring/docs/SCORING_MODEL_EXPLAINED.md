# How the Player Scoring Model Works

*A plain-language walkthrough of the four scores that power every page of GetScouted — what they measure, where the numbers come from, and how we made sure they're trustworthy. No data science background required.*

## The big picture

Every player on GetScouted gets four numbers. Together, they answer the four questions a scout, analyst, or director actually asks when they look at a player.

Underneath the AI Dashboard, the Shortlist, the Player Profile, the Club Intelligence page — all of it — sits one scoring engine that produces these four scores. It was originally built by hand as a large, custom Python program. This document explains what that program actually does, translated out of code and into plain language.

| Score | Answers the question… | How it's computed | Range |
|---|---|---|---|
| **RMM** — Player Score | How good is this player, relative to others in the same position? | Rule-based statistics | 0–100 |
| **CS** — Compatibility Score | How well would this player's style fit this specific club? | Rule-based statistics | 0–100 |
| **TFM** — Financial Fit | What would this player realistically cost this club? | Machine learning | € amount |
| **TP** — Transfer Probability | How likely is a transfer to actually happen? | Weighted formula | 0–100% |

---

## RMM — Player Score

*The foundation everything else builds on.*

Player Score measures how good a player is **relative to other players in the same position**. It never compares a goalkeeper's stats to a striker's — that comparison would be meaningless. Instead, each player is measured only against their direct peers: centre-backs against centre-backs, wingers against wingers, across ten position groups in total.

> **Think of it like…** grading on a curve. If you lined up every centre-back in the dataset from worst to best, Player Score tells you where this one falls in that line. A score of 94 means this player performs better than 94% of centre-backs in the real data — not "94 out of 100 points," but "94th place out of 100 peers."

The underlying stats depend on the position — a goalkeeper is judged on shot-stopping, command of the box, and distribution; a striker is judged on finishing, movement, and hold-up play. Each of the ten position groups has its own tailored calculation, built from real match statistics: goals, assists, tackles, interceptions, passing accuracy, duels won, and dozens more, all pulled from actual recorded matches, not estimates.

## CS — Compatibility Score

*Good player ≠ right player for this club.*

A brilliant player isn't automatically the right signing for every club. Compatibility Score asks a different question than Player Score does: not "is this player good," but **"does this player's style of play match how this specific club actually plays?"**

> **Think of it like…** a job candidate and a company's culture. A brilliant candidate can still be the wrong hire if their working style clashes with how the team actually operates. Compatibility Score checks a player's strengths against the specific club's real playing style — their formation tendencies, tempo, and tactical identity — not against some generic "good player" standard.

It's built from two ingredients: how well the player's individual attributes suit the role that club typically needs filled, and the player's underlying Player Score as a performance anchor. That's the first place the two scores connect — more on that below.

## TFM — Financial Fit

*The one score that's a trained prediction, not a fixed formula.*

Financial Fit estimates what a player would realistically cost a given club to sign — a real transfer-fee prediction in euros, tailored to that specific buying club's financial context.

> **Think of it like…** an automated home-price estimate. A model like that doesn't know the "true" value of a house — it looked at thousands of real past sales, learned the pattern between a house's features and what it actually sold for, and applies that pattern to a new house it's never seen. Financial Fit works the same way, trained on real historical transfers instead of home sales.

This is the one score in the system built with machine learning rather than a fixed set of rules — specifically, a model that learned from real transfer history what combination of factors (a player's ability, age, contract situation, league, and more) tends to predict what clubs actually pay. Everything else in this document is deterministic: same inputs always produce the same output, by design, no learning involved. Financial Fit is the exception, and it's treated with extra scrutiny because of that — see "How we know it's right," below.

## TP — Transfer Probability

*Four ingredients, weighted and summed.*

Transfer Probability estimates how likely a transfer actually is to happen — not just whether a move makes sense on paper, but whether the real-world conditions point toward a deal.

> **Think of it like…** a weighted checklist a hiring manager runs through before making an offer. No single factor decides it alone — it's a blend, with some factors counting for more than others.

Four ingredients go into it, each with a fixed weight:

| Ingredient | Weight |
|---|---|
| Compatibility fit | 30% |
| Current performance | 20% |
| Financial fit | 20% |
| Contract situation | 30% |

"Contract situation" carries real weight because a player entering the final year of their deal is under very different pressure to move than one who just signed a long-term extension. Notice that Compatibility and Financial Fit — the two scores above — feed directly into this one. Transfer Probability is the score where everything else comes together.

---

## How the four scores connect

These aren't four independent numbers. Player Score sits at the base, and the other three all lean on it in some way:

```
RMM (Player Score)
  ├──> CS (Compatibility Score) ──┐
  └──> TFM (Financial Fit) ───────┼──> TP (Transfer Probability)
                                  │
       CS's "performance anchor" ─┘
```

Practically, that means: if Player Score were ever wrong for a player, that error wouldn't stay contained — it would quietly ripple into their Compatibility Score, their Financial Fit prediction, and their Transfer Probability too. That's exactly why Player Score was treated as the highest-priority piece to get right and verify, before anything else was built on top of it.

## Where the numbers come from

Every input to every score is real, not simulated: real match statistics for over 41,000 players, real club playing-style data, and real historical transfer records with actual fees paid. Nothing in this system is a guess dressed up as a number — if the underlying data for a calculation genuinely doesn't exist for a player (say, a player with no recorded club), the system reports that honestly as "not available" rather than inventing a plausible-looking score.

## How we know it's right

This scoring engine started life as a single, 15,000+ line program that had never been tested and had duplicate, conflicting versions of some of its own logic. Before any of it went into the live product, it went through four separate, verified stages:

**Stage 1 — Characterize.** Read through the original program, resolved every duplicate/conflicting piece of logic, and produced a trusted snapshot of what it should output for real players — the "answer key" every later stage gets checked against.
*Caught: a missing stat was silently being treated as zero, which wrongly implied a player had no playing time at all.*

**Stage 2 — Rebuild.** Faithfully rebuilt that same logic inside the real backend, reachable as a live service — without changing what it calculates, only how it's delivered.
*Caught: Financial Fit was about to display "13.1" instead of "€1.29 million" — a units bug, fixed before ever shipping.*

**Stage 3 — Prove it matches.** Ran both the original program and the rebuilt version against the same 41,000+ real players and checked, position by position, that the outputs genuinely matched — not just "seems close," but measured against a defined tolerance for every single player.
*Caught: a technical mismatch in how the test itself matched players between systems — would have made every player look wrong even when the scores were actually correct.*

**Stage 4 — Make it fast.** The correct version was initially slow — recalculating from the entire 41,000-player dataset on every single request. This stage made common lookups close to instant without changing a single number the system produces.
*Caught: the speed work was built and tested in isolation but hadn't actually been connected to the live product yet — found before sign-off, then wired in and re-verified.*

The pattern across all four stages is the same: nothing was marked "done" on trust. Every claim was checked against real data, and the things that were wrong were wrong in small, findable ways — exactly the kind of mistakes this process exists to catch before they reach a scout relying on the number.

## Glossary

- **Percentile** — A player's rank compared to their peers, expressed as "better than X% of them" — not a raw point total.
- **Deterministic** — Follows a fixed rule every time. Feed it the same inputs twice, get the exact same answer twice. Most of this system works this way.
- **Machine learning model** — A program that learned patterns from real historical examples (past transfers, in this case) rather than following a hand-written rule. Only Financial Fit uses one.
- **Weighted formula** — Several factors combined into one number, where each factor counts for a different, fixed share of the total — like Transfer Probability's 30/20/20/30 split.
- **Ground truth / oracle** — The trusted, verified answer a new calculation gets checked against — in this case, the original program's real output, saved and used as the standard the rebuilt version had to match.

---

*Internal reference document — describes the scoring engine as implemented in the GetScouted backend. The methodology itself — what factors matter and how they're weighted — was designed by World In Motion Ltd; this document explains the system as built, not the business reasoning behind its design choices.*
