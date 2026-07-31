CREATE TABLE IF NOT EXISTS participant_positions
(
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    trade_date TEXT NOT NULL,

    participant TEXT NOT NULL,

    segment TEXT NOT NULL,

    position_side TEXT NOT NULL,

    value REAL NOT NULL,

    source_file TEXT NOT NULL,

    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS
idx_trade_date
ON participant_positions(trade_date);

CREATE INDEX IF NOT EXISTS
idx_participant
ON participant_positions(participant);

CREATE INDEX IF NOT EXISTS
idx_segment
ON participant_positions(segment);