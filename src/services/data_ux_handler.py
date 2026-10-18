# src/services/data_ux_handler.py
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from src.models.data_plan import DataPlan
from src.utils.responses import DATA_RESPONSES

logger = logging.getLogger(__name__)


def format_data_size(size_str: str) -> str:
    """Normalizes raw size values into readable units (e.g., '1' -> '1GB', '45' -> '45MB')."""
    if not size_str:
        return "Data Bundle"
    s = str(size_str).strip().upper()
    
    if any(unit in s for unit in ["MB", "GB", "KB", "TB"]):
        return s
        
    try:
        val = float(s)
        if val in [1.0, 1]:
            return "1GB"
        elif val < 20:
            return f"{val}GB".replace(".0", "")
        elif val >= 1024:
            val_gb = val / 1024
            return f"{val_gb:.1f}GB".replace(".0", "")
        else:
            return f"{int(val)}MB"
    except ValueError:
        return s


async def process_data_ux_routing(
    db: AsyncSession,
    user_lang: str,
    phone_number: str,
    extracted_network: str | None,
    extracted_size: str | None,
    extracted_amount: float | None = None,
) -> dict:
    lang = user_lang if user_lang in DATA_RESPONSES else "english"
    text_catalog = DATA_RESPONSES[lang]

    if not extracted_network:
        return {"text": text_catalog["no_plans_found"], "reply_markup": None}

    clean_net = extracted_network.strip().lower()
    net_display = clean_net.upper() if clean_net != "9mobile" else "9mobile"

    if extracted_size or extracted_amount:
        matched_plans = []

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

        if matched_plans:
            chosen_plan = matched_plans[0]
            formatted_size = format_data_size(chosen_plan.size)
            message_text = text_catalog["confirm_direct"].format(
                network=chosen_plan.network_name,
                size=formatted_size,
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
            all_active_plans.sort(
                key=lambda p: abs(float(p.retail_amount) - target_amount)
            )
            recommendations = all_active_plans[:3]

            message_text = text_catalog["price_anchor_fallback"].format(
                network=net_display
            )

            inline_keyboard = []
            for plan in recommendations:
                p_size = format_data_size(plan.size)
                inline_keyboard.append(
                    [
                        {
                            "text": f"{p_size} ({plan.validity}) - ₦{int(plan.retail_amount)}",
                            "callback_data": f"data_pay:{plan.vendor_plan_id}:{phone_number}",
                        }
                    ]
                )
            inline_keyboard.append(
                [
                    {
                        "text": "📂 View Main Menu",
                        "callback_data": f"data_back_to_net:{clean_net}:{phone_number}",
                    }
                ]
            )

            return {
                "text": message_text,
                "reply_markup": {"inline_keyboard": inline_keyboard},
            }

    # SCENARIO B: Carry phone_number in category callback data (e.g. data_net_view:glo:daily:07059188019)
    message_text = text_catalog["select_validity"].format(network=net_display)

    reply_markup = {
        "inline_keyboard": [
            [
                {
                    "text": "☀️ Daily Plans",
                    "callback_data": f"data_net_view:{clean_net}:daily:{phone_number}",
                },
                {
                    "text": "⏳ Weekly Plans",
                    "callback_data": f"data_net_view:{clean_net}:weekly:{phone_number}",
                },
            ],
            [
                {
                    "text": "📅 Monthly Plans",
                    "callback_data": f"data_net_view:{clean_net}:monthly:{phone_number}",
                },
                {
                    "text": "💼 Corporate Plans",
                    "callback_data": f"data_net_view:{clean_net}:corporate:{phone_number}",
                },
            ],
            [{"text": "❌ Cancel Operations", "callback_data": "action_cancel"}],
        ]
    }

    return {"text": message_text, "reply_markup": reply_markup}


async def generate_plan_selection_buttons(
    db: AsyncSession, user_lang: str, network: str, validity_category: str, phone_number: str = "PROMPT_PHONE"
) -> dict:
    lang = user_lang if user_lang in DATA_RESPONSES else "english"
    text_catalog = DATA_RESPONSES[lang]

    category_map = {
        "daily": ["day", "24hr", "hourly"],
        "weekly": ["week", "7days", "7 days"],
        "monthly": ["month", "30days", "30 days", "days", "day"],
        "corporate": ["corporate", "corp", "sme", "gifting"]
    }

    search_terms = category_map.get(validity_category.lower(), [validity_category])

    conditions = []
    for term in search_terms:
        pattern = f"%{term}%"
        conditions.append(DataPlan.validity.ilike(pattern))
        conditions.append(DataPlan.plan_type.ilike(pattern))

    stmt = (
        select(DataPlan)
        .where(DataPlan.network_name.ilike(network))
        .where(or_(*conditions))
        .where(DataPlan.plan_disabled == False)
        .order_by(DataPlan.retail_amount.asc())
        .limit(8)
    )

    result = await db.execute(stmt)
    plans = result.scalars().all()

    if not plans:
        return {
            "text": f"⚠️ No active {validity_category.upper()} plans found for {network.upper()} right now.",
            "reply_markup": {
                "inline_keyboard": [
                    [
                        {
                            "text": "⬅️ Back to Categories",
                            "callback_data": f"data_back_to_net:{network}:{phone_number}",
                        }
                    ]
                ]
            },
        }

    inline_keyboard = []

    for i in range(0, len(plans), 2):
        row = []
        p1 = plans[i]
        p1_size = format_data_size(p1.size)
        row.append(
            {
                "text": f"{p1_size} - ₦{int(p1.retail_amount)}",
                "callback_data": f"data_pay:{p1.vendor_plan_id}:{phone_number}",
            }
        )

        if i + 1 < len(plans):
            p2 = plans[i + 1]
            p2_size = format_data_size(p2.size)
            row.append(
                {
                    "text": f"{p2_size} - ₦{int(p2.retail_amount)}",
                    "callback_data": f"data_pay:{p2.vendor_plan_id}:{phone_number}",
                }
            )
        inline_keyboard.append(row)

    inline_keyboard.append(
        [
            {
                "text": "⬅️ Back to Categories",
                "callback_data": f"data_back_to_net:{network}:{phone_number}",
            }
        ]
    )

    return {
        "text": text_catalog["list_plans"].format(
            network=network.upper(), validity=validity_category.capitalize()
        ),
        "reply_markup": {"inline_keyboard": inline_keyboard},
    }