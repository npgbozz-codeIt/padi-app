# src/utils/ledger_guard.py
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.profile import Profile
from src.models.transaction import Transaction, TransactionType, TransactionStatus


async def initialize_local_ledger(
    db: AsyncSession,
    profile: Profile,
    amount: int,
    recipient: str,
    tx_type: TransactionType,
    provider: str,
) -> tuple[bool, Transaction | None]:
    """
    Unified ledger safety rail. Checks balances and stages a pending database entry atomicity.
    Returns (True, transaction_instance) if wallet balance checks clear successfully.
    """
    current_balance = float(profile.user_wallet or 0.0)

    # 1. Enforce safety barrier check
    if current_balance < amount:
        return False, None

    # 2. Subtract local currency values atomically before firing external endpoints
    profile.user_wallet = current_balance - amount

    # 3. Create the centralized financial tracking entity
    pending_tx = Transaction(
        profile_id=profile.id,
        tx_type=tx_type,
        amount=amount,
        recipient=recipient,
        provider=provider,
        status=TransactionStatus.PENDING,
    )

    db.add(pending_tx)
    await db.flush()  # Populates pending_tx.id asynchronously without committing yet

    return True, pending_tx
