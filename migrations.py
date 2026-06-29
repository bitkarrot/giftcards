async def m001_initial(db):
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS giftcards.cards (
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


async def m002_add_raw_token(db):
    """Store raw_token and redemption_url so links can be retrieved later by the issuer."""
    await db.execute(
        "ALTER TABLE giftcards.cards ADD COLUMN raw_token TEXT"
    )
    await db.execute(
        "ALTER TABLE giftcards.cards ADD COLUMN redemption_url TEXT"
    )