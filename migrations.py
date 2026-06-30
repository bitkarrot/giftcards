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


async def m003_branded_delivery(db):
    """Add design config columns, email delivery columns, and magic_links table."""
    # Design config columns on cards table
    await db.execute("ALTER TABLE giftcards.cards ADD COLUMN template_asset_id TEXT")
    await db.execute("ALTER TABLE giftcards.cards ADD COLUMN template_name TEXT")
    await db.execute("ALTER TABLE giftcards.cards ADD COLUMN qr_config TEXT")
    await db.execute("ALTER TABLE giftcards.cards ADD COLUMN text_config TEXT")

    # Email delivery columns
    await db.execute("ALTER TABLE giftcards.cards ADD COLUMN recipient_email TEXT")
    await db.execute(
        "ALTER TABLE giftcards.cards ADD COLUMN email_status TEXT DEFAULT 'not_sent'"
    )
    await db.execute("ALTER TABLE giftcards.cards ADD COLUMN email_subject TEXT")
    await db.execute("ALTER TABLE giftcards.cards ADD COLUMN email_body TEXT")
    await db.execute("ALTER TABLE giftcards.cards ADD COLUMN email_template TEXT")

    # Magic links table
    await db.execute(
        f"""
        CREATE TABLE IF NOT EXISTS giftcards.magic_links (
            id            TEXT PRIMARY KEY,
            token_hash    TEXT NOT NULL UNIQUE,
            email         TEXT NOT NULL,
            wallet        TEXT NOT NULL,
            created_at    TIMESTAMP NOT NULL DEFAULT {db.timestamp_now},
            expires_at    TIMESTAMP NOT NULL,
            used_at       TIMESTAMP
        );
        """
    )
    table = f"{db.references_schema}magic_links"
    await db.execute(
        f"CREATE INDEX IF NOT EXISTS idx_giftcards_magic_links_email ON {table}(email);"
    )
    await db.execute(
        f"CREATE INDEX IF NOT EXISTS idx_giftcards_magic_links_token_hash ON {table}(token_hash);"
    )


async def m004_dashboard_indexes(db):
    """Add index on (wallet, status, created_at) for filtered dashboard query performance."""
    table = f"{db.references_schema}cards"
    await db.execute(
        f"""
        CREATE INDEX IF NOT EXISTS idx_giftcards_cards_wallet_status_created
        ON {table}(wallet, status, created_at);
        """
    )