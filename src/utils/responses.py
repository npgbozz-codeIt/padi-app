# src/utils/responses.py

ONBOARDING_RESPONSES = {
    "english": {
        "ask_lang": "Welcome to MyPadi! 🇳🇬 Please reply with your preferred language: 'english', 'pidgin', or 'hausa'.",
        "invalid_lang": "Invalid selection. Please type 'english', 'pidgin', or 'hausa'.",
        "ask_phone": "Language saved! Please click the button below to share your phone number securely.",
        "ask_bvn": "Phone number recorded. Kindly type out your 11-digit BVN to continue security verification.",
        "invalid_bvn": "Invalid BVN. Your Bank Verification Number must be exactly 11 numeric digits. Try again:",
        "ask_pin": "BVN accepted! 🔐 Now, enter a secure 4-digit transaction PIN to protect your wallet:",
        "invalid_pin": "Security alert: Your PIN must be exactly 4 digits long. Try again:",
        "confirm_pin": "Please re-type your 4-digit PIN to confirm it:",
        "mismatch_pin": "PINs do not match! Let's restart: Enter a new 4-digit PIN:",
        "completed": "Onboarding complete! 🥳 Welcome to MyPadi. Your account tag is active. What bills are we paying today?",
    },
    "pidgin": {
        "ask_lang": "Welcome to MyPadi! 🇳🇬 Abeg reply with the language wey you prefer: 'english', 'pidgin', or 'hausa'.",
        "invalid_lang": "That choice no follow. Abeg type 'english', 'pidgin', or 'hausa'.",
        "ask_phone": "Language saved sharp-sharp! Abeg click the button below to share your phone number make we link your account.",
        "ask_bvn": "Phone number done land! Now, abeg type your 11-digit BVN make we confirm your secure profile.",
        "invalid_bvn": "This BVN no correct. Your BVN suppose be exactly 11 numbers. Type am again:",
        "ask_pin": "BVN confirmed! 🔐 Now, type the 4-digit PIN wey you wan dey use run transactions:",
        "invalid_pin": "Your PIN must be exactly 4 numbers. Type am again:",
        "confirm_pin": "Abeg enter that same PIN again make we confirm am:",
        "mismatch_pin": "The two PINs no match at all! Make we start again: Type a fresh 4-digit PIN:",
        "completed": "Onboarding finish! 🥳 Welcome to MyPadi, your account done setup live. Which bills we dey pay today?",
    },
    "hausa": {
        "ask_lang": "Barka da zuwa MyPadi! 🇳🇬 Da fatan za ku zaɓi yaren da kuka fi so: 'english', 'pidgin', ko 'hausa'.",
        "invalid_lang": "Zaɓin da ba daidai ba. Da fatan za ku rubuta 'english', 'pidgin', ko 'hausa'.",
        "ask_phone": "An adana yarenku! Tura lambar wayarku don Allah ta danna maballin da ke ƙasa.",
        "ask_bvn": "An yi nasarar adana lambar wayarku. Don Allah saka lambar BVN dinku guda 11.",
        "invalid_bvn": "Lambar BVN ba daidai ba ce. Dole ne ya zama lambobi 11 daidai. Sake gwadawa:",
        "ask_pin": "An karɓi BVN! 🔐 Yanzu, saka lambar sirri guda 4 don kiyaye asusunku:",
        "invalid_pin": "Dole ne lambar sirri ta zama lambobi 4 daidai. Sake gwadawa:",
        "confirm_pin": "Da fatan za ku sake saka lambar sirrin asusunku guda 4 don tabbatarwa:",
        "mismatch_pin": "Lambar sirri ba ta yi daidai ba! Bari mu sake farawa: Saka sabuwar lambar sirri guda 4:",
        "completed": "An kammala rajista! 🥳 Barka da zuwa MyPadi. Wace lissafin kuke son biya yau?",
    },
}

TRANSACTION_RESPONSES = {
    "english": {
        "greeting": "Welcome back, Boss! 🦾\nWhat bills are we taking care of today? Tap an option below or just talk to me naturally!",
        "greeting_markup": {
            "inline_keyboard": [
                [
                    {"text": "📱 Buy Airtime", "callback_data": "menu_airtime"},
                    {"text": "📶 Buy Data", "callback_data": "data_back_to_net:mtn"},
                ],
                [
                    {
                        "text": "💡 Electricity Token",
                        "callback_data": "menu_electricity",
                    },
                    {"text": "📺 Cable TV", "callback_data": "menu_cable"},
                ],
                [
                    {"text": "⚽ Sports Betting", "callback_data": "menu_betting"},
                    {"text": "💬 Type other bills", "callback_data": "action_cancel"},
                ],
            ]
        },
        "airtime_prompt": "📱 *Airtime Vending Mode*\n\nPlease enter the phone number and amount you wish to purchase (e.g., _Send 500 airtime to 08012345678_).",
        "data_prompt": "📶 *Data Vending Mode*\n\nPlease select your provider network from the options or type the explicit bundle allocation you need.",
        "electricity_prompt": "💡 *Electricity Payment Mode*\n\nPlease provide your distribution company name, meter number, and the amount (e.g., _Pay 5000 naira for IKEDC prepaid meter 123456789_).",
        "cable_prompt": "📺 *Cable TV Subscription Mode*\n\nPlease enter your decoder details, package type, and smartcard registration number.",
        "betting_prompt": "⚽ *Betting Wallet Funding Mode*\n\nPlease state your preferred betting company ID reference along with your payment tier details.",
        "missing_slots": "An issue popped up while processing that. Please check that you provided the phone number, correct network provider name, and transaction amount clearly!",
        "insufficient_funds": "🪙 Your balance is running low! Your current wallet balance sits at ₦{balance}. Kindly top up your profile account to complete this trade seamlessly.",
        "vending_success": "🎉 Transaction complete! ₦{amount} {provider} recharge has been successfully applied to target line {recipient}.",
        "vending_failed": "⚠️ We couldn't complete this request right now because the provider gateway reported a service constraint. Please try again shortly or modify your parameters.",
        "coming_soon": "⚡ This bill payment feature is coming soon to MyPadi! Stay tuned.",
        "fallback_safety": "I couldn't quite map that request to a bill, Padi. You can tell me to *'buy MTN airtime'* or *'recharge data'* naturally, and I'll handle it!",
    },
    "pidgin": {
        "greeting": "Welcome back, Boss! 🦾\nWhich bills we dey run today? Select from the options down or just tell me wetin you want!",
        "greeting_markup": {
            "inline_keyboard": [
                [
                    {"text": "📱 Buy Airtime", "callback_data": "menu_airtime"},
                    {"text": "📶 Buy Data", "callback_data": "data_back_to_net:mtn"},
                ],
                [
                    {"text": "💡 Light Token", "callback_data": "menu_electricity"},
                    {"text": "📺 Cable TV", "callback_data": "menu_cable"},
                ],
                [
                    {"text": "⚽ Betting Wallet", "callback_data": "menu_betting"},
                    {"text": "💬 Type other bills", "callback_data": "action_cancel"},
                ],
            ]
        },
        "airtime_prompt": "📱 *Airtime Vending Mode*\n\nAbeg enter the phone number and how much you wan buy (e.g., _Send 500 airtime to 08012345678_).",
        "data_prompt": "📶 *Data Vending Mode*\n\nSelect your network provider or type wetin you wan purchase clear clear.",
        "electricity_prompt": "💡 *Electricity Payment Mode*\n\nAbeg drop your company code, meter number, and the amount (e.g., _Pay 5000 naira for IKEDC prepaid meter 123456789_).",
        "cable_prompt": "📺 *Cable TV Subscription Mode*\n\nTell me your decoder company, package name, and smartcard number make we run am.",
        "betting_prompt": "⚽ *Betting Wallet Funding Mode*\n\nDrop your betting user ID plus the amount make we fund your account sharply.",
        "missing_slots": "Something miss inside details wey you send, boss! Check well make sure network, phone number, and how much dey inside properly.",
        "insufficient_funds": "🪙 Your money no reach this level, boss. Your wallet balance na ₦{balance}. Abeg fund your pocket make we try again.",
        "vending_success": "🎉 E don go successfully! We don wire ₦{amount} {provider} airtime directly to {recipient}.",
        "vending_failed": "⚠️ Gateway network error happen from provider side. Your wallet money intact, abeg chill small or try another provider tier.",
        "coming_soon": "⚡ This bill payment feature dey come soon on MyPadi! Abeg stay tuned.",
        "fallback_safety": "Boss, I no match that bill request clear-clear. You fit tell me *'buy MTN airtime'* or *'recharge data'* normal-normal, and I go run am sharp-sharp! ⚡",
    },
    "hausa": {
        "greeting": "Sannu Padi! 👋 Yaya dai? Wace lissafin kuke son biya yau? Za ku iya zaɓar zaɓi a ƙasa ko kuyi magana dani!",
        "greeting_markup": {
            "inline_keyboard": [
                [
                    {"text": "📱 Sayi Airtime", "callback_data": "menu_airtime"},
                    {"text": "📶 Tura Data", "callback_data": "data_back_to_net:mtn"},
                ],
                [
                    {"text": "💡 Wutar Lantarki", "callback_data": "menu_electricity"},
                    {"text": "📺 Cable TV", "callback_data": "menu_cable"},
                ],
                [
                    {"text": "⚽ Betting", "callback_data": "menu_betting"},
                    {"text": "💬 Rubuta sauran kuɗi", "callback_data": "action_cancel"},
                ],
            ]
        },
        "airtime_prompt": "📱 *Tsarin Airtime*\n\nDa fatan za a shigar da lambar waya da adadin da kuke son saya (misali, _Send 500 airtime to 08012345678_).",
        "data_prompt": "📶 *Tsarin Data*\n\nZaɓi hanyar sadarwa ko rubuta adadin da kuke buƙata sarai.",
        "electricity_prompt": "💡 *Tsarin Wutar Lantarki*\n\nDa fatan za a bayar da sunan kamfani, lambar mita, da adadin kuɗi (misali, _Pay 5000 naira for IKEDC prepaid meter 123456789_).",
        "cable_prompt": "📺 *Tsarin Cable TV*\n\nShigar da bayanan akwatin ku, nau'in fakiti, da lambar katin ku.",
        "betting_prompt": "⚽ *Tsarin Betting*\n\nShigar da ID na kamfanin betting ɗin ku tare da adadin kuɗi.",
        "missing_slots": "❌ Cikakken bayani bai cika ba. Da fatan za a sake dubawa hanyar sadarwa, adadin kudi, da lambar waya.",
        "insufficient_funds": "🪙 Kuɗin ku bai isa ba! Ma'ajin ku na yanzu shine ₦{balance}. Da fatan za a saka kuɗi don ci gaba.",
        "vending_success": "🎉 An yi nasara! An tura ₦{amount} {provider} zuwa {recipient}.",
        "vending_failed": "⚠️ An sami matsala daga kamfanin sadarwa. Da fatan za a sake gwadawa nan ba da jimawa ba.",
        "coming_soon": "⚡ Wannan fasalin biyan kuɗi yana zuwa kwanan nan akan MyPadi! Kasance tare da mu.",
        "fallback_safety": "Ban gane wannan bukatar biyan kuɗi ba sarai. Kuna iya gaya mani *'sayi airtime na MTN'* ko *'sami data'* a sauƙaƙe! ⚡",
    },
}

DATA_RESPONSES = {
    "english": {
        "confirm_direct": "📦 *Confirm Your Data Purchase*\n\nNetwork: {network}\nBundle Size: {size}\nValidity: {validity}\nCost: ₦{price}\nTarget Phone: {phone}\n\nClick the button below to authorize this payment via your wallet securely.",
        "select_validity": "⚡ Choose your preferred *{network}* data lifespan category below:",
        "list_plans": "📂 Available *{network} ({validity})* bundles. Select one to purchase:",
        "price_anchor_fallback": "💡 *Plan Suggestion*\n\nWe couldn't find an exact match for {network} data at that price. Here are the closest active options on the network right now:",
        "no_plans_found": "❌ Sorry Padi, no active data plans match your description at the moment. Type *'Airtel Data'* or *'MTN Data'* to view available options.",
    },
    "pidgin": {
        "confirm_direct": "📦 *Confirm Your Data Purchase*\n\nNetwork: {network}\nBundle Size: {size}\nValidity: {validity}\nAmount: ₦{price}\nPhone Number: {phone}\n\nPress the button down to authorize dis payment from your wallet.",
        "select_validity": "⚡ Select how long you want the *{network}* data to last:",
        "list_plans": "📂 Clear *{network} ({validity})* plans. Choose the one you want:",
        "price_anchor_fallback": "💡 *Better Option For You*\n\nThat exact price no dey for {network} data right now. Check out these active ones wey close to am:",
        "no_plans_found": "❌ Aza man, we no see any plan wey match wetin you type. Abeg type *'MTN Data'* or *'Glo Data'* to see wetin dey ground.",
    },
    "hausa": {
        "confirm_direct": "📦 *Tabbatar da Sayen Data*\n\nHanyar Sadarwa: {network}\nGirman Data: {size}\nTsawon Lokaci: {validity}\nFarashi: ₦{price}\nLambar Waya: {phone}\n\nDanna maɓallin da ke ƙasa don izinin biyan kuɗi.",
        "select_validity": "⚡ Zaɓi tsawon lokacin da kake son *{network}* data ya ɗauka a ƙasa:",
        "list_plans": "📂 Wadatar *{network} ({validity})* data. Zaɓi ɗaya don siya:",
        "price_anchor_fallback": "💡 *Shawara Akan Data*\n\nBa mu sami takaimiman farashi na {network} data ba. Ga zaɓuɓɓuka mafi kusa da ke aiki yanzu:",
        "no_plans_found": "❌ Gafara dai, ba a sami tsarin da ya dace da bayanin ku ba. Rubuta *'MTN Data'* don ganin wadanda ke akwai.",
    },
}
