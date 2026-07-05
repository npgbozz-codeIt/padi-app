# src/services/data_ux_handler.py
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from src.models.data_plan import DataPlan
from src.utils.responses import DATA_RESPONSES

logger = logging.getLogger(__name__)


async def process_data_ux_routing(
    db: AsyncSession,
    user_lang: str,
    phone_number: str,
    extracted_network: str | None,
    extracted_size: str | None,
    extracted_amount: float | None = None,
) -> dict:
    """
    Analyzes NLU slots against the local database cache to determine
    the optimal UX scenario:
    - SCENARIO A: Direct Confirmation if size matches perfectly.
    - SCENARIO C: Smart Proximity Recommendations if size is down or amount doesn't match.
    - SCENARIO B: Category Filter Grid if only network name is provided.
    """
    lang = user_lang if user_lang in DATA_RESPONSES else "english"
    text_catalog = DATA_RESPONSES[lang]

    # Quick validation safety block
    if not extracted_network:
        return {"text": text_catalog["no_plans_found"], "reply_markup": None}

    clean_net = extracted_network.strip().lower()
    net_display = clean_net.upper() if clean_net != "9mobile" else "9mobile"

    # =========================================================================
    # SCENARIO A & C: Direct Intent Matching & Price-Anchor Fallbacks
    # =========================================================================
    if extracted_size or extracted_amount:
        matched_plans = []

        # 1. Attempt Scenario A: Try for an exact look up first if size is known
        if extracted_size:
            clean_size = extracted_size.strip().upper()
            stmt = (
                select(DataPlan)
                .where(DataPlan.network_name.ilike(clean_net))
                .where(DataPlan.size.ilike(f"%{clean_size}%"))
                .where(DataPlan.plan_disabled == False)
                .order_by(DataPlan.retail_amount.asc())
            )
            result = await db.execute(stmt)
            matched_plans = result.scalars().all()

        # If Scenario A finds an active match, serve it instantly
        if matched_plans:
            chosen_plan = matched_plans[0]
            message_text = text_catalog["confirm_direct"].format(
                network=chosen_plan.network_name,
                size=chosen_plan.size,
                validity=chosen_plan.validity,
                price=int(chosen_plan.retail_amount),
                phone=phone_number,
            )
            reply_markup = {
                "inline_keyboard": [
                    [
                        {
                            "text": f"✅ Pay ₦{int(chosen_plan.retail_amount)} Now",
                            "callback_data": f"data_pay:{chosen_plan.vendor_plan_id}:{phone_number}",
                        }
                    ],
                    [{"text": "❌ Cancel", "callback_data": "action_cancel"}],
                ]
            }
            return {"text": message_text, "reply_markup": reply_markup}

        # =========================================================================
        # SCENARIO C: Smart Alternatives (Exact match failed or user typed guessed price)
        # =========================================================================
        target_amount = extracted_amount if extracted_amount else 500.0

        fallback_stmt = (
            select(DataPlan)
            .where(DataPlan.network_name.ilike(clean_net))
            .where(DataPlan.plan_disabled == False)
            .order_by(DataPlan.retail_amount.asc())
        )
        fb_result = await db.execute(fallback_stmt)
        all_active_plans = fb_result.scalars().all()

        if all_active_plans:
            # Sort plans by mathematical proximity to the requested amount target
            all_active_plans.sort(
                key=lambda p: abs(float(p.retail_amount) - target_amount)
            )
            recommendations = all_active_plans[:3]  # Extract top 3 closest options

            message_text = text_catalog["price_anchor_fallback"].format(
                network=net_display
            )

            inline_keyboard = []
            for plan in recommendations:
                inline_keyboard.append(
                    [
                        {
                            "text": f"{plan.size} ({plan.validity}) - ₦{int(plan.retail_amount)}",
                            "callback_data": f"data_pay:{plan.vendor_plan_id}:{phone_number}",
                        }
                    ]
                )
            inline_keyboard.append(
                [
                    {
                        "text": "📂 View Main Menu",
                        "callback_data": f"data_back_to_net:{clean_net}",
                    }
                ]
            )

            return {
                "text": message_text,
                "reply_markup": {"inline_keyboard": inline_keyboard},
            }

    # =========================================================================
    # SCENARIO B: Category Lifespan Filter Grid Generation (Network Only)
    # =========================================================================
    message_text = text_catalog["select_validity"].format(network=net_display)

    reply_markup = {
        "inline_keyboard": [
            [
                {
                    "text": "☀️ Daily Plans",
                    "callback_data": f"data_net_view:{clean_net}:daily",
                },
                {
                    "text": "⏳ Weekly Plans",
                    "callback_data": f"data_net_view:{clean_net}:weekly",
                },
            ],
            [
                {
                    "text": "📅 Monthly Plans",
                    "callback_data": f"data_net_view:{clean_net}:monthly",
                },
                {
                    "text": "💼 Corporate Plans",
                    "callback_data": f"data_net_view:{clean_net}:corporate",
                },
            ],
            [{"text": "❌ Cancel Operations", "callback_data": "action_cancel"}],
        ]
    }

    return {"text": message_text, "reply_markup": reply_markup}


async def generate_plan_selection_buttons(
    db: AsyncSession, user_lang: str, network: str, validity_category: str
) -> dict:
    """
    Fetches localized active bundles according to timeframe constraints
    and constructs a scannable grid keyboard matrix.
    """
    lang = user_lang if user_lang in DATA_RESPONSES else "english"
    text_catalog = DATA_RESPONSES[lang]

    query_pattern = f"%{validity_category}%"

    stmt = (
        select(DataPlan)
        .where(DataPlan.network_name.ilike(network))
        .where(
            or_(
                DataPlan.validity.ilike(query_pattern),
                DataPlan.plan_type.ilike(query_pattern),
            )
        )
        .where(DataPlan.plan_disabled == False)
        .order_by(DataPlan.retail_amount.asc())
        .limit(6)
    )

    result = await db.execute(stmt)
    plans = result.scalars().all()

    if not plans:
        return {"text": text_catalog["no_plans_found"], "reply_markup": None}

    inline_keyboard = []

    # Bundle items two by two for optimized layout layout grids
    for i in range(0, len(plans), 2):
        row = []
        p1 = plans[i]
        row.append(
            {
                "text": f"{p1.size} - ₦{int(p1.retail_amount)}",
                "callback_data": f"data_pay:{p1.vendor_plan_id}:PROMPT_PHONE",  # Flow placeholder handles setup via callback router context later
            }
        )

        if i + 1 < len(plans):
            p2 = plans[i + 1]
            row.append(
                {
                    "text": f"{p2.size} - ₦{int(p2.retail_amount)}",
                    "callback_data": f"data_pay:{p2.vendor_plan_id}:PROMPT_PHONE",
                }
            )
        inline_keyboard.append(row)

    inline_keyboard.append(
        [
            {
                "text": "⬅️ Back to Categories",
                "callback_data": f"data_back_to_net:{network}",
            }
        ]
    )

    return {
        "text": text_catalog["list_plans"].format(
            network=network.upper(), validity=validity_category.capitalize()
        ),
        "reply_markup": {"inline_keyboard": inline_keyboard},
    }
