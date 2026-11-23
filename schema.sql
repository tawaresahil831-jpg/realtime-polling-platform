PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS polls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS options (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    poll_id INTEGER NOT NULL,
    text TEXT NOT NULL,
    position INTEGER NOT NULL,
    FOREIGN KEY (poll_id) REFERENCES polls (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS votes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    poll_id INTEGER NOT NULL,
    option_id INTEGER NOT NULL,
    voter_token TEXT NOT NULL,
    ip_hash TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (poll_id) REFERENCES polls (id) ON DELETE CASCADE,
    FOREIGN KEY (option_id) REFERENCES options (id) ON DELETE CASCADE,
    UNIQUE (poll_id, voter_token),
    UNIQUE (poll_id, ip_hash)
);

CREATE INDEX IF NOT EXISTS idx_options_poll_id ON options (poll_id);
CREATE INDEX IF NOT EXISTS idx_votes_poll_id ON votes (poll_id);
CREATE INDEX IF NOT EXISTS idx_votes_option_id ON votes (option_id);
