# src/utils/ledger_guard.py
from decimal import Decimal
from typing import Optional, Union
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.profile import Profile
from src.models.transaction import Transaction, TransactionType, TransactionStatus


async def initialize_local_ledger(
    db: AsyncSession,
    profile: Profile,
    amount: Union[Decimal, int, float, str],
    recipient: str,
    tx_type: TransactionType,
    provider: str,
) -> tuple[bool, Optional[Transaction]]:
    """
    Unified ledger safety rail. Checks balances and stages a pending database entry atomically.
    Returns (True, transaction_instance) if wallet balance checks clear successfully.
    """
    # 1. Enforce Decimal precision across all balance arithmetic
    current_balance = (
        profile.user_wallet
        if profile.user_wallet is not None
        else Decimal("0.00")
    )
    if not isinstance(current_balance, Decimal):
        current_balance = Decimal(str(current_balance))

    dec_amount = Decimal(str(amount))

    # 2. Enforce safety barrier check
    if current_balance < dec_amount:
        return False, None

    # 3. Deduct wallet balance atomically before firing external endpoints
    profile.user_wallet = current_balance - dec_amount

    # 4. Create the centralized financial tracking entity
    pending_tx = Transaction(
        profile_id=profile.id,
        tx_type=tx_type,
        amount=dec_amount,
        recipient=recipient,
        provider=provider.upper() if provider else None,
        status=TransactionStatus.PENDING,
        balance_after=profile.user_wallet,
    )

    db.add(pending_tx)
    await db.flush()  # Populates pending_tx.id asynchronously without committing yet

    return True, pending_tx