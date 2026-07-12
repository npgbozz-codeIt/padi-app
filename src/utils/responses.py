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
        "greeting": "Hello Padi! 👋 How can I help you today? You can tell me to buy airtime, purchase data, or handle your bills naturally!",
        "missing_slots": "❌ Details incomplete. Please specify the provider, amount, and phone number clearly.",
        "insufficient_funds": "❌ Transaction failed. Insufficient funds. Your current wallet balance is ₦{balance}.",
        "vending_success": "🎉 Success! ₦{amount} {provider} airtime has been sent to {recipient}.",
        "vending_failed": "❌ Failed: {error}",
        "coming_soon": "⚡ This bill payment feature is coming soon to MyPadi! Stay tuned.",
        "fallback_safety": "I couldn't quite map that request to a bill, Padi. You can tell me to *'buy MTN airtime'* or *'recharge data'* naturally, and I'll handle it!",
    },
    "pidgin": {
        "greeting": "Moni o Padi! 👋 How far? Wetin we dey run today? You fit tell me to buy airtime, data, or pay bills normal-normal!",
        "missing_slots": "❌ Dis details no complete. Abeg tell me the network, how much, and phone number well.",
        "insufficient_funds": "❌ Your money no reach. Your wallet balance na ₦{balance}.",
        "vending_success": "🎉 E don go! We don send ₦{amount} {provider} airtime to {recipient}.",
        "vending_failed": "❌ Error happen: {error}",
        "coming_soon": "⚡ This bill payment feature dey come soon on MyPadi! Abeg stay tuned.",
        "fallback_safety": "Boss, I no match that bill request clear-clear. You fit tell me *'buy MTN airtime'* or *'recharge data'* normal-normal, and I go run am sharp-sharp! ⚡",
    },
    "hausa": {
        "greeting": "Sannu Padi! 👋 Yaya dai? Wace lissafin kuke son biya yau? Za ku iya siyan airtime, data, ko biyan kuɗi a sauƙaƙe!",
        "missing_slots": "❌ Cikakken bayani bai cika ba. Da fatan za a fadi hanyar sadarwa, adadin kudi, da lambar waya.",
        "insufficient_funds": "❌ Kudinka bai isa ba. Ma'ajin ku shine ₦{balance}.",
        "vending_success": "🎉 An yi nasara! An tura ₦{amount} {provider} zuwa {recipient}.",
        "vending_failed": "❌ Kuskure: {error}",
        "coming_soon": "⚡ Wannan fasalin biyan kuɗi yana zuwa kwanan nan akan MyPadi! Kasance tare da mu.",
        "fallback_safety": "Ban gane wannan bukatar biyan kuɗi ba sarai. Kuna iya gaya mani *'sayi airtime na MTN'* ko *'sami data'* a sauƙaƙe, kuma zan tura muku da wuri! ⚡",
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
