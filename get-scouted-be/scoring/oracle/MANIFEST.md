# Scoring Oracle Snapshot -- MANIFEST

snapshot_version: v1

- Generated: 2026-07-22T13:33:05.213179+00:00
- Git commit: 8296bd8c547b11e474ad6108f44e5cbb38191c81
- Row count: 41708 (of 41708 reconstructed players)
- Output file: `scoring/oracle/scoring_oracle_v1_2026-07-22.csv`
- sklearn version: 1.9.0
- TFM artifact used: `scoring/ml_artifacts/tfm_value_model_v1.joblib`

## Per-score population & context

- **RMM (`rmm`)**: context-free per player (`impact.compute_rmm_column`) --
  position-relative percentile of the player's own stats, no club
  comparison involved. Non-null for 41707/41708 players.
  Never zero-filled -- a player excluded from a position group's percentile
  computation is left NaN.
- **Compatibility Score (`cs`)**: per player vs. their OWN CURRENT club
  (`Player.club` FK, `deterministic_scores.compute_cs_tp_for_pairs` with
  `club_context=None`). Non-null for 15051/41708 players.
  NaN (not 0) when the player has no club, the club's playing-style vector
  is entirely unknown, or the player's position has no role-score coverage
  -- exclusion counts from this run: `{'no_club': 0, 'unresolved_role_fit': 26657, 'nan_player_impact': 1}`.
- **TFM (`tfm`)**: `predicted_fee` from the trained RandomForestRegressor
  Pipeline (Financial Fit, NOT Transfer Probability -- see
  `docs/CURATION_MAP.md`'s resolved mapping), evaluated per player with
  their CURRENT club as buying-club context
  (`tfm_model.build_oracle_player_features`). Non-null for
  41708/41708 players -- NaN for players with no
  resolvable current club (no real transfer-value context to price
  against), never a value fabricated from an all-imputed feature row.
- **Transfer Probability (`transfer_probability`)**: the fully
  deterministic weighted formula (0.30*Compatibility + 0.20*Performance +
  0.20*Financial + 0.30*contract_fit), evaluated per player vs. their own
  current club in the same `compute_cs_tp_for_pairs` call as Compatibility
  Score. Non-null for 15051/41708 players -- propagates
  to NaN whenever any of its inputs (including RMM via Performance Score)
  is NaN.
