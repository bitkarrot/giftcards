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
    await db.execute(
        """
        CREATE INDEX idx_giftcards_cards_wallet ON giftcards.cards(wallet);
        """
    )
    await db.execute(
        """
        CREATE INDEX idx_giftcards_cards_status_expires ON giftcards.cards(status, expires_at);
        """
    )