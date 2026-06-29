async def m001_initial(db):
    await db.execute(
        """
        CREATE TABLE giftcards.cards (
            id            TEXT PRIMARY KEY,
            wallet        TEXT NOT NULL,
            card_wallet_id TEXT,
            amount        INTEGER NOT NULL,
            token_hash    TEXT NOT NULL UNIQUE,
            status        TEXT NOT NULL DEFAULT 'active',
            recipient_name TEXT,
            sender_name   TEXT,
            message       TEXT,
            expires_at    TIMESTAMP,
            created_at    TIMESTAMP NOT NULL DEFAULT """
        + db.timestamp_now
        + """,
            redeemed_at   TIMESTAMP,
            expired_at    TIMESTAMP
        );
        """
    )
    # SQLite cannot create indexes with a schema prefix on an attached database,
    # so use the db-specific table reference.
    table = f"{db.references_schema}cards"
    await db.execute(
        f"""
        CREATE INDEX IF NOT EXISTS idx_giftcards_cards_wallet ON {table}(wallet);
        """
    )
    await db.execute(
        f"""
        CREATE INDEX IF NOT EXISTS idx_giftcards_cards_status_expires ON {table}(status, expires_at);
        """
    )