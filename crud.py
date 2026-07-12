import hashlib
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

from lnbits.db import Database

from .models import GiftCard, GiftCardSummary, MagicLink, TemplateImage

db = Database("ext_giftcards")


async def create_card(card: GiftCard) -> GiftCard:
    await db.insert("giftcards.cards", card)
    return card


async def get_card(card_id: str) -> Optional[GiftCard]:
    return await db.fetchone(
        "SELECT * FROM giftcards.cards WHERE id = :id",
        {"id": card_id},
        GiftCard,
    )


async def get_card_by_token_hash(token_hash: str) -> Optional[GiftCard]:
    return await db.fetchone(
        "SELECT * FROM giftcards.cards WHERE token_hash = :hash",
        {"hash": token_hash},
        GiftCard,
    )


async def get_cards_by_wallet(wallet_id: str) -> list[GiftCardSummary]:
    return await db.fetchall(
        "SELECT id, amount, status, recipient_name, sender_name, message, expires_at, created_at, redeemed_at, expired_at, redemption_url, recipient_email, email_status FROM giftcards.cards WHERE wallet = :wallet",
        {"wallet": wallet_id},
        GiftCardSummary,
    )


async def get_cards_by_ids(card_ids: list[str]) -> list[GiftCard]:
    """Return full card records for the given ids (no wallet filter)."""
    if not card_ids:
        return []
    placeholders = ", ".join(f":id_{i}" for i in range(len(card_ids)))
    params = {f"id_{i}": card_id for i, card_id in enumerate(card_ids)}
    return await db.fetchall(
        f"SELECT * FROM giftcards.cards WHERE id IN ({placeholders})",
        params,
        GiftCard,
    )


async def get_cards_by_wallet_filtered(
    wallet_id: str,
    status: Optional[str] = None,
    search: Optional[str] = None,
    date_from: Optional[float] = None,
    date_to: Optional[float] = None,
) -> list[GiftCardSummary]:
    """Return gift cards for a wallet with optional server-side filters.

    Per D-12 (status, search, date range) and RESEARCH.md Pattern 4
    (Server-Side Filtered Query). All filter values use parameterized SQL
    (:status, :search, timestamp_placeholder) — no string interpolation of
    user input (T-03-14). The WHERE wallet = :wallet clause is ALWAYS
    present so cross-wallet leakage is impossible (T-03-15). Search uses
    LOWER(col) LIKE LOWER(:search) for cross-DB case-insensitive matching
    (RESEARCH.md Pitfall 3 — works on both SQLite and PostgreSQL).
    Results are ordered by created_at DESC.
    """
    query = (
        "SELECT id, amount, status, recipient_name, sender_name, message, "
        "expires_at, created_at, redeemed_at, expired_at, redemption_url, "
        "recipient_email, email_status "
        "FROM giftcards.cards WHERE wallet = :wallet"
    )
    values: dict = {"wallet": wallet_id}

    if status is not None:
        query += " AND status = :status"
        values["status"] = status

    if search is not None:
        query += (
            " AND (LOWER(recipient_name) LIKE LOWER(:search) "
            "OR LOWER(sender_name) LIKE LOWER(:search) "
            "OR LOWER(id) LIKE LOWER(:search))"
        )
        values["search"] = f"%{search}%"

    if date_from is not None:
        query += f" AND created_at >= {db.timestamp_placeholder('date_from')}"
        values["date_from"] = date_from

    if date_to is not None:
        query += f" AND created_at <= {db.timestamp_placeholder('date_to')}"
        values["date_to"] = date_to

    query += " ORDER BY created_at DESC"

    return await db.fetchall(query, values, GiftCardSummary)


async def mark_redeeming(token_hash: str) -> Optional[GiftCard]:
    """Atomically mark a card as redeeming. Returns the card if successful, None if already redeemed/not active."""
    result = await db.execute(
        """
        UPDATE giftcards.cards 
        SET status = 'redeeming' 
        WHERE token_hash = :hash AND status = 'active'
        """,
        {"hash": token_hash},
    )
    
    if result.rowcount == 0:
        return None
    
    return await get_card_by_token_hash(token_hash)



async def mark_redeemed(card_id: str) -> None:
    await db.execute(
        f"""
        UPDATE giftcards.cards
        SET status = 'redeemed', redeemed_at = {db.timestamp_placeholder('now')}
        WHERE id = :id
        """,
        {"id": card_id, "now": time.time()},
    )


async def reset_card_to_active(card_id: str) -> None:
    """Reset a card back to active status (used when payment fails)."""
    await db.execute(
        """
        UPDATE giftcards.cards
        SET status = 'active'
        WHERE id = :id
        """,
        {"id": card_id},
    )


async def mark_card_expired(card_id: str) -> bool:
    """Atomically mark a single active card as expired. Returns True if changed."""
    result = await db.execute(
        f"""
        UPDATE giftcards.cards
        SET status = 'expired', expired_at = {db.timestamp_placeholder('now')}
        WHERE id = :id AND status = 'active'
        """,
        {"id": card_id, "now": time.time()},
    )
    return result.rowcount == 1


async def get_expired_active_cards() -> list[GiftCard]:
    """Get all active cards that have passed their expiration date."""
    return await db.fetchall(
        f"""
        SELECT * FROM giftcards.cards
        WHERE status = 'active'
        AND expires_at IS NOT NULL
        AND expires_at < {db.timestamp_placeholder('now')}
        """,
        {"now": time.time()},
        GiftCard,
    )


async def update_card_email_status(card_id: str, status: str) -> None:
    """Update the email_status column on a card."""
    await db.execute(
        """
        UPDATE giftcards.cards
        SET email_status = :status
        WHERE id = :id
        """,
        {"id": card_id, "status": status},
    )


async def update_card_recipient_email(card_id: str, email: str) -> None:
    """Update the recipient_email column on a card."""
    await db.execute(
        """
        UPDATE giftcards.cards
        SET recipient_email = :email
        WHERE id = :id
        """,
        {"id": card_id, "email": email},
    )


async def delete_card(card_id: str) -> None:
    """Hard-delete a card record by id."""
    await db.execute(
        "DELETE FROM giftcards.cards WHERE id = :id",
        {"id": card_id},
    )


async def update_card_fields(card_id: str, fields: dict) -> None:
    """Update editable card metadata and design fields.

    Metadata: recipient_name, sender_name, message, recipient_email
    (per D-15 — amount changes require cancel + recreate).
    Design: template_name, template_asset_id, qr_config, text_config
    (serialized JSON columns from DesignConfig).
    """
    allowed = {
        "recipient_name",
        "sender_name",
        "message",
        "recipient_email",
        "template_name",
        "template_asset_id",
        "qr_config",
        "text_config",
    }
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return
    set_clauses = ", ".join(f"{k} = :{k}" for k in updates)
    params = {"id": card_id, **updates}
    await db.execute(
        f"""
        UPDATE giftcards.cards
        SET {set_clauses}
        WHERE id = :id
        """,
        params,
    )


# ---------------------------------------------------------------------------
# Magic link CRUD (Phase 2 — plan 02-03)
# ---------------------------------------------------------------------------

async def create_magic_link(email: str, wallet: str) -> str:
    """Generate a magic link token, store its SHA-256 hash, and return the raw token.

    The raw token is never stored in the database — only its hash.
    TTL is 30 minutes from creation.
    """
    magic_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(magic_token.encode()).hexdigest()
    link_id = f"ml_{token_hash[:16]}"
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=30)

    link = MagicLink(
        id=link_id,
        token_hash=token_hash,
        email=email,
        wallet=wallet,
        created_at=now,
        expires_at=expires_at,
        used_at=None,
    )
    await db.insert("giftcards.magic_links", link)
    return magic_token


async def get_magic_link_by_hash(token_hash: str) -> Optional[MagicLink]:
    """Fetch a magic link by token_hash where used_at IS NULL and expires_at > now."""
    link = await db.fetchone(
        "SELECT * FROM giftcards.magic_links WHERE token_hash = :hash AND used_at IS NULL",
        {"hash": token_hash},
        MagicLink,
    )
    if link is None:
        return None
    # Timezone-aware expiry check in Python
    now = datetime.now(timezone.utc)
    expires = link.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if now > expires:
        return None
    return link


async def invalidate_magic_links_for_email(email: str) -> None:
    """Delete all magic_links rows for a given email (D-16 — invalidation on redemption)."""
    await db.execute(
        "DELETE FROM giftcards.magic_links WHERE email = :email",
        {"email": email},
    )


async def get_pending_cards_by_email(email: str) -> list[dict]:
    """Get all active, non-expired cards for an email (for magic link landing page).

    Returns raw_token for each card so the frontend can redirect to
    /giftcards/redeem/{raw_token} after magic link verification.
    """
    now = time.time()
    rows = await db.fetchall(
        """
        SELECT id, amount, sender_name, recipient_name, message,
               raw_token, created_at, expires_at
        FROM giftcards.cards
        WHERE recipient_email = :email
          AND status = 'active'
          AND (expires_at IS NULL OR expires_at > :now)
        ORDER BY created_at DESC
        """,
        {"email": email, "now": now},
    )
    return [dict(row) for row in rows]


async def count_recent_magic_links(email: str) -> int:
    """Count magic_links rows for an email created in the last hour (rate limit check)."""
    cutoff = time.time() - 3600
    row = await db.fetchone(
        f"SELECT COUNT(*) as count FROM giftcards.magic_links WHERE email = :email AND created_at > {db.timestamp_placeholder('cutoff')}",
        {"email": email, "cutoff": cutoff},
    )
    if row is None:
        return 0
    return int(row["count"])


async def mark_magic_link_used(token_hash: str) -> None:
    """Mark a magic link as used by setting used_at to now."""
    await db.execute(
        f"""
        UPDATE giftcards.magic_links
        SET used_at = {db.timestamp_placeholder('now')}
        WHERE token_hash = :hash
        """,
        {"hash": token_hash, "now": time.time()},
    )


async def mark_magic_link_used_if_unused(token_hash: str) -> bool:
    """Atomically mark a magic link as used only if it is currently unused.

    H-2: prevents the single-use TOCTOU race where two concurrent requests
    both pass the `used_at IS NULL` check before either marks it used.
    Returns True if this call claimed the link (rowcount == 1), False if it
    was already used (or does not exist).
    """
    result = await db.execute(
        f"""
        UPDATE giftcards.magic_links
        SET used_at = {db.timestamp_placeholder('now')}
        WHERE token_hash = :hash AND used_at IS NULL
        """,
        {"hash": token_hash, "now": time.time()},
    )
    return result.rowcount == 1


# ---------------------------------------------------------------------------
# Template images (m005 — bypass global asset per-user cap)
# ---------------------------------------------------------------------------

async def create_template_image(template: TemplateImage) -> TemplateImage:
    await db.insert("giftcards.template_images", template)
    return template


async def get_template_image(template_id: str) -> Optional[TemplateImage]:
    return await db.fetchone(
        "SELECT * FROM giftcards.template_images WHERE id = :id",
        {"id": template_id},
        TemplateImage,
    )


async def delete_template_image(template_id: str) -> None:
    await db.execute(
        "DELETE FROM giftcards.template_images WHERE id = :id",
        {"id": template_id},
    )