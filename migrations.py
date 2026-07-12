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
    """Add design config columns, email delivery columns, and magic_links table.

    Idempotent: catches "duplicate column name" errors so re-running this
    migration (e.g. after a failed version update) does not fail.
    """
    # Design config columns on cards table — try each, skip if already exists
    for col, col_def in [
        ("template_asset_id", "TEXT"),
        ("template_name", "TEXT"),
        ("qr_config", "TEXT"),
        ("text_config", "TEXT"),
        ("recipient_email", "TEXT"),
        ("email_status", "TEXT DEFAULT 'not_sent'"),
        ("email_subject", "TEXT"),
        ("email_body", "TEXT"),
        ("email_template", "TEXT"),
    ]:
        try:
            await db.execute(
                f"ALTER TABLE giftcards.cards ADD COLUMN {col} {col_def}"
            )
        except Exception:
            pass  # Column already exists

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


async def m005_template_images(db):
    """Store custom template images in the giftcards DB.

    Bypasses the global LNbits asset system (which enforces a per-user cap
    of lnbits_max_assets_per_user, default 1) so non-admin users can upload
    and replace template images freely.
    """
    await db.execute(
        f"""
        CREATE TABLE IF NOT EXISTS giftcards.template_images (
            id            TEXT PRIMARY KEY,
            wallet        TEXT NOT NULL,
            user_id       TEXT NOT NULL,
            mime_type     TEXT NOT NULL,
            filename      TEXT,
            size_bytes    INTEGER NOT NULL,
            data          BLOB NOT NULL,
            created_at    TIMESTAMP NOT NULL DEFAULT {db.timestamp_now}
        );
        """
    )